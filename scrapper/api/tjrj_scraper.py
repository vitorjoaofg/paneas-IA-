from __future__ import annotations

import asyncio
import contextlib
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from .config import Settings, get_settings
from .models import (
    Movimento,
    ProcessoResumoTJRJ,
    ProcessoTJRJ,
    TJRJProcessoListResponse,
    TJRJProcessoQuery,
)

BASE_URL = "https://www3.tjrj.jus.br/consultaprocessual/"


class TJRJFetcher:
    """Fetcher for TJRJ (Tribunal de Justiça do Rio de Janeiro) processes using Playwright."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.frame: Optional[Any] = None  # Will hold the iframe context

    async def __aenter__(self) -> "TJRJFetcher":
        playwright = await async_playwright().start()
        browser_launcher = getattr(playwright, self.settings.playwright_browser)

        # Use headless with anti-detection for TJRJ
        launch_kwargs: Dict[str, Any] = {
            "headless": True,
            "args": [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        }

        self.browser = await browser_launcher.launch(**launch_kwargs)
        self.context = await self.browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            # Anti-bot detection settings
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        # Add comprehensive anti-detection scripts
        await self.context.add_init_script("""
            // Overwrite the `plugins` property to use a custom getter.
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Overwrite the `plugins` property
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Overwrite the `languages` property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en']
            });

            // Remove Playwright/Puppeteer traces
            delete navigator.__proto__.webdriver;

            // Chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        self.page = await self.context.new_page()
        self.page.set_default_navigation_timeout(self.settings.navigation_timeout_ms)
        self.page.set_default_timeout(self.settings.navigation_timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        with contextlib.suppress(Exception):
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()

    async def navigate_to_search(self) -> None:
        """Navigate to TJRJ consultation page and wait for Angular to load."""
        assert self.page

        # Navigate to the consultation page with hash route
        base_url = f"{BASE_URL}#/consultapublica"

        try:
            # Use networkidle to wait for Angular to settle
            response = await self.page.goto(base_url, wait_until="networkidle", timeout=30000)
            if not response or response.status >= 500:
                raise HTTPException(status_code=503, detail="Portal TJRJ indisponível no momento.")
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=504, detail="Portal TJRJ demorou muito para responder.")

        print(f"Navigated to: {self.page.url}")

        # Add small random delay to mimic human behavior
        import random
        await asyncio.sleep(random.uniform(1.0, 2.0))

        # Wait for Angular app to be fully bootstrapped by checking for specific Angular component
        try:
            await self.page.wait_for_selector("app-consulta-publica", timeout=15000, state="attached")
            print("Angular app loaded (app-consulta-publica found)")
        except PlaywrightTimeoutError:
            print("Warning: app-consulta-publica not found, continuing...")

        # Wait for iframe to be created dynamically by Angular
        print("Waiting for iframe #mainframe...")
        try:
            await self.page.wait_for_selector("#mainframe", timeout=30000, state="attached")
            print("✓ Found iframe #mainframe")

            # Extra wait for iframe src to load
            await asyncio.sleep(random.uniform(0.5, 1.5))

        except PlaywrightTimeoutError:
            # Debug: check page state
            try:
                has_app = await self.page.query_selector("app-root")
                has_iframe_component = await self.page.query_selector("app-iframe")
                html_snippet = await self.page.evaluate("() => document.body.innerHTML.substring(0, 1500)")

                print(f"Debug - has app-root: {has_app is not None}")
                print(f"Debug - has app-iframe: {has_iframe_component is not None}")
                print(f"Debug - HTML: {html_snippet[:500]}")

                # Try to detect bot blocking
                if "router-outlet" in html_snippet and len(html_snippet) < 2000:
                    raise HTTPException(status_code=403, detail="Portal TJRJ bloqueou acesso automatizado (detecção de bot)")
            except HTTPException:
                raise
            except:
                pass

            raise HTTPException(status_code=503, detail="Portal TJRJ não carregou o iframe principal (timeout 30s).")

        # Get the iframe
        iframe_element = await self.page.query_selector("#mainframe")
        if not iframe_element:
            raise HTTPException(status_code=503, detail="Iframe #mainframe não encontrado.")

        # Get the frame content
        frame = await iframe_element.content_frame()
        if not frame:
            raise HTTPException(status_code=503, detail="Não foi possível acessar o conteúdo do iframe.")

        print(f"Switched to iframe context")
        self.frame = frame

        # Wait for Angular to load inside the iframe
        await asyncio.sleep(2)  # Reduced from 5s - TJRJ loads fast

        # Wait for network to be idle inside iframe
        try:
            await frame.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass

        # Click on "Por Nome" tab within the iframe to activate that search form
        try:
            await frame.wait_for_selector("text=Por Nome", timeout=10000, state="visible")
            await frame.click("text=Por Nome")
            print("Clicked 'Por Nome' tab in iframe")
            await asyncio.sleep(1)  # Reduced from 2s
        except PlaywrightTimeoutError:
            print("Warning: Could not find/click 'Por Nome' tab in iframe")

        # Wait for form-specific content to appear in the iframe
        form_loaded = False
        form_indicators = [
            "text=Nome da parte",
            "text=Ano Inicial",
            "text=Origem",
            "input[placeholder*='Informe o nome' i]"
        ]

        for indicator in form_indicators:
            try:
                await frame.wait_for_selector(indicator, timeout=10000, state="visible")
                print(f"Form loaded - found indicator: {indicator}")
                form_loaded = True
                break
            except PlaywrightTimeoutError:
                continue

        if not form_loaded:
            print("Warning: Form indicators not found in iframe, trying additional wait...")
            await asyncio.sleep(2)  # Reduced from 5s

        # Debug: Check iframe content
        try:
            frame_url = frame.url
            print(f"Frame URL: {frame_url}")

            inputs_info = await frame.evaluate("""
                () => {
                    const inputs = Array.from(document.querySelectorAll('input'));
                    return inputs.map(inp => ({
                        id: inp.id,
                        name: inp.name,
                        placeholder: inp.placeholder,
                        type: inp.type,
                        visible: inp.offsetParent !== null
                    }));
                }
            """)
            visible_inputs = [inp for inp in inputs_info if inp['visible']]
            print(f"Available inputs in iframe ({len(inputs_info)} total, {len(visible_inputs)} visible): {visible_inputs[:5]}")

            # Check for buttons
            buttons = await frame.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    return btns.map(btn => btn.textContent.trim()).filter(t => t);
                }
            """)
            print(f"Buttons found in iframe: {buttons[:10]}")
        except Exception as e:
            print(f"Error in debug: {e}")

        # Wait for search form to be visible in iframe - try multiple possible selectors
        nome_parte_selectors = [
            "#nomeParte",
            "input[placeholder*='nome da parte' i]",
            "input[placeholder*='Informe o nome' i]",
            "input[name='nomeParte']"
        ]

        found = False
        for selector in nome_parte_selectors:
            try:
                await frame.wait_for_selector(selector, timeout=5000, state="visible")
                print(f"Found nome parte field with selector: {selector}")
                found = True
                break
            except PlaywrightTimeoutError:
                continue

        if not found:
            # Try to save screenshot for debugging
            try:
                await self.page.screenshot(path="/tmp/tjrj_error.png")
                print("Screenshot saved to /tmp/tjrj_error.png")
            except:
                pass
            raise HTTPException(status_code=503, detail="Portal TJRJ não carregou o formulário de busca (campo nomeParte não encontrado).")

    async def submit_query(self, query: TJRJProcessoQuery) -> None:
        """Submit search query on TJRJ portal."""
        assert self.frame

        # Wait for form to be ready
        await asyncio.sleep(1)

        # 1. Select "Origem" (Instância) - OBRIGATÓRIO
        # Click on the dropdown to open it
        await self.frame.click("#filtroOrigem1", timeout=5000)
        await asyncio.sleep(0.5)

        # Select instância based on query
        instancia_map = {
            "1": "1ª Instância",
            "2": "Tribunal de Justiça (2ª Instância)",
            "juizados": "Juizados Especiais",
            "execucoes": "Vara de Execuções Penais",
        }
        instancia_text = instancia_map.get(query.instancia or "1", "1ª Instância")

        # Click on the option containing the instância text
        await self.frame.click(f"li:has-text('{instancia_text}')", timeout=3000)
        await asyncio.sleep(1.5)  # Wait for comarca/competencia to load

        # 2. Comarca - Select "Todas" (NECESSÁRIO para trazer resultados)
        try:
            comarca_input = await self.frame.query_selector("#filtroComarca1")
            if comarca_input:
                is_readonly = await comarca_input.get_attribute("readonly")
                if not is_readonly:
                    await self.frame.click("#filtroComarca1", timeout=3000)
                    await asyncio.sleep(0.5)
                    # Select "Todas"
                    await self.frame.click("li:has-text('Todas')", timeout=3000)
                    await asyncio.sleep(1)
                    print("Selected Comarca: Todas")
        except Exception as e:
            print(f"Could not select Comarca: {e}")

        # 3. Competência - Use from query or default to Cível
        try:
            competencia_input = await self.frame.query_selector("#filtroCompetencia1")
            if competencia_input:
                is_readonly = await competencia_input.get_attribute("readonly")
                if not is_readonly:
                    await self.frame.click("#filtroCompetencia1", timeout=3000)
                    await asyncio.sleep(0.5)
                    # Use competencia from query or default to Cível
                    competencia_text = query.competencia or "Cível"
                    await self.frame.click(f"li:has-text('{competencia_text}')", timeout=3000)
                    await asyncio.sleep(0.5)
                    print(f"Selected Competência: {competencia_text}")
        except Exception as e:
            print(f"Could not select Competência: {e}")

        # 4. Fill Nome da Parte - OBRIGATÓRIO
        if query.nome_parte:
            await self.frame.fill("#nomeParte", query.nome_parte, timeout=3000)

        # 5. Fill Ano Inicial e Final - Use 2024-2025 for better results
        import datetime
        current_year = datetime.datetime.now().year
        ano_inicial = "2024"  # Changed from 2020 to 2024
        ano_final = str(current_year)

        await self.frame.fill("#anoInicial1", ano_inicial, timeout=3000)
        await self.frame.fill("#anoFinal1", ano_final, timeout=3000)
        print(f"Using years: {ano_inicial} - {ano_final}")

        # 6. Click search button
        # First, wait a moment for any dynamic updates
        await asyncio.sleep(1)

        # There are multiple "Pesquisar" buttons (one per tab)
        # We need to click the visible one, which is for the "Por Nome" tab
        clicked = False
        try:
            # Use JavaScript to click the first visible "Pesquisar" button
            result = await self.frame.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const pesquisarBtn = buttons.find(btn =>
                        btn.textContent.trim() === 'Pesquisar' &&
                        btn.offsetParent !== null
                    );
                    if (pesquisarBtn) {
                        pesquisarBtn.click();
                        return true;
                    }
                    return false;
                }
            """)
            if result:
                print("Clicked Pesquisar button via JavaScript")
                clicked = True
            else:
                print("Could not find visible Pesquisar button")
        except Exception as e:
            print(f"Error clicking button via JavaScript: {e}")

        if not clicked:
            raise HTTPException(status_code=500, detail="Não foi possível localizar o botão de consulta")

        # Wait for Angular to render results
        print("Waiting for results to load...")
        await asyncio.sleep(3)  # Reduced from 8s - TJRJ is fast
        print("Wait complete, proceeding to extract results")

        # Save screenshot and HTML for debugging
        try:
            await self.page.screenshot(path="/tmp/tjrj_results_page.png", full_page=True)
            results_html = await self.frame.evaluate("() => document.body.innerHTML")
            with open("/tmp/tjrj_results_content.html", "w", encoding="utf-8") as f:
                f.write(results_html)
            print(f"Saved results screenshot and HTML ({len(results_html)} bytes)")
        except Exception as e:
            print(f"Error saving debug files: {e}")

    async def extract_process_list(self) -> List[ProcessoResumoTJRJ]:
        """Extract list of processes from search results page."""
        assert self.frame

        # Extract process list based on actual TJRJ structure
        # TJRJ uses Angular components with nested divs for each process

        extraction_script = """
        () => {
            const processes = [];

            // Debug: Log all div counts
            const allDivs = document.querySelectorAll('div');
            const textoLinkDivs = document.querySelectorAll('div.texto-link');
            const processoText = Array.from(allDivs).filter(d => d.textContent.includes('Processo:'));

            console.log(`Total divs: ${allDivs.length}`);
            console.log(`Divs with class texto-link: ${textoLinkDivs.length}`);
            console.log(`Divs containing 'Processo:': ${processoText.length}`);

            // Find all divs that contain "Processo:" label
            const processDivs = Array.from(document.querySelectorAll('div.texto-link'))
                .filter(div => div.textContent.includes('Processo:'));

            console.log(`Process divs to extract: ${processDivs.length}`);

            // If no process divs found, return debug info
            if (processDivs.length === 0) {
                return {
                    debug: true,
                    totalDivs: allDivs.length,
                    textoLinkDivs: textoLinkDivs.length,
                    processoTextDivs: processoText.length,
                    processes: []
                };
            }

            processDivs.forEach(processDiv => {
                try {
                    // Extract process number from the div with "Processo:" label
                    const numeroText = processDiv.textContent;
                    const numeroMatch = numeroText.match(/(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})/);
                    if (!numeroMatch) return;

                    const numeroProcesso = numeroMatch[1];

                    // Get the parent container to find other fields
                    let parent = processDiv.parentElement;
                    while (parent && !parent.classList.contains('ng-star-inserted')) {
                        parent = parent.parentElement;
                    }

                    if (!parent) return;

                    // Extract Autor, Réu, and other fields from sibling divs
                    const allDivs = Array.from(parent.querySelectorAll('div'));

                    let autor = null;
                    let reu = null;
                    let descricao = null;

                    allDivs.forEach(div => {
                        const text = div.textContent.trim();
                        if (text.startsWith('Autor:')) {
                            autor = text.replace('Autor:', '').trim();
                        } else if (text.startsWith('Réu:')) {
                            reu = text.replace('Réu:', '').trim();
                        } else if (text.startsWith('Descrição')) {
                            descricao = text.replace('Descrição', '').trim();
                        }
                    });

                    // Build parties list
                    const partes = [];
                    if (autor) partes.push(`Autor: ${autor}`);
                    if (reu) partes.push(`Réu: ${reu}`);

                    processes.push({
                        numeroProcesso,
                        classe: null,
                        assunto: descricao,
                        comarca: null,
                        vara: null,
                        partesRelacionadas: partes,
                        dataDistribuicao: null
                    });
                } catch (e) {
                    console.error('Error parsing process:', e);
                }
            });

            return processes;
        }
        """

        try:
            result = await self.frame.evaluate(extraction_script)

            # Check if result is a dict with debug info or a list
            if isinstance(result, dict) and 'debug' in result:
                print(f"DEBUG: Total divs: {result.get('totalDivs', 'N/A')}")
                print(f"DEBUG: texto-link divs: {result.get('textoLinkDivs', 'N/A')}")
                print(f"DEBUG: Processo text divs: {result.get('processoTextDivs', 'N/A')}")
                result = result.get('processes', [])

            print(f"Extraction script returned {len(result)} raw items")

            processes = []
            for item in result:
                # Build full link if relative
                link = item.get("href") or ""
                if link and not link.startswith("http"):
                    link = f"{BASE_URL}{link.lstrip('/')}"

                processes.append(ProcessoResumoTJRJ(
                    numeroProcesso=item["numeroProcesso"],
                    classe=item.get("classe"),
                    assunto=item.get("assunto"),
                    comarca=item.get("comarca"),
                    vara=item.get("vara"),
                    partesRelacionadas=item.get("partesRelacionadas", []),
                    dataDistribuicao=item.get("dataDistribuicao"),
                    linkPublico=link or f"{BASE_URL}#/processo/{item['numeroProcesso']}"
                ))

            print(f"Returning {len(processes)} processes from extraction")
            return processes

        except Exception as e:
            # If extraction fails, return empty list
            # In production, we might want to log this
            print(f"Extraction failed with error: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def extract_process_detail(self, numero_processo: str) -> ProcessoTJRJ:
        """Extract detailed process information."""
        assert self.page

        # Navigate to process detail page
        # Note: URL structure may need adjustment
        detail_url = f"{BASE_URL}#/processo/{numero_processo}"
        await self.page.goto(detail_url)
        await asyncio.sleep(2)  # Wait for Angular to load

        # Extract process details
        # This is a placeholder - will need adjustment based on real page structure
        extraction_script = """
        () => {
            const getText = (selector) => {
                const elem = document.querySelector(selector);
                return elem ? elem.textContent.trim() : null;
            };

            return {
                numeroProcesso: getText('.numero-processo, #numeroProcesso') || '',
                classe: getText('.classe, #classe'),
                assunto: getText('.assunto, #assunto'),
                comarca: getText('.comarca, #comarca'),
                vara: getText('.vara, #vara'),
                juiz: getText('.juiz, #juiz'),
                valorCausa: getText('.valor-causa, #valorCausa'),
                dataDistribuicao: getText('.data-distribuicao, #dataDistribuicao'),
                autor: getText('.autor, #autor'),
                reu: getText('.reu, #reu'),
                situacao: getText('.situacao, #situacao'),
                advogados: Array.from(document.querySelectorAll('.advogado, .advogados li')).map(el => el.textContent.trim()),
                movimentos: []
            };
        }
        """

        try:
            data = await self.page.evaluate(extraction_script)

            return ProcessoTJRJ(
                uf="RJ",
                numeroProcesso=data["numeroProcesso"] or numero_processo,
                classe=data.get("classe"),
                assunto=data.get("assunto"),
                comarca=data.get("comarca"),
                vara=data.get("vara"),
                juiz=data.get("juiz"),
                valorCausa=data.get("valorCausa"),
                dataDistribuicao=data.get("dataDistribuicao"),
                autor=data.get("autor"),
                reu=data.get("reu"),
                advogados=data.get("advogados", []),
                situacao=data.get("situacao"),
                linkPublico=f"{BASE_URL}#/processo/{numero_processo}",
                movimentos=[]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Falha ao extrair detalhes do processo: {str(e)}")


async def fetch_tjrj_process_list(query: TJRJProcessoQuery) -> TJRJProcessoListResponse:
    """
    Busca lista de processos no TJRJ usando os filtros fornecidos.
    Tenta múltiplas variações do nome se necessário.
    """
    settings = get_settings()

    async with TJRJFetcher(settings) as fetcher:
        await fetcher.navigate_to_search()

        # Try with original query first
        await fetcher.submit_query(query)
        processos = await fetcher.extract_process_list()

        # If no results and nome_parte was provided, try with common suffixes (like PJE)
        if len(processos) == 0 and query.nome_parte:
            nome_original = query.nome_parte.strip()

            # Check if already has a suffix
            has_suffix = any(
                sufixo in nome_original.upper()
                for sufixo in ["SA", "S/A", "S.A.", "LTDA", "LTDA.", "ME", "EPP", "EIRELI"]
            )

            if not has_suffix:
                # Try common suffixes
                sufixos = ["SA", "S/A", "LTDA", "S.A."]

                for sufixo in sufixos:
                    query_variacao = TJRJProcessoQuery(
                        nome_parte=f"{nome_original} {sufixo}",
                        documento_parte=query.documento_parte,
                        nome_advogado=query.nome_advogado,
                        numero_oab=query.numero_oab,
                        numero_processo=query.numero_processo,
                        instancia=query.instancia,
                        competencia=query.competencia,
                        comarca=query.comarca,
                    )

                    try:
                        print(f"Trying name variation: {query_variacao.nome_parte}")
                        await fetcher.navigate_to_search()
                        await fetcher.submit_query(query_variacao)
                        processos = await fetcher.extract_process_list()

                        if len(processos) > 0:
                            break
                    except HTTPException:
                        # If retry navigation fails, just return what we have
                        print(f"Failed to retry with suffix {sufixo}, returning current results")
                        break

        return TJRJProcessoListResponse(
            total_processos=len(processos),
            processos=processos
        )


async def fetch_tjrj_process_detail(numero_processo: str) -> ProcessoTJRJ:
    """
    Busca detalhes completos de um processo TJRJ.
    """
    settings = get_settings()

    async with TJRJFetcher(settings) as fetcher:
        return await fetcher.extract_process_detail(numero_processo)
