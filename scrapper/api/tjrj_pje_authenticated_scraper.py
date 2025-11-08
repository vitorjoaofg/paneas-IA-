"""
Scrapper para o sistema PJE AUTENTICADO do TJRJ
https://tjrj.pje.jus.br/pje/ (área do advogado com login)

Este scrapper é diferente do tjrj_scraper.py (consulta pública).
Aqui fazemos login e acessamos o painel do advogado para buscar processos.
"""

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
    ProcessoResumoTJRJ,
    ProcessoTJRJ,
    TJRJProcessoListResponse,
    TJRJProcessoQuery,
    Movimento,
    Audiencia,
    Publicacao,
    Documento,
)

# URLs do sistema PJE TJRJ
PJE_BASE_URL = "https://tjrj.pje.jus.br/pje"
LOGIN_URL = f"{PJE_BASE_URL}/loginOld.seam"
PAINEL_ADVOGADO_URL = f"{PJE_BASE_URL}/Painel/painel_usuario/advogado.seam"


class TJRJPJEAuthenticatedFetcher:
    """
    Fetcher para o sistema PJE AUTENTICADO do TJRJ.
    Faz login como advogado e acessa o painel para buscar processos.
    """

    def __init__(self, settings: Settings, cpf: str, senha: str):
        self.settings = settings
        self.cpf = cpf
        self.senha = senha
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self) -> "TJRJPJEAuthenticatedFetcher":
        playwright = await async_playwright().start()
        browser_launcher = getattr(playwright, self.settings.playwright_browser)

        # Anti-bot configuration
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
            extra_http_headers={
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )

        # Anti-detection scripts
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en']
            });
            delete navigator.__proto__.webdriver;
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
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

    async def login(self) -> None:
        """
        Faz login no sistema PJE do TJRJ.
        URL: https://tjrj.pje.jus.br/pje/loginOld.seam
        """
        assert self.page
        print(f"[TJRJ PJE] Navigating to login page: {LOGIN_URL}")

        try:
            # Navegar para página de login
            response = await self.page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
            if not response or response.status >= 500:
                raise HTTPException(status_code=503, detail="Portal PJE TJRJ indisponível no momento.")
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=504, detail="Portal PJE TJRJ demorou muito para responder.")

        print(f"[TJRJ PJE] Login page loaded: {self.page.url}")
        await asyncio.sleep(1)

        # Aguardar formulário de login
        try:
            await self.page.wait_for_selector("input[name*='username'], input[id*='username'], input[type='text']", timeout=10000)
            print("[TJRJ PJE] Login form found")
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=503, detail="Formulário de login não encontrado.")

        # Preencher CPF (username)
        # Tentar múltiplos seletores comuns para username
        username_filled = False
        for selector in ["#username", "input[name='username']", "input[id*='username']", "input[type='text']"]:
            try:
                await self.page.fill(selector, self.cpf, timeout=2000)
                print(f"[TJRJ PJE] CPF filled using selector: {selector}")
                username_filled = True
                break
            except:
                continue

        if not username_filled:
            raise HTTPException(status_code=500, detail="Não foi possível preencher o campo de usuário (CPF).")

        await asyncio.sleep(0.5)

        # Preencher senha
        password_filled = False
        for selector in ["#password", "input[name='password']", "input[type='password']"]:
            try:
                await self.page.fill(selector, self.senha, timeout=2000)
                print(f"[TJRJ PJE] Password filled using selector: {selector}")
                password_filled = True
                break
            except:
                continue

        if not password_filled:
            raise HTTPException(status_code=500, detail="Não foi possível preencher o campo de senha.")

        await asyncio.sleep(0.5)

        # Clicar no botão de login
        try:
            # Aguardar um pouco para garantir que o formulário está pronto
            await asyncio.sleep(1)

            # Listar todos os botões disponíveis para debug
            buttons_info = await self.page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'));
                    return buttons.map(btn => ({
                        tag: btn.tagName,
                        type: btn.type,
                        id: btn.id,
                        name: btn.name,
                        value: btn.value,
                        text: btn.textContent?.trim(),
                        classes: btn.className
                    }));
                }
            """)
            print(f"[TJRJ PJE] Available buttons: {buttons_info}")

            # Tentar clicar usando JavaScript diretamente
            login_clicked = await self.page.evaluate("""
                () => {
                    // Tentar por ID comum
                    const loginBtn = document.querySelector('#loginButton, #btnLogin, #submit, button[name="login"]');
                    if (loginBtn) {
                        loginBtn.click();
                        return 'id/name selector';
                    }

                    // Tentar por texto do botão
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"]'));
                    for (let btn of buttons) {
                        const text = btn.textContent?.toLowerCase() || btn.value?.toLowerCase() || '';
                        if (text.includes('entrar') || text.includes('login') || text.includes('acessar')) {
                            btn.click();
                            return 'text: ' + text;
                        }
                    }

                    // Tentar primeiro submit button visível
                    for (let btn of buttons) {
                        if ((btn.type === 'submit' || btn.tagName === 'BUTTON') && btn.offsetParent !== null) {
                            btn.click();
                            return 'first visible submit';
                        }
                    }

                    // Tentar submeter formulário diretamente
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                        return 'form.submit()';
                    }

                    return null;
                }
            """)

            if login_clicked:
                print(f"[TJRJ PJE] Login button clicked via JavaScript: {login_clicked}")
            else:
                raise HTTPException(status_code=500, detail="Botão de login não encontrado.")

        except HTTPException:
            raise
        except Exception as e:
            print(f"[TJRJ PJE] Error clicking login button: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao clicar no botão de login: {str(e)}")

        # Aguardar navegação após login
        print("[TJRJ PJE] Waiting for login to complete...")
        await asyncio.sleep(3)

        # Verificar se login foi bem-sucedido
        # Se houver erro de login ou sistema fora do ar, aparece uma mensagem
        try:
            error_info = await self.page.evaluate("""
                () => {
                    // Verificar erro específico do banco de dados (sistema fora)
                    const dbErrorElements = document.querySelectorAll('.rich-messages-label, [class*="message"], [class*="error"]');
                    for (let el of dbErrorElements) {
                        const text = el.textContent.trim();
                        if (text.includes('dao.sgbd.error') || text.includes('codeDefault')) {
                            return {
                                type: 'system_error',
                                message: 'Sistema PJE TJRJ fora do ar (erro de banco de dados: ' + text + ')'
                            };
                        }
                    }

                    // Verificar erro de credenciais
                    const errorElements = document.querySelectorAll('.error, .erro, .alert-danger, [class*="error"]');
                    for (let el of errorElements) {
                        const text = el.textContent.trim();
                        if (text.includes('incorret') || text.includes('inválid')) {
                            return {
                                type: 'auth_error',
                                message: text
                            };
                        }
                    }

                    return null;
                }
            """)

            if error_info:
                if error_info.get('type') == 'system_error':
                    print(f"[TJRJ PJE] ✗ {error_info['message']}")
                    raise HTTPException(
                        status_code=503,
                        detail=f"Portal PJE TJRJ indisponível: {error_info['message']}"
                    )
                elif error_info.get('type') == 'auth_error':
                    print(f"[TJRJ PJE] ✗ Erro de autenticação: {error_info['message']}")
                    raise HTTPException(
                        status_code=401,
                        detail=f"Erro no login: {error_info['message']}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[TJRJ PJE] Warning: Could not check for errors: {e}")
            pass

        print(f"[TJRJ PJE] Login successful! Current URL: {self.page.url}")

    async def navigate_to_painel_advogado(self) -> None:
        """
        Navega para o painel do advogado após o login.
        URL: https://tjrj.pje.jus.br/pje/Painel/painel_usuario/advogado.seam
        """
        assert self.page
        print(f"[TJRJ PJE] Navigating to painel advogado: {PAINEL_ADVOGADO_URL}")

        try:
            await self.page.goto(PAINEL_ADVOGADO_URL, wait_until="networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=504, detail="Painel do advogado demorou muito para carregar.")

        print(f"[TJRJ PJE] Painel loaded: {self.page.url}")
        await asyncio.sleep(2)

    async def click_consulta_processo_tab(self) -> None:
        """
        Clica na aba 'CONSULTA PROCESSO' no painel do advogado.
        """
        assert self.page
        print("[TJRJ PJE] Looking for 'CONSULTA PROCESSO' tab...")

        # Aguardar a aba aparecer
        try:
            # Tentar múltiplos seletores para a aba
            tab_clicked = False

            # Opção 1: Por texto exato
            for tab_text in ["CONSULTA PROCESSO", "Consulta Processo", "CONSULTA DE PROCESSOS"]:
                try:
                    await self.page.click(f"text={tab_text}", timeout=3000)
                    print(f"[TJRJ PJE] Clicked on tab: {tab_text}")
                    tab_clicked = True
                    break
                except:
                    continue

            # Opção 2: Por link/button que contém o texto
            if not tab_clicked:
                for tab_text in ["CONSULTA PROCESSO", "Consulta Processo"]:
                    try:
                        await self.page.click(f"a:has-text('{tab_text}'), button:has-text('{tab_text}')", timeout=3000)
                        print(f"[TJRJ PJE] Clicked on tab link: {tab_text}")
                        tab_clicked = True
                        break
                    except:
                        continue

            if not tab_clicked:
                # Debug: listar todas as abas disponíveis
                tabs_text = await self.page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a, button, [role="tab"]'));
                        return links.map(l => l.textContent.trim()).filter(t => t.length > 0).slice(0, 20);
                    }
                """)
                print(f"[TJRJ PJE] Available tabs/links: {tabs_text}")
                raise HTTPException(status_code=500, detail="Aba 'CONSULTA PROCESSO' não encontrada.")

        except PlaywrightTimeoutError:
            raise HTTPException(status_code=500, detail="Aba 'CONSULTA PROCESSO' não encontrada no painel.")

        # Aguardar o formulário de consulta carregar
        await asyncio.sleep(2)
        print("[TJRJ PJE] Consulta Processo tab loaded")

        # A aba "Consulta Processo" usa um IFRAME para carregar o formulário!
        # ID do iframe: frameConsultaProcessos
        # Src: ../../Processo/ConsultaProcesso/listView.seam?iframe=true
        print("[TJRJ PJE] Waiting for iframe #frameConsultaProcessos to load...")

        try:
            await self.page.wait_for_selector("#frameConsultaProcessos", timeout=15000, state="attached")
            print("[TJRJ PJE] ✓ Found iframe #frameConsultaProcessos")

            # Aguardar iframe carregar
            await asyncio.sleep(3)

            # Mudar contexto para o iframe
            iframe_element = await self.page.query_selector("#frameConsultaProcessos")
            if not iframe_element:
                raise HTTPException(status_code=503, detail="Iframe #frameConsultaProcessos não encontrado.")

            self.frame = await iframe_element.content_frame()
            if not self.frame:
                await asyncio.sleep(2)  # Aguardar mais
                self.frame = await iframe_element.content_frame()

            if not self.frame:
                raise HTTPException(status_code=503, detail="Não foi possível acessar o conteúdo do iframe de consulta.")

            print(f"[TJRJ PJE] Switched to iframe context! Frame URL: {self.frame.url}")

            # Aguardar o iframe carregar completamente
            await self.frame.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)

        except PlaywrightTimeoutError:
            raise HTTPException(status_code=503, detail="Iframe de consulta não carregou (timeout 15s).")

    async def search_by_nome_parte(self, nome_parte: str) -> None:
        """
        Busca processos por nome da parte no formulário de Consulta Processo.
        OBS: O formulário está dentro de um iframe (self.frame deve estar configurado)
        """
        assert self.frame
        print(f"[TJRJ PJE] Searching for parte: {nome_parte} (inside iframe)")

        # Aguardar formulário estar disponível - mais tempo para AJAX
        await asyncio.sleep(3)

        # Listar TODOS os inputs visíveis para debug (DENTRO DO IFRAME)
        all_inputs = await self.frame.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input, textarea'));
                return inputs.map(inp => ({
                    id: inp.id,
                    name: inp.name,
                    placeholder: inp.placeholder,
                    type: inp.type,
                    visible: inp.offsetParent !== null,
                    value: inp.value
                }));
            }
        """)
        visible_inputs = [inp for inp in all_inputs if inp.get('visible')]
        print(f"[TJRJ PJE] ALL inputs: {len(all_inputs)} total, {len(visible_inputs)} visible")
        print(f"[TJRJ PJE] Visible inputs: {visible_inputs[:10]}")

        # Preencher campo "Nome da Parte"
        # Tentar múltiplos seletores
        nome_filled = False
        selectors_to_try = [
            "input[id*='nomeParte' i]",
            "input[name*='nomeParte' i]",
            "input[placeholder*='Nome da Parte' i]",
            "input[placeholder*='nome' i]",
            "input[id*='nomeParteAdvogado' i]",
            "input[id*='nomeAutor' i]",
            "input[id*='parte' i]",
            # PJE geralmente usa IDs como fPP:j_id123:nomeParte
            "input[id*=':nomeParte']",
            "input[name*=':nomeParte']"
        ]

        for selector in selectors_to_try:
            try:
                # Verificar se elemento existe e está visível (NO IFRAME)
                element = await self.frame.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.fill(nome_parte)
                        print(f"[TJRJ PJE] Nome da parte filled with selector: {selector}")
                        nome_filled = True
                        break
            except Exception as e:
                print(f"[TJRJ PJE] Selector {selector} failed: {e}")
                continue

        # Se não encontrou com seletores, tentar por label
        if not nome_filled:
            try:
                filled_by_label = await self.frame.evaluate(f"""
                    (nomeParte) => {{
                        // Buscar por labels que contenham "Nome" e "Parte"
                        const labels = Array.from(document.querySelectorAll('label'));
                        for (let label of labels) {{
                            const text = label.textContent.toLowerCase();
                            if (text.includes('nome') && text.includes('parte')) {{
                                // Tentar encontrar input associado
                                let input = null;
                                if (label.htmlFor) {{
                                    input = document.getElementById(label.htmlFor);
                                }} else {{
                                    input = label.querySelector('input');
                                    if (!input) {{
                                        input = label.nextElementSibling?.querySelector('input');
                                    }}
                                }}
                                if (input && input.type !== 'hidden') {{
                                    input.value = nomeParte;
                                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                        }}
                        return false;
                    }}
                """, nome_parte)
                if filled_by_label:
                    print(f"[TJRJ PJE] Nome da parte filled by label search")
                    nome_filled = True
            except Exception as e:
                print(f"[TJRJ PJE] Label search failed: {e}")

        if not nome_filled:
            # Último recurso: salvar HTML completo DO IFRAME
            try:
                html = await self.frame.content()
                with open("/tmp/tjrj_pje_iframe_form_html.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[TJRJ PJE] Iframe HTML saved to /tmp/tjrj_pje_iframe_form_html.html ({len(html)} bytes)")
            except:
                pass

            print(f"[TJRJ PJE] ALL inputs found in iframe: {all_inputs}")
            raise HTTPException(status_code=500, detail="Campo 'Nome da Parte' não encontrado após tentativas exaustivas.")

        await asyncio.sleep(1)

        # Clicar no botão Pesquisar (NO IFRAME) - usar JavaScript como no login
        try:
            # Listar botões disponíveis no iframe para debug
            buttons_info = await self.frame.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a[onclick]'));
                    return buttons.map(btn => ({
                        tag: btn.tagName,
                        type: btn.type,
                        id: btn.id,
                        name: btn.name,
                        value: btn.value,
                        text: btn.textContent?.trim(),
                        onclick: btn.onclick ? 'has onclick' : null,
                        href: btn.href
                    })).filter(b => b.text || b.value);
                }
            """)
            print(f"[TJRJ PJE] Available buttons in iframe: {buttons_info[:15]}")

            # Usar JavaScript para clicar no botão de pesquisa
            search_clicked = await self.frame.evaluate("""
                () => {
                    // Tentar por ID/name comum do PJE
                    const commonSelectors = [
                        '#fPP\\\\:searchProcessos',  // PJE usa esse ID
                        'input[id*="searchProcessos"]',
                        'input[id*="pesquisar" i]',
                        'input[id*="buscar" i]',
                        'button[id*="pesquisar" i]'
                    ];

                    for (let selector of commonSelectors) {
                        try {
                            const btn = document.querySelector(selector);
                            if (btn && btn.offsetParent !== null) {
                                btn.click();
                                return 'selector: ' + selector;
                            }
                        } catch (e) {}
                    }

                    // Tentar por texto/value do botão
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'));
                    for (let btn of buttons) {
                        const text = (btn.textContent?.toLowerCase() || btn.value?.toLowerCase() || '');
                        if (text.includes('pesquisar') || text.includes('buscar') || text.includes('consultar')) {
                            if (btn.offsetParent !== null) {
                                btn.click();
                                return 'text: ' + text;
                            }
                        }
                    }

                    // Tentar primeiro submit button visível
                    for (let btn of buttons) {
                        if ((btn.type === 'submit' || btn.tagName === 'BUTTON') && btn.offsetParent !== null) {
                            btn.click();
                            return 'first visible submit';
                        }
                    }

                    // Submeter formulário diretamente
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                        return 'form.submit()';
                    }

                    return null;
                }
            """)

            if search_clicked:
                print(f"[TJRJ PJE] Search button clicked via JavaScript in iframe: {search_clicked}")
            else:
                raise HTTPException(status_code=500, detail="Botão 'Pesquisar' não encontrado no iframe após todas as tentativas.")

        except HTTPException:
            raise
        except Exception as e:
            print(f"[TJRJ PJE] Error clicking search button in iframe: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao clicar no botão Pesquisar: {str(e)}")

        # Aguardar resultados
        print("[TJRJ PJE] Waiting for search results...")
        await asyncio.sleep(5)  # PJE pode demorar para carregar resultados

    async def extract_process_list_from_table(self) -> List[ProcessoResumoTJRJ]:
        """
        Extrai lista de processos da tabela de resultados.
        PJE geralmente usa tabelas PrimeFaces com class 'ui-datatable' ou similar.
        OBS: A tabela está dentro do iframe (self.frame)
        """
        assert self.frame
        print("[TJRJ PJE] Extracting process list from results table (inside iframe)...")

        # Aguardar tabela carregar
        await asyncio.sleep(2)

        # Script de extração - PJE usa estrutura similar ao PJE TRF1
        extraction_script = """
        () => {
            const processes = [];

            // PJE usa tabelas com classes como 'ui-datatable', 'rich-table', etc
            const tables = document.querySelectorAll('table[id*="processo"], table.ui-datatable, table.rich-table');

            console.log(`Found ${tables.length} tables`);

            for (let table of tables) {
                const rows = table.querySelectorAll('tbody tr');
                console.log(`Table has ${rows.length} rows`);

                for (let row of rows) {
                    try {
                        // Buscar número do processo - geralmente está em link ou bold
                        const links = row.querySelectorAll('a');
                        const bolds = row.querySelectorAll('b, strong');

                        let numeroProcesso = null;
                        let linkPublico = null;

                        // Tentar extrair de link
                        for (let link of links) {
                            const text = link.textContent.trim();
                            // Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
                            const match = text.match(/\\d{7}-\\d{2}\\.\\d{4}\\.\\d\\.\\d{2}\\.\\d{4}/);
                            if (match) {
                                numeroProcesso = match[0];
                                linkPublico = link.href || null;
                                break;
                            }
                        }

                        // Se não achou em link, tentar em bold
                        if (!numeroProcesso) {
                            for (let bold of bolds) {
                                const text = bold.textContent.trim();
                                const match = text.match(/\\d{7}-\\d{2}\\.\\d{4}\\.\\d\\.\\d{2}\\.\\d{4}/);
                                if (match) {
                                    numeroProcesso = match[0];
                                    break;
                                }
                            }
                        }

                        // Se não encontrou número, pular esta linha
                        if (!numeroProcesso) continue;

                        // Extrair outras informações das células
                        const cells = row.querySelectorAll('td');

                        // DEBUG: Capturar estrutura da primeira linha
                        if (processes.length === 0) {
                            const cellsDebug = [];
                            cells.forEach((cell, idx) => {
                                cellsDebug.push({
                                    index: idx,
                                    text: cell.textContent.trim().substring(0, 200)  // Limitar a 200 chars
                                });
                            });
                            window.__DEBUG_FIRST_ROW = {
                                numCells: cells.length,
                                cells: cellsDebug
                            };
                        }
                        let classe = null;
                        let partes = [];
                        let dataDistribuicao = null;
                        let comarca = null;
                        let vara = null;

                        // PJE TJRJ: estrutura real das colunas (descoberta via debug):
                        // Cell 0: (vazio - checkboxes ou ícones)
                        // Cell 1: Número do processo (já extraído acima)
                        // Cell 2: (vazio)
                        // Cell 3: Órgão julgador (Vara/Comarca)
                        // Cell 4: Data de distribuição
                        // Cell 5: Classe judicial
                        // Cell 6, 7: Partes envolvidas (nomes das pessoas/empresas)
                        // Cell 8, 9: Cartório e último movimento

                        // Extrair classe (Cell 5)
                        if (cells.length > 5) {
                            const classeText = cells[5]?.textContent.trim();
                            if (classeText && classeText.length > 0) {
                                classe = classeText;
                            }
                        }

                        // Extrair órgão julgador (Cell 3)
                        if (cells.length > 3) {
                            const orgaoText = cells[3]?.textContent.trim();
                            if (orgaoText && orgaoText.length > 0) {
                                vara = orgaoText;
                                // Detectar comarca se tiver na string
                                if (orgaoText.toLowerCase().includes('comarca')) {
                                    comarca = orgaoText;
                                }
                            }
                        }

                        // Extrair data de distribuição (Cell 4)
                        if (cells.length > 4) {
                            const dateText = cells[4]?.textContent.trim();
                            const dateMatch = dateText.match(/\d{2}\/\d{2}\/\d{4}/);
                            if (dateMatch) {
                                dataDistribuicao = dateMatch[0];
                            }
                        }

                        // Estrutura real da tabela TJRJ PJE:
                        // Cell 6 = Polo ativo (AUTOR)
                        // Cell 7 = Polo passivo (RÉU)
                        // Cell 8 = Localização (não é parte)
                        // Cell 9 = Última movimentação (não é parte)

                        // Array para armazenar partes com tipo
                        const partesComTipo = [];

                        // Polo ativo (autor) - Cell 6
                        if (cells.length > 6) {
                            const poloAtivo = cells[6]?.textContent.trim();
                            if (poloAtivo && poloAtivo.length > 0) {
                                partesComTipo.push({tipo: 'autor', nome: poloAtivo});
                            }
                        }

                        // Polo passivo (réu) - Cell 7
                        if (cells.length > 7) {
                            const poloPassivo = cells[7]?.textContent.trim();
                            if (poloPassivo && poloPassivo.length > 0) {
                                partesComTipo.push({tipo: 'reu', nome: poloPassivo});
                            }
                        }

                        processes.push({
                            numeroProcesso: numeroProcesso,
                            classe: classe,
                            assunto: null,
                            comarca: comarca,
                            vara: vara,
                            partesRelacionadas: partesComTipo,
                            dataDistribuicao: dataDistribuicao,
                            linkPublico: linkPublico
                        });

                    } catch (e) {
                        console.error('Error parsing row:', e);
                    }
                }
            }

            console.log(`Extracted ${processes.length} processes`);
            return {
                processes: processes,
                debugFirstRow: window.__DEBUG_FIRST_ROW || null
            };
        }
        """

        try:
            result = await self.frame.evaluate(extraction_script)
            debug_row = result.get("debugFirstRow")
            process_list = result.get("processes", [])

            print(f"[TJRJ PJE] Extracted {len(process_list)} processes from table")

            if debug_row:
                import json
                print(f"[DEBUG] First row structure:")
                print(f"  Number of cells: {debug_row.get('numCells')}")
                print(f"  Cells content:")
                for cell in debug_row.get('cells', []):
                    print(f"    Cell {cell['index']}: {cell['text']}")

            processes = []
            for item in process_list:
                link = item.get("linkPublico") or f"{PJE_BASE_URL}#/processo/{item['numeroProcesso']}"

                processes.append(ProcessoResumoTJRJ(
                    numeroProcesso=item["numeroProcesso"],
                    classe=item.get("classe"),
                    assunto=item.get("assunto"),
                    comarca=item.get("comarca"),
                    vara=item.get("vara"),
                    partesRelacionadas=item.get("partesRelacionadas", []),
                    dataDistribuicao=item.get("dataDistribuicao"),
                    linkPublico=link
                ))

            return processes

        except Exception as e:
            print(f"[TJRJ PJE] Error extracting processes: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def check_for_pagination_and_extract_all(self, max_pages: Optional[int] = None) -> List[ProcessoResumoTJRJ]:
        """
        Verifica se há paginação e extrai TODOS os processos de todas as páginas (ou até max_pages).
        Para capturar os 51200 processos mencionados pelo usuário.

        Args:
            max_pages: Número máximo de páginas a extrair. Se None, extrai todas.
        """
        assert self.frame
        print(f"[TJRJ PJE] Checking for pagination (inside iframe)... max_pages={max_pages or 'ALL'}")

        all_processes = []
        page_num = 1

        while True:
            print(f"[TJRJ PJE] Extracting page {page_num}...")

            # Extrair processos da página atual
            processes = await self.extract_process_list_from_table()
            all_processes.extend(processes)

            print(f"[TJRJ PJE] Page {page_num}: extracted {len(processes)} processes (total so far: {len(all_processes)})")

            # Verificar se atingiu max_pages
            if max_pages and page_num >= max_pages:
                print(f"[TJRJ PJE] Reached max_pages limit ({max_pages}). Stopping.")
                break

            # Verificar se há próxima página (NO IFRAME)
            # RichFaces DataScroller usa Event.fire() com onclick
            # Exemplo: onclick="Event.fire(this, 'rich:datascroller:onscroll', {'page': 'next'});"
            has_next = await self.frame.evaluate("""
                () => {
                    console.log('[Pagination] Looking for next page button...');

                    // Procurar botão com onclick que tenha "page": "next"
                    const allElements = document.querySelectorAll('td[onclick], a[onclick], button[onclick]');

                    for (let elem of allElements) {
                        const onclick = elem.getAttribute('onclick') || '';

                        // Verificar se é o botão de próxima página
                        if (onclick.includes("'page': 'next'") || onclick.includes('"page": "next"')) {
                            // Verificar se não está desabilitado
                            const isDisabled = elem.classList.contains('rich-datascr-button-dsbld') ||
                                              elem.classList.contains('disabled') ||
                                              elem.hasAttribute('disabled');

                            if (!isDisabled) {
                                console.log('[Pagination] Found next button, clicking...');
                                elem.click();
                                return true;
                            } else {
                                console.log('[Pagination] Next button is disabled');
                                return false;
                            }
                        }
                    }

                    // Fallback: procurar botão "»" ou "fastforward"
                    for (let elem of allElements) {
                        const onclick = elem.getAttribute('onclick') || '';
                        const text = elem.textContent?.trim() || '';

                        if ((onclick.includes("'page': 'fastforward'") || text === '»') &&
                            !elem.classList.contains('rich-datascr-button-dsbld')) {
                            console.log('[Pagination] Found fastforward button, clicking...');
                            elem.click();
                            return true;
                        }
                    }

                    console.log('[Pagination] No next page button found');
                    return false;
                }
            """)

            if not has_next:
                print(f"[TJRJ PJE] No more pages. Total processes extracted: {len(all_processes)}")
                break

            # Aguardar próxima página carregar - RichFaces usa AJAX
            print(f"[TJRJ PJE] Waiting for page {page_num + 1} to load...")
            await asyncio.sleep(4)  # RichFaces pode demorar

            # Aguardar a tabela recarregar
            try:
                await self.frame.wait_for_selector('table[id*="processosTable"]', timeout=10000, state="attached")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[TJRJ PJE] Warning: table reload timeout on page {page_num + 1}: {e}")

            page_num += 1

            # Limite de segurança para não ficar em loop infinito
            # 51200 processos / 20 por página = 2560 páginas
            if page_num > 3000:
                print(f"[TJRJ PJE] Reached safety limit of 3000 pages. Stopping.")
                break

        print(f"[TJRJ PJE] ✅ Pagination complete! Total: {len(all_processes)} processes from {page_num} pages")
        return all_processes

    async def click_process_and_extract_details(self, numero_processo: str) -> ProcessoTJRJ:
        """
        Clica em um processo específico na listagem (DENTRO DO IFRAME),
        aceita o alert de confirmação, e extrai TODOS os detalhes.
        """
        assert self.frame
        print(f"[TJRJ PJE] Clicking on process {numero_processo} in iframe...")

        # Setup para lidar com o dialog/alert na página principal (não no iframe)
        # O alert aparece na página principal, não no iframe
        dialog_handled = False
        dialog_message = None

        async def handle_dialog(dialog):
            nonlocal dialog_handled, dialog_message
            dialog_message = dialog.message
            print(f"[TJRJ PJE] ⚠️  Dialog appeared: {dialog.message[:100]}...")
            try:
                await dialog.accept()  # Clica em OK
                dialog_handled = True
                print("[TJRJ PJE] ✓ Dialog accepted")
            except Exception as e:
                print(f"[TJRJ PJE] ⚠️  Could not accept dialog (may already be handled): {e}")
                dialog_handled = True

        # Registrar handler na página principal (self.page, não self.frame)
        self.page.on("dialog", handle_dialog)

        # Clicar no link do processo DENTRO DO IFRAME
        try:
            # Primeiro tentar encontrar o link no iframe
            link_found = await self.frame.evaluate(f"""
                (numeroProcesso) => {{
                    console.log('[Click] Looking for process link:', numeroProcesso);

                    // Buscar todos os links no iframe
                    const links = Array.from(document.querySelectorAll('a'));

                    for (let link of links) {{
                        const text = link.textContent.trim();
                        if (text === numeroProcesso || text.includes(numeroProcesso)) {{
                            console.log('[Click] Found link:', link.href || link.onclick);
                            link.click();
                            return true;
                        }}
                    }}

                    return false;
                }}
            """, numero_processo)

            if not link_found:
                raise HTTPException(status_code=500, detail=f"Link do processo {numero_processo} não encontrado no iframe")

            print(f"[TJRJ PJE] ✓ Clicked on process link in iframe")

        except HTTPException:
            raise
        except Exception as e:
            print(f"[TJRJ PJE] Error clicking process link: {e}")
            raise HTTPException(status_code=500, detail=f"Erro ao clicar no processo: {str(e)}")

        # Aguardar dialog aparecer
        await asyncio.sleep(2)

        if dialog_handled:
            print(f"[TJRJ PJE] ✓ Dialog handled: '{dialog_message[:50]}...'")
        else:
            print("[TJRJ PJE] ⚠️  No dialog appeared (may not be needed)")

        # Aguardar um pouco mais para a nova página/aba carregar
        await asyncio.sleep(3)

        # Verificar se abriu nova aba
        pages = self.context.pages
        detail_page = None

        if len(pages) > 1:
            print(f"[TJRJ PJE] New tab detected! Total pages: {len(pages)}")
            # Última aba é geralmente a nova
            detail_page = pages[-1]
            await detail_page.wait_for_load_state("domcontentloaded", timeout=30000)
            print(f"[TJRJ PJE] Detail page URL: {detail_page.url}")
        else:
            # Pode ter navegado no mesmo iframe ou página
            print(f"[TJRJ PJE] No new tab, checking if iframe navigated...")
            # Usar o frame atual
            detail_page = self.page

        # Extrair TODOS os detalhes do processo da página/aba de detalhes
        return await self._extract_all_process_details(numero_processo, detail_page)

    async def _extract_all_process_details(self, numero_processo: str, detail_page: Page) -> ProcessoTJRJ:
        """
        Extrai ABSOLUTAMENTE TODOS os detalhes disponíveis do processo:
        - Dados básicos (classe, assunto, comarca, vara, juiz, valor da causa)
        - Partes (autor, réu, advogados)
        - Movimentações (todas)
        - Audiências
        - Publicações/Intimações
        - Documentos/Anexos
        """
        print(f"[TJRJ PJE] Extracting ALL details for process {numero_processo}...")

        # Aguardar página carregar completamente
        await asyncio.sleep(3)

        # Aguardar elementos principais carregarem
        try:
            await detail_page.wait_for_load_state("networkidle", timeout=15000)
        except:
            print("[TJRJ PJE] Warning: networkidle timeout, continuing anyway")

        await asyncio.sleep(2)

        # Save HTML for debugging
        try:
            detail_html = await detail_page.content()
            with open("/tmp/tjrj_pje_detail.html", "w", encoding="utf-8") as f:
                f.write(detail_html)
            print(f"[TJRJ PJE] Saved detail HTML ({len(detail_html)} bytes)")
        except Exception as e:
            print(f"[TJRJ PJE] Error saving debug HTML: {e}")

        # Script de extração baseado na estrutura real do PJE TJRJ
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
                documentos: [],
                partes: []
            };

            // MOVIMENTOS E DOCUMENTOS - Estrutura TimeLine do PJE
            // Buscar dentro de: <div id="divTimeLine:eventosTimeLineElement">
            const timelineDiv = document.querySelector('#divTimeLine\\\\:eventosTimeLineElement, div[id*="eventosTimeLineElement"], div[id*="TimeLine"]');

            if (timelineDiv) {
                console.log('[Extract] Found timeline div');

                // Buscar todas as datas principais
                const dataElements = timelineDiv.querySelectorAll('.media.data span.text-muted');
                let currentDate = null;

                // Buscar todos os movimentos
                const movimentoDivs = timelineDiv.querySelectorAll('.media.interno');
                console.log('[Extract] Found ' + movimentoDivs.length + ' movimento divs');

                for (let movDiv of movimentoDivs) {
                    // Tentar pegar data do movimento
                    const dataMuted = movDiv.closest('.media')?.previousElementSibling?.querySelector('span.text-muted');
                    if (dataMuted && dataMuted.textContent.match(/\\d{2}\\s+\\w{3}\\s+\\d{4}/)) {
                        currentDate = dataMuted.textContent.trim();
                    }

                    // Pegar hora
                    const horaSmall = movDiv.querySelector('small.text-muted.pull-right');
                    const hora = horaSmall ? horaSmall.textContent.trim() : '';

                    // Pegar texto do movimento
                    const textoMovSpan = movDiv.querySelector('span.texto-movimento');
                    if (textoMovSpan) {
                        const textoMov = textoMovSpan.textContent.trim();

                        data.movimentos.push({
                            data: currentDate + (hora ? ' ' + hora : ''),
                            descricao: textoMov
                        });

                        console.log('[Extract] Movimento: ' + textoMov.substring(0, 50));
                    }

                    // Buscar documentos dentro deste movimento (div.anexos)
                    const anexosDiv = movDiv.querySelector('.anexos');
                    if (anexosDiv) {
                        // Buscar links diretos de documentos (formato: "241423663 - Petição Inicial")
                        const docLinks = anexosDiv.querySelectorAll('a[id*="divTimeLine"]');

                        for (let docLink of docLinks) {
                            // Pegar span com nome do documento
                            const docSpan = docLink.querySelector('span[title]');
                            if (docSpan) {
                                const docText = docSpan.textContent.trim();

                                // Extrair número e tipo do documento (formato: "241423663 - Petição Inicial")
                                const docMatch = docText.match(/(\\d+)\\s*-\\s*(.+)/);
                                if (docMatch) {
                                    const numeroDoc = docMatch[1];
                                    const nomeDoc = docMatch[2];

                                    data.documentos.push({
                                        nome: nomeDoc,
                                        tipo: nomeDoc.split('(')[0].trim(),
                                        data_juntada: currentDate,
                                        autor: null,
                                        link: docLink.href || null,
                                        numero_documento: numeroDoc
                                    });

                                    console.log('[Extract] Documento: ' + numeroDoc + ' - ' + nomeDoc);
                                }
                            }
                        }

                        // Buscar sub-documentos (dentro de ul.tree > li)
                        const subDocs = anexosDiv.querySelectorAll('ul.tree > li');
                        for (let subDoc of subDocs) {
                            const subDocLink = subDoc.querySelector('a');
                            if (subDocLink) {
                                const subDocSpan = subDocLink.querySelector('span');
                                if (subDocSpan) {
                                    const subDocText = subDocSpan.textContent.trim();
                                    const subDocMatch = subDocText.match(/(\\d+)\\s*-\\s*(.+)/);

                                    if (subDocMatch) {
                                        const numeroDoc = subDocMatch[1];
                                        const nomeDoc = subDocMatch[2];

                                        data.documentos.push({
                                            nome: nomeDoc,
                                            tipo: nomeDoc.split('(')[0].trim(),
                                            data_juntada: currentDate,
                                            autor: null,
                                            link: subDocLink.href || null,
                                            numero_documento: numeroDoc
                                        });

                                        console.log('[Extract] Sub-documento: ' + numeroDoc + ' - ' + nomeDoc);
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // DADOS BÁSICOS DO PROCESSO
            // Buscar em elementos <dt> e <dd> (definition list)
            const dts = document.querySelectorAll('dt');
            for (let dt of dts) {
                const label = dt.textContent.trim();

                // Procurar o próximo <dd> (pode não ser nextElementSibling imediatamente)
                let dd = dt.nextElementSibling;
                while (dd && dd.tagName !== 'DD') {
                    dd = dd.nextElementSibling;
                }

                const value = dd?.textContent.trim();

                if (label.includes('Classe') && !data.classe) data.classe = value;
                if (label.includes('Assunto') && !data.assunto) data.assunto = value;
                if (label.includes('Comarca') && !data.comarca) data.comarca = value;
                if (label.includes('Vara') && !data.vara) data.vara = value;
                if (label.includes('Juiz') && !data.juiz) data.juiz = value;
                if (label.includes('Valor') && label.includes('Causa') && !data.valorCausa) {
                    data.valorCausa = value;
                    console.log('[Extract] Valor da causa: ' + value);
                }
                if (label.includes('Distribuição') && !data.dataDistribuicao) data.dataDistribuicao = value;
            }

            // NÚMERO DO PROCESSO - buscar em vários lugares
            const numProc = document.querySelector('h3, h4, .processo-numero, [class*="numero-processo"]');
            if (numProc) {
                const numMatch = numProc.textContent.match(/(\\d{7}-\\d{2}\\.\\d{4}\\.\\d\\.\\d{2}\\.\\d{4})/);
                if (numMatch) data.numeroProcesso = numMatch[1];
            }

            // PARTES E ADVOGADOS - estrutura específica do PJE TJRJ
            // Polo Ativo: <div id="poloAtivo">
            const poloAtivoDiv = document.querySelector('#poloAtivo, div[id*="poloAtivo"]');
            if (poloAtivoDiv) {
                // Buscar todas as spans (tanto as de td > span > span quanto as de ul.tree li)
                const allSpans = poloAtivoDiv.querySelectorAll('span');
                for (let span of allSpans) {
                    const text = span.textContent.trim();

                    // Buscar AUTOR: "SHEILA CHOR - CPF: 596.259.887-34 (AUTOR)"
                    if (text.includes('AUTOR') && !text.includes('ADVOGADO')) {
                        const parteMatch = text.match(/^([^-]+)/);
                        if (parteMatch) {
                            const nomeParte = parteMatch[1].trim();
                            if (!data.autor) {
                                data.autor = nomeParte;
                                data.partes.push({ tipo: 'POLO ATIVO - AUTOR', nome: text });
                                console.log('[Extract] Autor encontrado: ' + nomeParte);
                            }
                        }
                    }

                    // Buscar ADVOGADO: "ALINE HADID JAGER - OAB RJ118729 - CPF: 085.735.157-59 (ADVOGADO)"
                    if (text.includes('ADVOGADO')) {
                        const advMatch = text.match(/^([^-]+)/);
                        if (advMatch) {
                            const nomeAdv = advMatch[1].trim();
                            if (nomeAdv && nomeAdv.length > 3 && !data.advogados.includes(nomeAdv)) {
                                data.advogados.push(nomeAdv);
                                console.log('[Extract] Advogado encontrado: ' + nomeAdv);
                            }
                        }
                    }
                }
            }

            // Polo Passivo: <div id="poloPassivo">
            const poloPassivoDiv = document.querySelector('#poloPassivo, div[id*="poloPassivo"]');
            if (poloPassivoDiv) {
                const poloPassivoSpans = poloPassivoDiv.querySelectorAll('td > span > span');
                for (let span of poloPassivoSpans) {
                    const text = span.textContent.trim();

                    // Buscar RÉU: "CLARO S.A.  - CNPJ: 40.432.544/0057-00 (RÉU)"
                    if (text.includes('RÉU') || text.includes('REU')) {
                        const parteMatch = text.match(/^([^-]+)/);
                        if (parteMatch) {
                            const nomeParte = parteMatch[1].trim();
                            data.reu = nomeParte;
                            data.partes.push({ tipo: 'POLO PASSIVO - RÉU', nome: text });
                            console.log('[Extract] Réu encontrado: ' + nomeParte);
                        }
                    }
                }
            }

            console.log('[Extract] FINAL - Movimentos: ' + data.movimentos.length +
                       ', Documentos: ' + data.documentos.length +
                       ', Partes: ' + data.partes.length);

            return data;
        }
        """

        try:
            data = await detail_page.evaluate(extraction_script)

            print(f"[TJRJ PJE] Extracted: {len(data.get('movimentos', []))} movimentos, "
                  f"{len(data.get('audiencias', []))} audiências, "
                  f"{len(data.get('publicacoes', []))} publicações, "
                  f"{len(data.get('documentos', []))} documentos")

            # Converter para modelos Pydantic
            audiencias = [Audiencia(**aud) for aud in data.get("audiencias", [])]
            publicacoes = [Publicacao(**pub) for pub in data.get("publicacoes", [])]
            documentos = [Documento(**doc) for doc in data.get("documentos", [])]
            movimentos = [{"data": mov["data"], "descricao": mov["descricao"]}
                         for mov in data.get("movimentos", [])]

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
                linkPublico=detail_page.url,
                movimentos=movimentos,
                audiencias=audiencias,
                publicacoes=publicacoes,
                documentos=documentos,
                partes=data.get("partes", [])
            )

        except Exception as e:
            print(f"[TJRJ PJE] Error extracting details: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao extrair detalhes do processo: {str(e)}"
            )


# Funções públicas para usar na API

async def fetch_tjrj_pje_authenticated_process_from_page(
    cpf: str,
    senha: str,
    nome_parte: str,
    target_page: int = 3,
    process_index: int = 0
) -> ProcessoTJRJ:
    """
    Função de TESTE: Busca processos por nome, navega até uma página específica,
    e extrai detalhes do processo no índice especificado.
    """
    settings = get_settings()

    async with TJRJPJEAuthenticatedFetcher(settings, cpf, senha) as fetcher:
        # 1. Login
        await fetcher.login()

        # 2. Navegar para painel
        await fetcher.navigate_to_painel_advogado()

        # 3. Ir para consulta
        await fetcher.click_consulta_processo_tab()

        # 4. Buscar por nome da parte
        await fetcher.search_by_nome_parte(nome_parte)

        # 5. Navegar até a página desejada (se > 1)
        current_page = 1
        while current_page < target_page:
            print(f"[TJRJ PJE TEST] Navigating from page {current_page} to {current_page + 1}...")

            # Clicar no botão de próxima página
            has_next = await fetcher.frame.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('td[onclick], a[onclick]');
                    for (let elem of allElements) {
                        const onclick = elem.getAttribute('onclick') || '';
                        if (onclick.includes("'page': 'next'") || onclick.includes('"page": "next"')) {
                            const isDisabled = elem.classList.contains('rich-datascr-button-dsbld');
                            if (!isDisabled) {
                                elem.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """)

            if not has_next:
                raise HTTPException(status_code=404, detail=f"Não foi possível navegar para a página {current_page + 1}")

            # Aguardar página carregar
            await asyncio.sleep(5)
            current_page += 1

        print(f"[TJRJ PJE TEST] ✓ Reached page {target_page}")

        # 6. Extrair processos da página atual
        processes = await fetcher.extract_process_list_from_table()

        if process_index >= len(processes):
            raise HTTPException(
                status_code=404,
                detail=f"Processo índice {process_index} não encontrado (página tem {len(processes)} processos)"
            )

        target_process = processes[process_index]
        print(f"[TJRJ PJE TEST] Target process: {target_process.numeroProcesso}")

        # 7. Clicar no processo e extrair detalhes
        return await fetcher.click_process_and_extract_details(target_process.numeroProcesso)


async def fetch_tjrj_pje_authenticated_process_detail_single(
    cpf: str,
    senha: str,
    numero_processo: str
) -> ProcessoTJRJ:
    """
    Busca detalhes completos de UM processo específico no PJE TJRJ autenticado.
    Faz login, navega até o processo, e extrai todos os detalhes.
    """
    settings = get_settings()

    async with TJRJPJEAuthenticatedFetcher(settings, cpf, senha) as fetcher:
        # 1. Login
        await fetcher.login()

        # 2. Navegar para painel
        await fetcher.navigate_to_painel_advogado()

        # 3. Ir para consulta
        await fetcher.click_consulta_processo_tab()

        # 4. Buscar pelo número do processo para chegar na lista
        # Extrair primeiros dígitos do número para buscar
        # Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
        # Vamos buscar por parte genérica para encontrar o processo
        await fetcher.search_by_nome_parte("*")  # Busca genérica ou extrair nome do processo

        # 5. Clicar no processo e extrair detalhes
        return await fetcher.click_process_and_extract_details(numero_processo)


async def fetch_tjrj_pje_authenticated_process_list(
    cpf: str,
    senha: str,
    nome_parte: str,
    max_pages: Optional[int] = None,
    extract_details: bool = False,
    max_details: Optional[int] = None
) -> TJRJProcessoListResponse:
    """
    Busca processos no sistema PJE TJRJ autenticado.
    Faz login, navega para o painel do advogado, busca por nome da parte,
    e retorna os processos encontrados (com paginação).

    Args:
        cpf: CPF para login
        senha: Senha para login
        nome_parte: Nome da parte para buscar
        max_pages: Número máximo de páginas a extrair. Se None, extrai todas.
        extract_details: Se True, extrai detalhes completos de cada processo
        max_details: Número máximo de processos para extrair detalhes. Se None, extrai de todos.
    """
    settings = get_settings()

    async with TJRJPJEAuthenticatedFetcher(settings, cpf, senha) as fetcher:
        # 1. Login
        await fetcher.login()

        # 2. Navegar para painel do advogado
        await fetcher.navigate_to_painel_advogado()

        # 3. Clicar na aba "CONSULTA PROCESSO"
        await fetcher.click_consulta_processo_tab()

        # 4. Buscar por nome da parte
        await fetcher.search_by_nome_parte(nome_parte)

        # 5. Extrair processos (até max_pages)
        processos = await fetcher.check_for_pagination_and_extract_all(max_pages=max_pages)

        # 6. Se extract_details=True, extrair detalhes completos
        if extract_details and len(processos) > 0:
            limit = max_details if max_details is not None else len(processos)
            print(f"[TJRJ PJE] Extraindo detalhes de {limit} processo(s)...")

            # IMPORTANTE: Voltar para a primeira página antes de extrair detalhes
            # porque após a paginação, o browser pode estar em qualquer página
            print("[TJRJ PJE] Voltando para a primeira página antes de extrair detalhes...")
            try:
                first_page_btn = await fetcher.iframe_context.query_selector("a.rich-datascr-button[onclick*='first']")
                if first_page_btn:
                    await first_page_btn.click()
                    await asyncio.sleep(2)
                    print("[TJRJ PJE] ✓ Voltou para a primeira página")
            except Exception as e:
                print(f"[TJRJ PJE] ⚠️  Não foi possível voltar para primeira página: {e}")

            processos_com_detalhes = []
            for idx, processo_resumo in enumerate(processos[:limit]):
                try:
                    print(f"[TJRJ PJE] Extraindo detalhes do processo {idx+1}/{limit}: {processo_resumo.numeroProcesso}")

                    # Chamar função que clica no processo e extrai detalhes
                    processo_detalhe = await fetcher.click_process_and_extract_details(processo_resumo.numeroProcesso)

                    if processo_detalhe:
                        # Adicionar como dict para preservar TODOS os campos (movimentos, documentos, etc.)
                        processos_com_detalhes.append(processo_detalhe.model_dump())
                    else:
                        # Se falhou, manter pelo menos o resumo (como dict)
                        processos_com_detalhes.append(processo_resumo.model_dump())

                    # Aguardar um pouco entre extrações para não sobrecarregar
                    await asyncio.sleep(2)

                except Exception as e:
                    print(f"[TJRJ PJE] Erro ao extrair detalhes de {processo_resumo.numeroProcesso}: {e}")
                    # Manter pelo menos o resumo (como dict)
                    processos_com_detalhes.append(processo_resumo.model_dump())

            # Adicionar os processos restantes (sem detalhes) como resumos (como dicts)
            processos_com_detalhes.extend([p.model_dump() for p in processos[limit:]])

            # Substituir lista original pelos processos com detalhes
            processos = processos_com_detalhes
        else:
            # Se não está extraindo detalhes, converter ProcessoResumoTJRJ para dicts
            processos = [p.model_dump() for p in processos]

        return TJRJProcessoListResponse(
            total_processos=len(processos),
            processos=processos
        )


async def fetch_tjrj_pje_authenticated_process_detail(
    cpf: str,
    senha: str,
    numero_processo: str
) -> ProcessoTJRJ:
    """
    Busca detalhes completos de um processo específico no PJE TJRJ autenticado.
    """
    settings = get_settings()

    async with TJRJPJEAuthenticatedFetcher(settings, cpf, senha) as fetcher:
        # 1. Login
        await fetcher.login()

        # 2. Navegar para painel
        await fetcher.navigate_to_painel_advogado()

        # 3. Ir para consulta
        await fetcher.click_consulta_processo_tab()

        # 4. Buscar pelo número do processo (para chegar na lista)
        # Extrair nome do processo se possível, senão buscar genérico
        await fetcher.search_by_nome_parte("*")  # Busca genérica

        # 5. Clicar no processo e extrair detalhes
        return await fetcher.click_process_and_extract_details(numero_processo)
