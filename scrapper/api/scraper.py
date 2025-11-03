from __future__ import annotations

import asyncio
import contextlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from fastapi import HTTPException
import httpx
from bs4 import BeautifulSoup
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
    ProcessoResumoTJSP,
    ProcessoTJSP,
    TJSPProcessoListQuery,
    TJSPProcessoListResponse,
    TJSPProcessoQuery,
)

SEARCH_PARAM_MAP = {
    "numero_processo": "NUMPROC",
    "nome_parte": "NMPARTE",
    "documento_parte": "DOCPARTE",
    "nome_advogado": "NMADVOGADO",
    "numero_oab": "NUMOAB",
    "numero_precatoria": "PRECATORIA",
    "numero_documento_delegacia": "DOCDELEG",
    "numero_cda": "NUMCDA",
}

LISTING_EXTRACTION_SCRIPT = r"""
() => {
    const norm = (value) => {
        if (value === null || value === undefined) {
            return null;
        }
        const text = typeof value === 'string' ? value : String(value);
        const trimmed = text.replace(/\s+/g, ' ').trim();
        return trimmed.length ? trimmed : null;
    };

    const collectLines = (element) => {
        if (!element) return [];
        return element.innerText
            .split('\\n')
            .map((line) => line.replace(/\s+/g, ' ').trim())
            .filter(Boolean);
    };

    const processes = Array.from(document.querySelectorAll('div.row.unj-ai-c.home__lista-de-processos')).map((row) => {
        const anchor = row.querySelector('.nuProcesso a');
        return {
            numeroProcesso: norm(anchor ? anchor.textContent : null),
            href: anchor ? anchor.getAttribute('href') : null,
            tipoParticipacao: norm(row.querySelector('.tipoDeParticipacao')?.textContent || null),
            partesRelacionadas: collectLines(row.querySelector('.nomeParte')),
            classe: norm(row.querySelector('.classeProcesso')?.innerText || null),
            assunto: norm(row.querySelector('.assuntoPrincipalProcesso')?.innerText || null),
            distribuicao: norm(row.querySelector('.dataLocalDistribuicaoProcesso')?.innerText || null),
        };
    });

    const totalText = document.querySelector('#contadorDeProcessos')?.textContent || null;
    const showingText = document.querySelector('#quantidadeProcessosNaPagina')?.textContent || null;
    const pagination = Array.from(document.querySelectorAll('a.paginacao')).map((anchor) => ({
        text: norm(anchor.textContent),
        href: anchor.getAttribute('href') || null,
    }));

    return { processes, totalText, showingText, pagination };
}
"""

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


