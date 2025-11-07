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
    ProcessoResumoPJE,
    PJEProcessoQuery,
    PJEProcessoListResponse,
    ProcessoPJE,
    PartePJE,
    AdvogadoPJE,
    MovimentoPJE,
    Audiencia,
    Publicacao,
    Documento,
)

BASE_URL = "https://pje1g.trf1.jus.br/consultapublica/ConsultaPublica/listView.seam"


def _filtrar_por_data_pje(processos: List[ProcessoResumoPJE], ano_minimo: int = 2022) -> List[ProcessoResumoPJE]:
    """
    Filtra processos PJE por data de distribuição >= ano_minimo.
    NOTA: ProcessoResumoPJE não inclui data na listagem, então retorna todos.
    O filtro de data será aplicado quando buscar detalhes completos.
    """
    # ProcessoResumoPJE não tem campo dataDistribuicao na listagem
    # Retorna todos os processos sem filtro
    return processos


class PJEFetcher:
    """Fetcher for PJE (Processo Judicial Eletrônico) processes using Playwright."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self) -> "PJEFetcher":
        playwright = await async_playwright().start()
        browser_launcher = getattr(playwright, self.settings.playwright_browser)

        # Use headless with anti-detection for PJE
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

        # Add anti-detection scripts
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
        """)

        self.page = await self.context.new_page()
        return self

    async def __aexit__(self, *args):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def buscar_processos_por_parte(self, nome_parte: str) -> List[ProcessoResumoPJE]:
        """Busca processos por nome de parte usando Playwright."""
        try:
            await self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait for page to be fully loaded
            await self.page.wait_for_load_state('networkidle', timeout=15000)

            # Wait for form to load
            await self.page.wait_for_selector('input[name="fPP:dnp:nomeParte"]', timeout=10000)

            # Fill in the search form
            await self.page.fill('input[name="fPP:dnp:nomeParte"]', nome_parte)

            # Click search button
            await self.page.click('input[id="fPP:searchProcessos"]')

            # Wait for AJAX results to load - wait for tbody with id or timeout
            try:
                # Wait for table tbody with results (up to 30 seconds)
                await self.page.wait_for_selector('tbody#fPP\\:processosTable\\:tb tr.rich-table-row', timeout=30000, state='attached')
                # Give it extra time for all rows to render
                await self.page.wait_for_timeout(2000)
            except PlaywrightTimeoutError:
                # No results found or timeout - that's ok, will return empty list
                pass

            # Get page content
            html = await self.page.content()

            # Parse results
            return self._parse_process_list(html)

        except PlaywrightTimeoutError as e:
            raise HTTPException(status_code=504, detail=f"Timeout ao buscar processos PJE: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao buscar processos PJE: {e}")

    def _parse_process_list(self, html: str) -> List[ProcessoResumoPJE]:
        """Extrai lista de processos do HTML."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        processos = []

        # Find the table with processes
        table = soup.find("table", {"id": "fPP:processosTable"})
        if not table:
            return processos

        # Find tbody with results (has specific ID: fPP:processosTable:tb)
        tbody = table.find("tbody", {"id": "fPP:processosTable:tb"})
        if not tbody:
            # Fallback: try to find any tbody
            tbody = table.find("tbody")
        if not tbody:
            return processos

        # Find all rows with class rich-table-row (includes rich-table-firstrow)
        rows = tbody.find_all("tr", class_=lambda x: x and "rich-table-row" in x)

        for row in rows:
            try:
                # Extract link and process number
                link_tag = row.find("a", onclick=lambda x: x and "DetalheProcessoConsultaPublica" in x)
                if not link_tag:
                    continue

                # Extract onclick parameter to build full link
                onclick = link_tag.get("onclick", "")
                if "ca=" in onclick:
                    ca_param = onclick.split("ca=")[1].split("'")[0]
                    link = f"https://pje1g.trf1.jus.br/consultapublica/ConsultaPublica/DetalheProcessoConsultaPublica/listView.seam?ca={ca_param}"
                else:
                    continue

                # Extract process info from cells
                cells = row.find_all("td", class_="rich-table-cell")
                if len(cells) < 3:
                    continue

                # Extract process number
                bold_tag = cells[1].find("b")
                if bold_tag:
                    numero_processo = bold_tag.get_text(strip=True)
                    # Remove class prefix if present
                    if " " in numero_processo:
                        parts = numero_processo.split(" ")
                        # Find the part that looks like a process number
                        for part in parts:
                            if re.search(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', part):
                                numero_processo = part
                                break
                else:
                    numero_processo = cells[1].get_text(strip=True).split()[0] if cells[1].get_text(strip=True) else "Desconhecido"

                # Extract class
                classe_tag = cells[1].find(text=True, recursive=False)
                classe = classe_tag.strip() if classe_tag else "Desconhecida"

                # Extract last movement from cell 2
                ultima_movimentacao = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                # Extract parties from cell 3
                partes = cells[3].get_text(separator=" ", strip=True) if len(cells) > 3 else ""

                processos.append(ProcessoResumoPJE(
                    numeroProcesso=numero_processo,
                    classe=classe,
                    partes=partes,
                    ultimaMovimentacao=ultima_movimentacao,
                    linkPublico=link
                ))

            except Exception as e:
                # Log error but continue processing other rows
                print(f"Erro ao processar linha: {e}")
                continue

        return processos

    async def buscar_detalhes_processo(self, ca_param: str) -> ProcessoPJE:
        """Busca detalhes completos de um processo usando o parâmetro CA."""
        # If full URL was provided, extract CA parameter
        if "ca=" in ca_param:
            ca_param = ca_param.split("ca=")[1].split("&")[0]

        detail_url = f"https://pje1g.trf1.jus.br/consultapublica/ConsultaPublica/DetalheProcessoConsultaPublica/listView.seam?ca={ca_param}"

        try:
            await self.page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)

            # Wait for page to load
            await self.page.wait_for_timeout(2000)

            # Get page content
            html = await self.page.content()

            # Parse details
            return self._parse_process_detail(html, detail_url)

        except PlaywrightTimeoutError as e:
            raise HTTPException(status_code=504, detail=f"Timeout ao buscar detalhes do processo PJE: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao buscar detalhes do processo PJE: {e}")

    def _parse_process_detail(self, html: str, link_publico: str) -> ProcessoPJE:
        """Extrai todos os detalhes de um processo PJE do HTML."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Extract basic info
        numero_processo = "Desconhecido"
        classe = None

        # Try to find process number
        numero_tag = soup.find("span", id=re.compile(".*numeroProcesso.*"))
        if numero_tag:
            numero_processo = numero_tag.get_text(strip=True)

        # Try to find class
        classe_tag = soup.find("span", id=re.compile(".*classeProcesso.*"))
        if classe_tag:
            classe = classe_tag.get_text(strip=True)

        # Extract movements from table
        movimentos = []
        movimento_tbody = soup.find("tbody", id=re.compile(".*[Ee]vento.*"))
        if movimento_tbody:
            rows = movimento_tbody.find_all("tr", class_="rich-table-row")
            for row in rows:
                span = row.find("span", id=re.compile(".*processoEvento.*"))
                if span:
                    movimento_text = span.get_text(strip=True)
                    # Format is "DD/MM/YYYY HH:MM:SS - Description"
                    if " - " in movimento_text:
                        parts = movimento_text.split(" - ", 1)
                        data = parts[0].strip()
                        descricao = parts[1].strip()
                        movimentos.append(MovimentoPJE(data=data, descricao=descricao))

        # Extract parties
        partes = self._extract_parties_from_table(soup)

        # Separate parties by polo
        polo_ativo = [p for p in partes if p.tipo and "Polo Ativo" in p.tipo]
        polo_passivo = [p for p in partes if p.tipo and "Polo Passivo" in p.tipo]

        # Extract audiências
        audiencias = []
        audiencia_sections = soup.find_all(["div", "table"], id=re.compile(".*[Aa]udiencia.*", re.IGNORECASE))
        for section in audiencia_sections:
            table = section if section.name == "table" else section.find("table")
            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        data = cells[0].get_text(strip=True)
                        tipo = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        if data and re.search(r'\d{2}/\d{2}/\d{4}', data):
                            audiencias.append(Audiencia(data=data, tipo=tipo, situacao=""))

        # Extract publicações
        publicacoes = []
        pub_section = soup.find("div", id=re.compile(".*[Pp]ublicac.*"))
        if pub_section:
            pub_rows = pub_section.find_all("tr")
            for row in pub_rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    data = cells[0].get_text(strip=True)
                    descricao = cells[1].get_text(strip=True)
                    if data and re.search(r'\d{2}/\d{2}/\d{4}', data):
                        publicacoes.append(Publicacao(data=data, descricao=descricao))

        # Extract documentos
        documentos = []
        doc_section = soup.find("div", id=re.compile(".*[Dd]ocumento.*"))
        if doc_section:
            doc_links = doc_section.find_all("a")
            for link in doc_links:
                nome = link.get_text(strip=True)
                url = link.get("href", "")
                if nome:
                    documentos.append(Documento(nome=nome, tipo="PDF", url=url))

        return ProcessoPJE(
            numeroProcesso=numero_processo,
            classe=classe,
            poloAtivo=polo_ativo,
            poloPassivo=polo_passivo,
            linkPublico=link_publico,
            movimentos=movimentos,
            audiencias=audiencias,
            publicacoes=publicacoes,
            documentos=documentos
        )

    def _extract_parties_from_table(self, soup) -> List[PartePJE]:
        """Extract parties from the parties table (Polo Ativo/Passivo)."""
        partes = []

        # Look for both Polo Ativo and Polo Passivo sections by ID
        polo_sections = [
            ("Polo Ativo", soup.find("div", id=re.compile(r".*[Pp]olo[Aa]tivo.*", re.IGNORECASE))),
            ("Polo Passivo", soup.find("div", id=re.compile(r".*[Pp]olo[Pp]assivo.*", re.IGNORECASE)))
        ]

        for polo_name, polo_section in polo_sections:
            if not polo_section:
                continue

            # Find the table in this section
            table = polo_section.find("table")
            if not table:
                continue

            # Parse rows
            rows = table.find_all("tr")
            current_parte = None
            advogados_temp = []

            for row in rows:
                cells = row.find_all("td")

                # We want rows with exactly 2 data cells (Participante, Situação)
                # Skip pagination rows which have many cells or wrong structure
                if len(cells) != 2:
                    continue

                participante = cells[0].get_text(strip=True)
                situacao = cells[1].get_text(strip=True)

                # Skip header rows and empty rows
                if not participante or "Participante" in participante or "Situação" in participante:
                    continue

                # Skip navigation elements
                if "resultados encontrados" in participante.lower():
                    continue

                # Check if this is a lawyer (ADVOGADO type)
                if "(ADVOGADO)" in participante.upper():
                    # Extract lawyer info
                    # Format: "NOME - OAB XXXXX - CPF: XXX (ADVOGADO)"
                    nome_adv = participante.split(" - OAB")[0].strip()
                    oab_match = re.search(r'OAB\s+([A-Z]{2}\d+)', participante)
                    oab = oab_match.group(1) if oab_match else None

                    advogados_temp.append(AdvogadoPJE(
                        nome=nome_adv,
                        oab=oab,
                        situacao=situacao
                    ))
                else:
                    # This is a main party (not a lawyer)
                    # If we have a previous party, save it with its lawyers
                    if current_parte:
                        current_parte["advogados"] = advogados_temp
                        partes.append(PartePJE(**current_parte))
                        advogados_temp = []

                    # Extract party info
                    # Format: "NOME - CNPJ/CPF: XXX (TIPO)"
                    nome_parte = participante.split(" - CNPJ:")[0].split(" - CPF:")[0].strip()

                    # Extract document (CNPJ or CPF)
                    doc_match = re.search(r'(?:CNPJ|CPF):\s*([\d./-]+)', participante)
                    documento = doc_match.group(1) if doc_match else None

                    # Extract type (EXEQUENTE, EXECUTADO, etc)
                    tipo_match = re.search(r'\(([^)]+)\)', participante)
                    tipo_parte = tipo_match.group(1) if tipo_match else ""

                    # Add polo to the type
                    tipo_parte = f"{polo_name} - {tipo_parte}" if tipo_parte else polo_name

                    current_parte = {
                        "tipo": tipo_parte,
                        "nome": nome_parte,
                        "documento": documento,
                        "advogados": []
                    }

            # Save the last party with its lawyers
            if current_parte:
                current_parte["advogados"] = advogados_temp
                partes.append(PartePJE(**current_parte))

        return partes


