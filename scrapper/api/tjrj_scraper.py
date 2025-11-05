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
    Audiencia,
    Publicacao,
    Documento,
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

        # Check if searching by process number - use "Por Número" tab
        if query.numero_processo:
            print(f"Searching by process number: {query.numero_processo}")

            # Click "Por Número" tab
            try:
                await self.frame.click("text=Por Número", timeout=5000)
                print("Clicked 'Por Número' tab")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error clicking Por Número tab: {e}")

            # Fill process number
            # TJRJ process number format: NNNNNNN-DD.AAAA.J.TR.OOOO
            # Need to split into parts
            numero = query.numero_processo.replace(".", "").replace("-", "")

            # Try to fill the process number field
            # The exact selectors depend on the "Por Número" form structure
            try:
                # Wait for the number input field
                await self.frame.wait_for_selector("input[name*='numero' i], input[placeholder*='número' i]", timeout=5000)

                # Try common selectors for process number input
                filled = False
                for selector in ["#numeroProcesso", "input[name='numeroProcesso']", "input[placeholder*='número' i]"]:
                    try:
                        await self.frame.fill(selector, query.numero_processo, timeout=2000)
                        print(f"Filled process number using selector: {selector}")
                        filled = True
                        break
                    except:
                        continue

                if not filled:
                    # Try JavaScript as fallback
                    await self.frame.evaluate(f"""
                        () => {{
                            const input = document.querySelector('input[placeholder*="número" i]');
                            if (input) {{
                                input.value = '{query.numero_processo}';
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            }}
                        }}
                    """)

                # Click search button for "Por Número" tab
                await asyncio.sleep(1)
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
                    print("Clicked Pesquisar button for process number search")
                    return  # Done - exit early since we're searching by number
                else:
                    raise HTTPException(status_code=500, detail="Não foi possível clicar no botão Pesquisar")

            except Exception as e:
                print(f"Error in process number search: {e}")
                raise HTTPException(status_code=500, detail=f"Erro ao buscar por número de processo: {str(e)}")

        # Otherwise, use "Por Nome" search (existing logic)
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

        # 5. Fill Ano Inicial e Final - Use 2022-2025 for last 3 years
        import datetime
        current_year = datetime.datetime.now().year
        ano_inicial = "2022"  # Collect processes from last 3 years
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

    async def extract_process_detail(self, numero_processo: str, skip_click: bool = False) -> ProcessoTJRJ:
        """
        Extract detailed process information by clicking on the process link.
        TJRJ opens details in a new iframe that needs to be accessed.

        Args:
            numero_processo: Process number to extract
            skip_click: If True, assume we're already on the details page (used after search by number)
        """
        assert self.frame  # Deve estar na página de resultados ou detalhes

        if not skip_click:
            print(f"Clicking on process {numero_processo} to open details...")

            # Click on the process link to open details
            # O processo está em um div com role="link" que contém o número
            try:
                # Usar JavaScript para clicar no link correto
                clicked = await self.frame.evaluate(f"""
                    () => {{
                        const links = Array.from(document.querySelectorAll('div[role="link"]'));
                        const processLink = links.find(link =>
                            link.textContent.includes('{numero_processo}')
                        );

                        if (processLink) {{
                            processLink.click();
                            return true;
                        }}
                        return false;
                    }}
                """)

                if not clicked:
                    # Se não encontrou na lista, pode ser que já esteja nos detalhes
                    print(f"Process link not found in list, assuming already on details page")
                    skip_click = True
                else:
                    print("✓ Clicked on process link")

                    # Aguardar o iframe de detalhes ser criado/atualizado
                    # O iframe muda de src para mostrar os detalhes
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"Error clicking process link: {e}, continuing anyway")
                # Continuar para tentar extrair - pode já estar na página de detalhes
        else:
            print("Skipping click - assuming already on details page")
            # Aguardar página de detalhes carregar
            await asyncio.sleep(3)

        # O iframe já existe (mainframe), mas o conteúdo muda
        # Aguardar indicadores de que os detalhes carregaram
        try:
            # Aguardar elementos específicos de detalhe aparecerem
            await self.frame.wait_for_function(
                """() => {
                    const text = document.body.textContent;
                    return text.includes('Classe:') ||
                           text.includes('Assunto:') ||
                           text.includes('Comarca:');
                }""",
                timeout=15000
            )
            print("✓ Process details loaded")
        except PlaywrightTimeoutError:
            print("⚠ Timeout waiting for details indicators")

        # Aguardar um pouco mais para garantir que tudo carregou
        await asyncio.sleep(2)

        # Save HTML for debugging
        try:
            detail_html = await self.frame.evaluate("() => document.body.innerHTML")
            with open("/tmp/tjrj_detail_content.html", "w", encoding="utf-8") as f:
                f.write(detail_html)
            print(f"Saved detail HTML ({len(detail_html)} bytes)")
        except Exception as debug_e:
            print(f"Error saving detail HTML: {debug_e}")

        # Extrair detalhes do processo - TJRJ usa labels com atributo "name"
        extraction_script = """
        () => {
            const data = {
                numeroProcesso: '',
                classe: null,
                assunto: null,
                comarca: null,
                vara: null,
                juiz: null,
                valorCausa: null,
                dataDistribuicao: null,
                autor: null,
                reu: null,
                advogados: [],
                situacao: null,
                movimentos: [],
                audiencias: [],
                publicacoes: [],
                documentos: []
            };

            // TJRJ usa <label name="campo"> para os dados
            const getFieldByName = (name) => {
                const label = document.querySelector(`label[name="${name}"]`);
                return label ? label.textContent.trim() : null;
            };

            // Extrair campos usando labels
            data.classe = getFieldByName('classe');
            data.assunto = getFieldByName('assunto');
            data.comarca = getFieldByName('comarca');
            data.vara = getFieldByName('vara');
            data.juiz = getFieldByName('juiz');
            data.valorCausa = getFieldByName('valorCausa') || getFieldByName('valor');

            // Número do processo - está no título
            const numeroMatch = document.body.textContent.match(/Processo\\s+Nº\\s+(\\d{7}-\\d{2}\\.\\d{4}\\.\\d\\.\\d{2}\\.\\d{4})/);
            if (numeroMatch) {
                data.numeroProcesso = numeroMatch[1];
            }

            // Situação - pode estar em vários lugares
            const situacaoLabel = document.querySelector('label[id*="Situação"], label[for*="Situação"]');
            if (situacaoLabel) {
                data.situacao = situacaoLabel.textContent.replace(/^Situação:\s*/i, '').trim();
            } else {
                // Buscar por texto "Situação:"
                const allText = document.body.textContent;
                const situacaoMatch = allText.match(/Situação:\\s*([^\\n<]+)/i);
                if (situacaoMatch) {
                    data.situacao = situacaoMatch[1].trim();
                }
            }

            // Autor e Réu - estão na seção "Dados dos Personagens"
            const personagens = document.querySelectorAll('label[for="personagemDesc"]');
            personagens.forEach(label => {
                const tipo = label.textContent.trim();
                const valor = label.nextElementSibling?.textContent?.trim();

                if (tipo === 'Autor' && valor) {
                    data.autor = valor.replace(/e outro\(s\)\.\.\./i, '').trim();
                }
                if (tipo === 'Réu' && valor) {
                    data.reu = valor.trim();
                }
            });

            // Se não encontrou, tentar por tabela
            if (!data.autor || !data.reu) {
                const personTable = document.querySelector('tbody.p-datatable-tbody');
                if (personTable) {
                    const rows = personTable.querySelectorAll('tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const tipo = cells[0].textContent.trim();
                            const nome = cells[1].textContent.trim();

                            if (tipo === 'Autor') data.autor = nome;
                            if (tipo === 'Réu') data.reu = nome;
                        }
                    });
                }
            }

            // Advogados - buscar por texto
            const allLabels = document.querySelectorAll('label');
            allLabels.forEach(label => {
                const text = label.textContent;
                if (text.includes('Advogad')) {
                    const advMatch = text.match(/Advogad[oa]:\\s*(.+?)(?:OAB|$)/i);
                    if (advMatch) {
                        const advNome = advMatch[1].trim();
                        if (advNome && !data.advogados.includes(advNome)) {
                            data.advogados.push(advNome);
                        }
                    }
                }
            });

            // Movimentações - última movimentação
            const tipoMov = document.querySelector('.titulo-movimentacao');
            if (tipoMov) {
                const movimento = {
                    data: null,
                    descricao: tipoMov.textContent.replace('Tipo do Movimento:', '').trim()
                };

                // Buscar data da movimentação
                const dataLabels = document.querySelectorAll('label[id*="Data"]');
                dataLabels.forEach(label => {
                    const text = label.textContent;
                    const dataMatch = text.match(/\\d{2}\\/\\d{2}\\/\\d{4}/);
                    if (dataMatch && !movimento.data) {
                        // Convert DD/MM/YYYY to YYYY-MM-DD (ISO format)
                        const [dia, mes, ano] = dataMatch[0].split('/');
                        movimento.data = `${ano}-${mes}-${dia}`;
                    }
                });

                if (movimento.descricao) {
                    data.movimentos.push(movimento);
                }
            }

            // Audiências - buscar por tabelas ou seções com "audiência"
            const audienciaKeywords = /audi[êe]ncia/i;
            document.querySelectorAll('table, div[class*="audiencia"], div[id*="audiencia"]').forEach(elem => {
                const text = elem.textContent;
                if (audienciaKeywords.test(text)) {
                    // Try to extract from table
                    const rows = elem.querySelectorAll('tr');
                    rows.forEach((row, idx) => {
                        if (idx === 0) return; // Skip header
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const dataCell = cells[0]?.textContent?.trim();
                            const tipoCell = cells[1]?.textContent?.trim();
                            const localCell = cells[2]?.textContent?.trim();
                            const statusCell = cells[3]?.textContent?.trim();

                            if (dataCell || tipoCell) {
                                data.audiencias.push({
                                    data: dataCell || null,
                                    tipo: tipoCell || null,
                                    local: localCell || null,
                                    status: statusCell || null,
                                    observacoes: cells.length > 4 ? cells[4]?.textContent?.trim() : null
                                });
                            }
                        }
                    });

                    // If no rows found, just extract as observacoes
                    if (rows.length === 0 && text.length < 500) {
                        data.audiencias.push({
                            data: null,
                            tipo: null,
                            local: null,
                            status: null,
                            observacoes: text.trim()
                        });
                    }
                }
            });

            // Publicações/Intimações
            const publicacaoKeywords = /publica[çc][ãa]o|intima[çc][ãa]o/i;
            document.querySelectorAll('div, section, table').forEach(elem => {
                const text = elem.textContent;
                const elemId = elem.id || '';
                const elemClass = elem.className || '';

                if (publicacaoKeywords.test(text) || publicacaoKeywords.test(elemId) || publicacaoKeywords.test(elemClass)) {
                    // Check for links
                    const links = elem.querySelectorAll('a');
                    links.forEach(link => {
                        const linkText = link.textContent.trim();
                        const href = link.href;
                        if (linkText && linkText.length > 3) {
                            const dataMatch = link.closest('tr, div')?.textContent.match(/\\d{2}\\/\\d{2}\\/\\d{4}/);
                            data.publicacoes.push({
                                data: dataMatch ? dataMatch[0] : null,
                                tipo: 'Publicação',
                                destinatario: null,
                                descricao: linkText,
                                link: href || null
                            });
                        }
                    });

                    // If no links but has text content
                    if (links.length === 0 && text.length > 10 && text.length < 1000) {
                        const dataMatch = text.match(/\\d{2}\\/\\d{2}\\/\\d{4}/);
                        data.publicacoes.push({
                            data: dataMatch ? dataMatch[0] : null,
                            tipo: 'Publicação',
                            destinatario: null,
                            descricao: text.trim(),
                            link: null
                        });
                    }
                }
            });

            // Documentos/Anexos - buscar links com keywords
            const docKeywords = /documento|peti[çc][ãa]o|download|anexo|decis[ãa]o|senten[çc]a|despacho/i;
            document.querySelectorAll('a').forEach(link => {
                const linkText = link.textContent.trim();
                const href = link.href || '';

                if (docKeywords.test(linkText) || docKeywords.test(href)) {
                    if (linkText && linkText.length > 3 && linkText.length < 200) {
                        // Extract date from parent context
                        const parent = link.closest('tr, div');
                        const dataMatch = parent?.textContent.match(/\\d{2}\\/\\d{2}\\/\\d{4}/);

                        // Determine document type
                        let tipo = 'Documento';
                        const lowerText = linkText.toLowerCase();
                        if (/peti[çc][ãa]o/i.test(lowerText)) tipo = 'Petição';
                        else if (/decis[ãa]o/i.test(lowerText)) tipo = 'Decisão';
                        else if (/senten[çc]a/i.test(lowerText)) tipo = 'Sentença';
                        else if (/despacho/i.test(lowerText)) tipo = 'Despacho';

                        data.documentos.push({
                            nome: linkText,
                            tipo: tipo,
                            data_juntada: dataMatch ? dataMatch[0] : null,
                            autor: null,
                            link: href.startsWith('http') ? href : null
                        });
                    }
                }
            });

            // Also look for document sections by id/class
            document.querySelectorAll('div[id*="documento"], div[class*="documento"], section[id*="documento"]').forEach(section => {
                const spans = section.querySelectorAll('span, div.documento-nome, td');
                spans.forEach(span => {
                    const text = span.textContent.trim();
                    if (text.length >= 5 && text.length <= 200) {
                        // Skip if already added
                        if (data.documentos.some(d => d.nome === text)) return;

                        // Check if looks like document name
                        if (docKeywords.test(text)) {
                            data.documentos.push({
                                nome: text,
                                tipo: 'Documento',
                                data_juntada: null,
                                autor: null,
                                link: null
                            });
                        }
                    }
                });
            });

            return data;
        }
        """

        try:
            data = await self.frame.evaluate(extraction_script)

            print(f"Extracted data: numeroProcesso={data.get('numeroProcesso')}, classe={data.get('classe')}, autor={data.get('autor')}")

            # Convert extracted data to Pydantic models
            audiencias = [Audiencia(**aud) for aud in data.get("audiencias", [])]
            publicacoes = [Publicacao(**pub) for pub in data.get("publicacoes", [])]
            documentos = [Documento(**doc) for doc in data.get("documentos", [])]

            return ProcessoTJRJ(
                uf="RJ",
                numeroProcesso=data.get("numeroProcesso") or numero_processo,
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
                movimentos=data.get("movimentos", []),
                audiencias=audiencias,
                publicacoes=publicacoes,
                documentos=documentos,
            )
        except Exception as e:
            print(f"Error extracting process details: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Falha ao extrair detalhes do processo: {str(e)}"
            )


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
    Primeiro faz uma busca pelo número do processo para chegar na lista de resultados,
    depois clica no processo para abrir os detalhes.
    """
    settings = get_settings()

    async with TJRJFetcher(settings) as fetcher:
        # Primeiro, fazer uma busca pelo número do processo
        # Isso nos leva para a página de resultados onde podemos clicar no processo
        print(f"Searching for process {numero_processo} first...")

        # Criar query com o número do processo
        query = TJRJProcessoQuery(
            numero_processo=numero_processo,
            instancia="1"  # Tentar 1ª instância primeiro
        )

        # Navegar e buscar
        await fetcher.navigate_to_search()

        # Para busca por número, usar o formulário "Por Número"
        # Busca por número geralmente vai direto para a página de detalhes
        try:
            # Submeter busca (vai usar "Por Número" se numero_processo estiver preenchido)
            await fetcher.submit_query(query)

            # Aguardar resultados/detalhes
            await asyncio.sleep(3)

            # Extrair detalhes - skip_click=True pois busca por número já vai direto pros detalhes
            return await fetcher.extract_process_detail(numero_processo, skip_click=True)

        except Exception as e:
            print(f"Error in process detail fetch: {e}")
            import traceback
            traceback.print_exc()

            # Se falhar, tentar retornar pelo menos o básico
            return ProcessoTJRJ(
                uf="RJ",
                numeroProcesso=numero_processo,
                classe=None,
                assunto=None,
                comarca=None,
                vara=None,
                juiz=None,
                valorCausa=None,
                dataDistribuicao=None,
                autor=None,
                reu=None,
                advogados=[],
                situacao=None,
                linkPublico=f"{BASE_URL}#/processo/{numero_processo}",
                movimentos=[],
                audiencias=[],
                publicacoes=[],
                documentos=[],
            )