class TJSPFetcher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self) -> "TJSPFetcher":
        playwright = await async_playwright().start()
        browser_launcher = getattr(playwright, self.settings.playwright_browser)
        launch_kwargs: Dict[str, Any] = {"headless": self.settings.headless}
        if self.settings.slow_mo_ms:
            launch_kwargs["slow_mo"] = self.settings.slow_mo_ms
        self.browser = await browser_launcher.launch(**launch_kwargs)
        self.context = await self.browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )
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
        assert self.page
        response = await self.page.goto(str(self.settings.base_url))
        if not response or response.status >= 500:
            raise HTTPException(status_code=503, detail="Portal TJSP indisponível no momento.")
        await self.ensure_page_is_ready()

    async def ensure_page_is_ready(self) -> None:
        assert self.page
        for attempt in range(3):
            try:
                await self.page.wait_for_load_state("domcontentloaded")
                with contextlib.suppress(PlaywrightTimeoutError):
                    await self.page.wait_for_load_state("networkidle", timeout=5_000)
                snapshot = await self.page.content()
                if "Service Unavailable" in snapshot:
                    raise HTTPException(status_code=503, detail="Portal TJSP retornou 'Service Unavailable'.")
                return
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                if "Execution context was destroyed" in str(exc) and attempt < 2:
                    await asyncio.sleep(1)
                    continue
                if isinstance(exc, PlaywrightTimeoutError) and attempt < 2:
                    continue
                raise
        raise HTTPException(status_code=504, detail="Portal TJSP não estabilizou a tempo.")

    async def submit_query(self, query: TJSPProcessoQuery) -> None:
        assert self.page
        search_key, search_value = self._resolve_search_parameter(query)
        await self._select_search_mode(search_key)
        await self._fill_inputs(search_key, search_value, query)
        submit_locator = self.page.locator("#botaoConsultarProcessos, input[type=submit][value='Consultar']")
        if await submit_locator.count() == 0:
            raise HTTPException(status_code=500, detail="Não foi possível localizar o botão de consulta.")
        await submit_locator.first.click(no_wait_after=True)
        with contextlib.suppress(PlaywrightTimeoutError):
            await self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
        with contextlib.suppress(PlaywrightTimeoutError):
            await self.page.wait_for_url("**/show.do**", timeout=15_000)
        await self.ensure_page_is_ready()
        await self._open_process_details_if_needed()

    async def submit_query_for_listing(self, query: TJSPProcessoQuery) -> None:
        assert self.page
        search_key, search_value = self._resolve_search_parameter(query)

        # Build URL with parameters instead of using form submission for better control
        base_url = "https://esaj.tjsp.jus.br/cpopg/search.do"
        params = {
            "conversationId": "",
            "cbPesquisa": search_key,
            "dadosConsulta.valorConsulta": search_value,
            "cdForo": query.foro if query.foro else "-1",
        }

        # Add nome_completo parameter if requested and searching by name
        if query.nome_completo and search_key == "NMPARTE":
            params["chNmCompleto"] = "true"

        # Build query string
        from urllib.parse import urlencode
        query_string = urlencode(params)
        full_url = f"{base_url}?{query_string}"

        # Navigate directly to the search results
        await self.page.goto(full_url, wait_until="domcontentloaded")
        await self.ensure_page_is_ready()

    async def go_to_listing_page(self, page_number: int) -> bool:
        assert self.page
        selector = f"a.paginacao[href*='paginaConsulta={page_number}']"
        locator = self.page.locator(selector)
        if await locator.count() == 0:
            return False
        async with self.page.expect_navigation(wait_until="domcontentloaded"):
            await locator.first.click()
        await self.ensure_page_is_ready()
        return True

    def _resolve_search_parameter(self, query: TJSPProcessoQuery) -> tuple[str, str]:
        for field, code in SEARCH_PARAM_MAP.items():
            value = getattr(query, field)
            if value:
                return code, value
        raise HTTPException(status_code=400, detail="Informe pelo menos um parâmetro de busca suportado.")

    async def _select_search_mode(self, code: str) -> None:
        assert self.page
        select_locator = self.page.locator("select[name='cbPesquisa']")
        if await select_locator.count() == 0:
            select_locator = self.page.get_by_label("Consultar por", exact=False)
        if await select_locator.count() == 0:
            raise HTTPException(status_code=500, detail="Campo 'Consultar por' não encontrado.")
        await select_locator.first.select_option(value=code)

    async def _fill_inputs(self, code: str, raw_value: str, query: TJSPProcessoQuery) -> None:
        assert self.page
        if code == "NUMPROC":
            digits = "".join(ch for ch in raw_value if ch.isdigit()).zfill(20)
            primeiro = digits[:13]
            ultimo = digits[-4:]
            await self._fill_first_input(
                [
                    "#numeroDigitoAnoUnificado",
                    "input[name='numeroDigitoAnoUnificado']",
                    "input[aria-label*='treze primeiros']",
                    "input[title*='treze primeiros']",
                ],
                primeiro,
            )
            await self._fill_first_input(
                [
                    "#foroNumeroUnificado",
                    "input[name='foroNumeroUnificado']",
                    "input[aria-label*='quatro últimos']",
                    "input[title*='quatro últimos']",
                ],
                ultimo,
            )
            formatted_compact = f"{digits[:13]}.{digits[13]}.{digits[14:16]}.{digits[16:]}"
            formatted_display = f"{digits[:7]}-{digits[7:9]}.{digits[9:13]}.{digits[13]}.{digits[14:16]}.{digits[16:]}"
            await self.page.evaluate(
                """({ digits, formattedCompact, formattedDisplay }) => {
                    const nodes = Array.from(
                        document.querySelectorAll('input[name="dadosConsulta.valorConsultaNuUnificado"]')
                    );
                    if (nodes.length > 0) {
                        nodes[0].value = formattedCompact;
                    }
                    const display = document.querySelector('#nuProcessoUnificadoFormatado');
                    if (display) {
                        display.value = formattedDisplay;
                    }
                    const hiddenRaw = document.querySelector('#nuProcessoUnificado');
                    if (hiddenRaw) {
                        hiddenRaw.value = digits;
                    }
                }""",
                {"digits": digits, "formattedCompact": formatted_compact, "formattedDisplay": formatted_display},
            )
        else:
            await self._fill_first_input(
                [
                    "input[name='dadosConsulta.valorConsulta']",
                    "input[name='dadosConsulta.valorConsultaNuUnificado']",
                    "input[aria-label*='Informe']",
                    "input[aria-label*='Digite']",
                ],
                raw_value,
            )

        if query.foro and query.foro.strip():
            foro_value = query.foro.strip().zfill(4)
            with contextlib.suppress(Exception):
                await self.page.fill("input[name='foroNumeroUnificado']", foro_value)
                await self.page.evaluate(
                    """(value) => {
                        const combo = document.querySelector('#comboForo');
                        if (combo) combo.value = value;
                    }""",
                    foro_value,
                )

        # Handle nome completo checkbox (must be AFTER filling the input)
        if query.nome_completo and query.nome_parte and code == "NMPARTE":
            with contextlib.suppress(Exception):
                # Remove disabled attribute and click the label
                await self.page.evaluate("""
                    () => {
                        const checkbox = document.querySelector("input[name='chNmCompleto']");
                        if (checkbox) {
                            checkbox.removeAttribute('disabled');
                            checkbox.disabled = false;
                        }
                        const label = document.querySelector("label:has(input[name='chNmCompleto'])");
                        if (label) {
                            label.click();
                        }
                    }
                """)
                await self.page.wait_for_timeout(500)  # Wait for any JS to react

    async def _fill_first_input(self, selectors: List[str], value: str) -> None:
        assert self.page
        for selector in selectors:
            locator = self.page.locator(selector)
            count = await locator.count()
            if count == 0:
                continue
            for index in range(count):
                candidate = locator.nth(index)
                try:
                    if await candidate.is_disabled():
                        continue
                except PlaywrightError:
                    continue
                try:
                    await candidate.fill(value)
                    return
                except PlaywrightError:
                    continue
        # Fallback: use JavaScript to try fill by aria-label substring
        success = await self.page.evaluate(
            """(value) => {
                const matchers = [
                    'treze primeiros',
                    'quatro últimos',
                    'Informe',
                    'Digite',
                ];
                for (const input of Array.from(document.querySelectorAll('input'))) {
                    const aria = (input.getAttribute('aria-label') || '').toLowerCase();
                    const title = (input.getAttribute('title') || '').toLowerCase();
                    if (matchers.some(m => aria.includes(m) || title.includes(m))) {
                        input.focus();
                        input.value = value;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                    }
                }
                return false;
            }""",
            value,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Não foi possível preencher o formulário de busca.")

    async def _open_process_details_if_needed(self) -> None:
        assert self.page
        url = self.page.url
        if "show.do" in url:
            return
        if "search.do" in url:
            # Attempt to open the first result
            link = self.page.locator("a[href*='show.do']").first
            if await link.count() == 0:
                alert_text = await self.page.evaluate(
                    """() => {
                        const alert = document.querySelector('.alert, .alert-danger, .alert-warning');
                        if (alert) {
                            return alert.textContent?.trim().replace(/\\s+/g, ' ') || null;
                        }
                        return null;
                    }"""
                )
                if alert_text:
                    raise HTTPException(status_code=404, detail=alert_text)
                raise HTTPException(status_code=404, detail="Processo não encontrado na listagem.")
            await asyncio.gather(
                link.click(),
                self.page.wait_for_load_state("networkidle"),
            )
            await self.ensure_page_is_ready()
            return
        raise HTTPException(status_code=500, detail="Página inesperada após consulta.")

    async def extract_process_data(self) -> ProcessoTJSP:
        assert self.page
        await self._expand_details_sections()
        payload = await self.page.evaluate(_EXTRACT_SCRIPT)
        if not payload or not payload.get("numeroProcesso"):
            raise HTTPException(status_code=404, detail="Detalhes do processo não encontrados.")

        movimentos_raw = payload.get("movimentos") or []
        movimentos = _parse_movimentos(movimentos_raw)
        inicio, ultima_atualizacao = _movimentacoes_extremos(movimentos)
        requerente, advogado = _parse_partes(payload.get("partes") or [])
        data_audiencia = _parse_data_audiencia(payload.get("audiencias") or [])

        valor_causa = payload.get("valorCausa")
        if valor_causa:
            valor_causa = valor_causa.replace("r$", "R$").strip()

        tipo_juizo = _infer_tipo_juizo(payload)
        situacao = _determine_situacao(movimentos)

        return ProcessoTJSP(
            uf="SP",
            numeroProcesso=payload.get("numeroProcesso"),
            valorCausa=valor_causa,
            tipoJuizo=tipo_juizo,
            classe=payload.get("classe"),
            assunto=payload.get("assunto"),
            foro=payload.get("foro"),
            vara=payload.get("vara"),
            juiz=payload.get("juiz"),
            requerente=requerente,
            advogadoConsumidor=advogado,
            dataAudiencia=data_audiencia,
            situacaoProcessual=situacao,
            inicio=inicio,
            ultima_atualizacao=ultima_atualizacao,
            linkPublico=payload.get("linkPublico"),
            movimentos=movimentos,
        )

    async def _expand_details_sections(self) -> None:
        assert self.page
        links = self.page.locator("a:has-text('Mais')")
        count = await links.count()
        for index in range(count):
            with contextlib.suppress(Exception):
                await links.nth(index).click()
                await self.page.wait_for_timeout(250)


async def fetch_tjsp_process(query: TJSPProcessoQuery, settings: Settings | None = None) -> ProcessoTJSP:
    settings = settings or get_settings()
    async with TJSPFetcher(settings) as fetcher:
        await fetcher.navigate_to_search()
        await fetcher.submit_query(query)
        return await fetcher.extract_process_data()


def _parse_total_from_text(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = re.findall(r"\d+", text.replace(".", ""))
    if not digits:
        return None
    try:
        return int(digits[0])
    except ValueError:
        return None


def _parse_showing_text(text: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not text:
        return None, None
    numbers = [int(value) for value in re.findall(r"\d+", text)]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    return None, None


async def _extract_listing_page(page: Page, settings: Settings, page_number: int) -> Dict[str, Any]:
    payload = await page.evaluate(LISTING_EXTRACTION_SCRIPT)
    raw_processes: List[Dict[str, Any]] = payload.get("processes") or []
    processes: List[Dict[str, Any]] = []
    for entry in raw_processes:
        numero = entry.get("numeroProcesso")
        href = entry.get("href")
        if not numero or not href:
            continue
        absolute_link = urljoin(str(settings.base_url), href)
        parsed = urlparse(absolute_link)
        params = parse_qs(parsed.query)
        processo_codigo = (params.get("processo.codigo") or [None])[0]
        foro_id = (params.get("processo.foro") or [None])[0]
        tipo_participacao = entry.get("tipoParticipacao")
        if isinstance(tipo_participacao, str):
            tipo_participacao = tipo_participacao.rstrip(": ") or None
        partes_relacionadas = entry.get("partesRelacionadas") or []
        if not isinstance(partes_relacionadas, list):
            partes_relacionadas = []

        processes.append(
            {
                "numeroProcesso": numero,
                "processoCodigo": processo_codigo,
                "foroId": foro_id,
                "linkPublico": absolute_link,
                "tipoParticipacao": tipo_participacao,
                "partesRelacionadas": partes_relacionadas,
                "classe": entry.get("classe"),
                "assunto": entry.get("assunto"),
                "distribuicao": entry.get("distribuicao"),
                "pagina": page_number,
                "contrapartesEncontradas": [],
            }
        )

    total = _parse_total_from_text(payload.get("totalText"))
    showing_range = _parse_showing_text(payload.get("showingText"))

    return {
        "processes": processes,
        "total": total,
        "showing_range": showing_range,
    }


def _extract_contra_matches(html: str, filtro_lower: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tablePartesPrincipais")
    if not table:
        return []
    matches: List[str] = []
    for row in table.select("tr"):
        tipo_node = row.select_one(".tipoDeParticipacao, .label")
        conteudo_node = row.select_one(".nomeParteEAdvogado")
        tipo_text = " ".join(tipo_node.stripped_strings) if tipo_node else ""
        conteudo_text = " ".join(conteudo_node.stripped_strings) if conteudo_node else ""
        combined = ": ".join(filter(None, [tipo_text, conteudo_text])).strip()
        if combined and filtro_lower in combined.lower():
            matches.append(combined)
    return matches


async def _apply_contra_parte_filter(
    processes: List[Dict[str, Any]],
    filtro: str,
    max_processos: Optional[int],
) -> List[Dict[str, Any]]:
    filtro_lower = filtro.lower()
    filtered: List[Dict[str, Any]] = []
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(headers=HTTP_HEADERS, timeout=timeout) as client:
        for process in processes:
            link = process.get("linkPublico")
            numero = process.get("numeroProcesso")
            if not link:
                continue
            try:
                response = await client.get(link)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"Falha ao consultar detalhes do processo {numero}: {exc}",
                ) from exc
            matches = _extract_contra_matches(response.text, filtro_lower)
            if matches:
                process["contrapartesEncontradas"] = matches
                filtered.append(process)
                if max_processos and len(filtered) >= max_processos:
                    break
    return filtered


async def fetch_tjsp_process_list(
    query: TJSPProcessoListQuery, settings: Settings | None = None
) -> TJSPProcessoListResponse:
    settings = settings or get_settings()

    base_query = TJSPProcessoQuery(
        numero_processo=query.numero_processo,
        nome_parte=query.nome_parte,
        nome_completo=query.nome_completo,
        documento_parte=query.documento_parte,
        nome_advogado=query.nome_advogado,
        numero_oab=query.numero_oab,
        numero_precatoria=query.numero_precatoria,
        numero_documento_delegacia=query.numero_documento_delegacia,
        numero_cda=query.numero_cda,
        foro=query.foro,
        uf=query.uf,
    )

    async with TJSPFetcher(settings) as fetcher:
        await fetcher.navigate_to_search()
        await fetcher.submit_query_for_listing(base_query)

        total_processos: Optional[int] = None
        all_processes: List[Dict[str, Any]] = []
        paginas_consultadas = 0
        current_page = 1
        possui_mais_paginas = False

        while True:
            page_data = await _extract_listing_page(fetcher.page, settings, current_page)
            paginas_consultadas += 1

            if total_processos is None:
                total_processos = page_data.get("total")

            all_processes.extend(page_data.get("processes") or [])

            next_page_locator = fetcher.page.locator(
                f"a.paginacao[href*='paginaConsulta={current_page + 1}']"
            )
            next_page_exists = await next_page_locator.count() > 0

            if query.contra_parte is None and query.max_processos and len(all_processes) >= query.max_processos:
                all_processes = all_processes[: query.max_processos]
                possui_mais_paginas = next_page_exists
                break

            if current_page >= query.max_paginas:
                possui_mais_paginas = next_page_exists
                break

            if not next_page_exists:
                possui_mais_paginas = False
                break

            current_page += 1
            navigated = await fetcher.go_to_listing_page(current_page)
            if not navigated:
                possui_mais_paginas = False
                break

        final_processes = all_processes

        if query.contra_parte:
            final_processes = await _apply_contra_parte_filter(
                all_processes,
                query.contra_parte,
                query.max_processos,
            )
            if query.max_processos:
                final_processes = final_processes[: query.max_processos]

        processos_model = [ProcessoResumoTJSP(**item) for item in final_processes]

        return TJSPProcessoListResponse(
            total_processos=total_processos,
            paginas_consultadas=paginas_consultadas,
            possui_mais_paginas=possui_mais_paginas,
            filtro_contra_parte=query.contra_parte,
            processos=processos_model,
        )


_EXTRACT_SCRIPT = r"""
() => {
    const norm = (text) => (text ? text.trim().replace(/\s+/g, ' ') : null);
    const textBySelector = (selector) => {
        const node = document.querySelector(selector);
        if (!node) return null;
        return norm(node.textContent) || norm(node.getAttribute('title'));
    };

    const numeroProcesso = (() => {
        const element = document.querySelector('#numeroProcesso, .numeroProcesso, .numero-proc, .nuProcesso');
        if (element) return norm(element.textContent);
        const match = document.body.innerText.match(/\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}/);
        return match ? match[0] : null;
    })();

    const partes = (() => {
        const table = document.querySelector('#tablePartesPrincipais');
        const result = [];
        if (!table) return result;
        table.querySelectorAll('tr').forEach((tr) => {
            const tipo = norm(tr.querySelector('.tipoDeParticipacao')?.textContent || tr.querySelector('.label')?.textContent);
            const conteudo = norm(tr.querySelector('.nomeParteEAdvogado')?.textContent || '');
            if (tipo && conteudo) {
                result.push({ tipo, conteudo });
            }
        });
        return result;
    })();

    const movimentos = (() => {
        const rows = [];
        const extract = (root) => {
            if (!root) return;
            root.querySelectorAll('tr.containerMovimentacao').forEach((tr) => {
                const data = norm(tr.querySelector('.dataMovimentacao')?.textContent);
                const descricao = norm(tr.querySelector('.descricaoMovimentacao')?.textContent);
                if (data && descricao) {
                    rows.push({ data, descricao });
                }
            });
        };
        extract(document.querySelector('#tabelaTodasMovimentacoes'));
        if (!rows.length) {
            extract(document.querySelector('#tabelaUltimasMovimentacoes'));
        }
        return rows;
    })();

    const audiencias = (() => {
        const table = document.querySelector('#tabelaTodasAudiencias, #tabelaAudiencias');
        const result = [];
        if (!table) return result;
        table.querySelectorAll('tr').forEach((tr) => {
            const cells = Array.from(tr.querySelectorAll('th, td')).map((cell) => norm(cell.textContent) || '');
            if (cells.some(Boolean)) {
                result.push(cells);
            }
        });
        return result;
    })();

    const distribuicao = {
        data: norm(document.querySelector('#dataHoraDistribuicaoProcesso')?.textContent),
        area: norm(document.querySelector('#areaProcesso span, #areaProcesso')?.textContent),
    };

    return {
        numeroProcesso,
        classe: textBySelector('#classeProcesso'),
        assunto: textBySelector('#assuntoProcesso'),
        foro: textBySelector('#foroProcesso'),
        vara: textBySelector('#varaProcesso'),
        juiz: textBySelector('#juizProcesso'),
        valorCausa: norm(document.querySelector('#valorAcaoProcesso')?.textContent),
        partes,
        movimentos,
        audiencias,
        distribuicao,
        linkPublico: window.location.href,
    };
}
"""


def _parse_partes(rows: List[Dict[str, str]]) -> tuple[Optional[str], Optional[str]]:
    for row in rows:
        tipo = (row.get("tipo") or "").lower()
        conteudo = row.get("conteudo") or ""
        if not tipo or not conteudo:
            continue
        if "reqte" in tipo or "autor" in tipo:
            partes = conteudo.split("Advogado:")
            requerente = partes[0].replace("\u00a0", " ").strip() if partes else None
            advogado = partes[1].replace("\u00a0", " ").strip() if len(partes) > 1 else None
            return requerente or None, advogado or None
    return None, None


def _parse_movimentos(rows: List[Dict[str, str]]) -> List[Movimento]:
    movimentos: List[Movimento] = []
    for row in rows:
        data_text = row.get("data")
        descricao = (row.get("descricao") or "").strip()
        if not data_text or not re.match(r"\d{2}/\d{2}/\d{4}", data_text):
            continue
        try:
            data = datetime.strptime(data_text[:10], "%d/%m/%Y").date()
        except ValueError:
            continue
        movimentos.append(Movimento(data=data, descricao=descricao))
    return movimentos


def _movimentacoes_extremos(movimentos: List[Movimento]) -> tuple[Optional[str], Optional[str]]:
    if not movimentos:
        return None, None
    sorted_movs = sorted(movimentos, key=lambda item: item.data)
    inicio = sorted_movs[0].data.strftime("%d/%m/%Y")
    ultima = sorted_movs[-1].data.strftime("%d/%m/%Y")
    return inicio, ultima


def _parse_data_audiencia(rows: List[List[str]]) -> Optional[str]:
    for row in rows:
        if not row:
            continue
        if any("não há" in (cell or "").lower() for cell in row if cell):
            return None
        for cell in row:
            if cell and re.match(r"\d{2}/\d{2}/\d{4}", cell):
                return cell
    return None


def _determine_situacao(movimentos: List[Movimento]) -> Optional[str]:
    if not movimentos:
        return None
    for movimento in movimentos:
        descricao = movimento.descricao.lower()
        if "julgada procedente em parte" in descricao or "senten" in descricao:
            if "procedente em parte" in descricao:
                return "sentença (procedente em parte)"
            if "procedente" in descricao:
                return "sentença (procedente)"
            if "improcedente" in descricao:
                return "sentença (improcedente)"
            return "sentença"
    return movimentos[0].descricao


def _infer_tipo_juizo(payload: Dict[str, Any]) -> Optional[str]:
    distribuicao = payload.get("distribuicao") or {}
    area_text = (distribuicao.get("area") or "").lower()
    if "juizado" in area_text:
        return "Juizado Especial"
    if "fazenda" in area_text:
        return "Justiça da Fazenda Pública"
    if "criminal" in area_text:
        return "Justiça Criminal"
    return "Justiça Comum"