# ==================== Public API Functions ====================

async def fetch_pje_process_list(query: PJEProcessoQuery) -> PJEProcessoListResponse:
    """
    Busca lista de processos PJE por nome de parte usando Playwright.
    Tenta múltiplas variações do nome se necessário (adiciona SA, LTDA, etc.)
    """
    settings = get_settings()

    async with PJEFetcher(settings) as fetcher:
        # Try search with original query
        processos = await fetcher.buscar_processos_por_parte(query.nome_parte)

        # If no results and nome_parte was provided, try with common suffixes
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
                    nome_com_sufixo = f"{nome_original} {sufixo}"
                    processos = await fetcher.buscar_processos_por_parte(nome_com_sufixo)

                    if len(processos) > 0:
                        # Found results with this suffix
                        break

        # Filter by date if needed
        processos_filtrados = _filtrar_por_data_pje(processos, ano_minimo=2022)

        return PJEProcessoListResponse(
            processos=processos_filtrados,
            total=len(processos_filtrados)
        )


async def fetch_pje_process_detail(ca_param: str) -> ProcessoPJE:
    """
    Busca detalhes completos de um processo PJE usando o parâmetro CA.
    """
    settings = get_settings()

    async with PJEFetcher(settings) as fetcher:
        return await fetcher.buscar_detalhes_processo(ca_param)
