from __future__ import annotations

import httpx
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

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
    PJE tem dataDistribuicao como string "DD/MM/YYYY".
    """
    filtrados = []
    for proc in processos:
        if not proc.dataDistribuicao:
            continue  # Sem data, pula

        try:
            # Parse DD/MM/YYYY
            partes = proc.dataDistribuicao.split("/")
            if len(partes) == 3:
                dia, mes, ano = int(partes[0]), int(partes[1]), int(partes[2])
                if ano >= ano_minimo:
                    filtrados.append(proc)
        except (ValueError, IndexError, AttributeError):
            # Se falhar o parse, inclui o processo por segurança
            filtrados.append(proc)

    return filtrados


async def fetch_pje_process_list(query: PJEProcessoQuery) -> PJEProcessoListResponse:
    """
    Busca lista de processos no PJE usando os filtros fornecidos.
    Tenta múltiplas variações do nome se necessário (adiciona SA, LTDA, etc.)
    """

    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # First, get the page to establish session and extract ViewState
        init_response = await client.get(BASE_URL, headers=headers)

        if init_response.status_code != 200:
            return PJEProcessoListResponse(
                total_processos=0,
                processos=[]
            )

        # Extract ViewState from the initial page
        soup = BeautifulSoup(init_response.text, "html.parser")
        viewstate_input = soup.find("input", {"name": "javax.faces.ViewState"})
        viewstate = viewstate_input["value"] if viewstate_input else "j_id1"

        # Try search with original query
        processos = await _try_search(client, query, viewstate, headers, init_response.cookies)

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
                    query_variacao = PJEProcessoQuery(
                        nome_parte=f"{nome_original} {sufixo}",
                        documento_parte=query.documento_parte,
                        nome_advogado=query.nome_advogado,
                        numero_processo=query.numero_processo,
                    )

                    processos = await _try_search(client, query_variacao, viewstate, headers, init_response.cookies)

                    if len(processos) > 0:
                        # Found results with this suffix
                        break

        # Aplicar filtro temporal (processos >= 2022)
        processos = _filtrar_por_data_pje(processos, ano_minimo=2022)

        return PJEProcessoListResponse(
            total_processos=len(processos),
            processos=processos
        )


async def _try_search(
    client: httpx.AsyncClient,
    query: PJEProcessoQuery,
    viewstate: str,
    headers: Dict[str, str],
    cookies,
) -> List[ProcessoResumoPJE]:
    """
    Tenta uma busca no PJE e retorna os processos encontrados.
    """
    # Build form data with extracted ViewState
    form_data = _build_form_data(query, viewstate)

    # Submit the search - PJE returns results directly in AJAX response
    search_response = await client.post(
        BASE_URL,
        headers=headers,
        cookies=cookies,
        data=form_data,
    )

    if search_response.status_code != 200:
        return []

    # Parse the AJAX response HTML (contains the results table)
    return _parse_process_list(search_response.text)


def _build_form_data(query: PJEProcessoQuery, viewstate: str) -> Dict[str, str]:
    """
    Constrói os dados do formulário para enviar ao PJE.
    """
    form_data = {
        "AJAXREQUEST": "_viewRoot",
        "fPP:numProcesso-inputNumeroProcessoDecoration:numProcesso-inputNumeroProcesso": query.numero_processo or "",
        "mascaraProcessoReferenciaRadio": "on",
        "fPP:j_id152:processoReferenciaInput": "",
        "fPP:dnp:nomeParte": query.nome_parte or "",
        "fPP:j_id170:nomeAdv": query.nome_advogado or "",
        "fPP:j_id179:classeProcessualProcessoHidden": "",
        "tipoMascaraDocumento": "on",
        "fPP:dpDec:documentoParte": query.documento_parte or "",
        "fPP:Decoration:numeroOAB": "",
        "fPP:Decoration:j_id214": "",
        "fPP:Decoration:estadoComboOAB": "org.jboss.seam.ui.NoSelectionConverter.noSelectionValue",
        "fPP": "fPP",
        "autoScroll": "",
        "javax.faces.ViewState": viewstate,
        "fPP:j_id220": "fPP:j_id220",
        "AJAX:EVENTS_COUNT": "1",
    }

    return form_data


def _parse_process_list(html: str) -> List[ProcessoResumoPJE]:
    """
    Extrai a lista de processos do HTML retornado pelo PJE.
    """
    soup = BeautifulSoup(html, "html.parser")
    processos = []

    # Find the table with processes
    table = soup.find("table", {"id": "fPP:processosTable"})
    if not table:
        return processos

    # Find all rows in tbody
    tbody = table.find("tbody")
    if not tbody:
        return processos

    rows = tbody.find_all("tr", class_="rich-table-row")

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

            # Extract process info from second cell
            cells = row.find_all("td", class_="rich-table-cell")
            if len(cells) < 3:
                continue

            # Cell 1 contains class and process number
            process_info = cells[1].get_text(separator=" ", strip=True)

            # Extract process number (format: XXXXX-XX.XXXX.X.XX.XXXX)
            bold_tag = cells[1].find("b")
            if bold_tag:
                numero_processo = bold_tag.get_text(strip=True)
                # Remove class prefix if present
                if " " in numero_processo:
                    parts = numero_processo.split(" ")
                    # Find the part that looks like a process number
                    for part in parts:
                        if "-" in part and "." in part:
                            numero_processo = part
                            break
            else:
                continue

            # Extract class
            classe = process_info.split(" ")[0] if " " in process_info else None

            # Extract parties
            partes_text = cells[1].get_text(separator=" ", strip=True)
            # Remove class and process number from parties
            partes = partes_text.replace(numero_processo, "").replace(classe or "", "").strip()

            # Cell 2 contains last movement
            ultima_mov = cells[2].get_text(strip=True)

            processos.append(
                ProcessoResumoPJE(
                    numeroProcesso=numero_processo,
                    classe=classe,
                    partes=partes,
                    ultimaMovimentacao=ultima_mov,
                    linkPublico=link,
                )
            )
        except Exception as e:
            # Skip invalid rows
            continue

    return processos


async def fetch_pje_process_detail(ca_param: str) -> ProcessoPJE:
    """
    Busca detalhes completos de um processo PJE usando o parâmetro CA.
    O parâmetro CA pode ser extraído do link público do processo.
    """
    # If full URL was provided, extract CA parameter
    if "ca=" in ca_param:
        ca_param = ca_param.split("ca=")[1].split("&")[0]

    detail_url = f"https://pje1g.trf1.jus.br/consultapublica/ConsultaPublica/DetalheProcessoConsultaPublica/listView.seam?ca={ca_param}"

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(detail_url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch process details: {response.status_code}")

        return _parse_process_detail(response.text, detail_url)


def _parse_process_detail(html: str, link_publico: str) -> ProcessoPJE:
    """
    Extrai todos os detalhes de um processo PJE do HTML da página de detalhes.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract process number from div with col-sm-12
    numero_processo = ""
    numero_elem = soup.find("div", class_="col-sm-12")
    if numero_elem:
        numero_text = numero_elem.get_text(strip=True)
        match = re.search(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', numero_text)
        if match:
            numero_processo = match.group(0)

    # Extract process metadata from propertyView structure
    classe = None
    data_distribuicao = None
    orgao_julgador = None
    secao_judiciaria = None

    # Find all propertyView divs (each contains a label and value)
    property_views = soup.find_all("div", class_="propertyView")
    for prop_view in property_views:
        label_div = prop_view.find("div", class_="name")
        value_div = prop_view.find("div", class_="value")

        if not label_div or not value_div:
            continue

        label_text = label_div.get_text(strip=True)
        value_text = value_div.get_text(strip=True)

        if "Classe Judicial" in label_text:
            classe = value_text
        elif "Data da Distribuição" in label_text or "Distribuição" in label_text:
            data_distribuicao = value_text
        elif "Órgão Julgador" in label_text or "Órgão julgador" in label_text:
            orgao_julgador = value_text
        elif "Jurisdição" in label_text or "Seção Judiciária" in label_text:
            secao_judiciaria = value_text

    # Extract subjects
    assuntos = []
    for prop_view in property_views:
        label_div = prop_view.find("div", class_="name")
        if label_div and "Assunto" in label_div.get_text(strip=True):
            value_div = prop_view.find("div", class_="value")
            if value_div:
                assunto_text = value_div.get_text(separator=";", strip=True)
                # Split by semicolons and clean up
                assuntos = [a.strip() for a in re.split(r'[;]', assunto_text) if a.strip()]
                break

    # Extract parties - Polo Ativo (plaintiffs)
    polo_ativo = []
    polo_ativo_section = soup.find("div", id=re.compile(".*PoloAtivo.*"))
    if polo_ativo_section:
        polo_ativo = _extract_parties_from_table(polo_ativo_section)

    # Extract parties - Polo Passivo (defendants)
    polo_passivo = []
    polo_passivo_section = soup.find("div", id=re.compile(".*PoloPassivo.*"))
    if polo_passivo_section:
        polo_passivo = _extract_parties_from_table(polo_passivo_section)

    # Extract current status/situation
    situacao = None
    situacao_dt = soup.find("dt", string=re.compile("Situação", re.IGNORECASE))
    if situacao_dt:
        situacao_dd = situacao_dt.find_next_sibling("dd")
        if situacao_dd:
            situacao = situacao_dd.get_text(strip=True)

    # Extract movements from table
    movimentos = []
    movimento_tbody = soup.find("tbody", id=re.compile(".*[Ee]vento.*"))
    if movimento_tbody:
        rows = movimento_tbody.find_all("tr", class_="rich-table-row")
        for row in rows:
            # Find span containing movement text
            span = row.find("span", id=re.compile(".*processoEvento.*"))
            if span:
                movimento_text = span.get_text(strip=True)
                # Format is "DD/MM/YYYY HH:MM:SS - Description"
                if " - " in movimento_text:
                    parts = movimento_text.split(" - ", 1)
                    data = parts[0].strip()
                    descricao = parts[1].strip()
                    movimentos.append(MovimentoPJE(data=data, descricao=descricao))

    # Extract audiências
    audiencias = []
    # Strategy 1: Look for tables/sections with "audiência" in id or class
    audiencia_sections = soup.find_all(["div", "table"], id=re.compile(".*[Aa]udiencia.*", re.IGNORECASE)) + \
                         soup.find_all(["div", "table"], class_=re.compile(".*[Aa]udiencia.*", re.IGNORECASE))

    for section in audiencia_sections:
        table = section if section.name == "table" else section.find("table")
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    # Extract data and details
                    data_text = cells[0].get_text(strip=True) if cells[0] else None
                    tipo_text = cells[1].get_text(strip=True) if len(cells) > 1 and cells[1] else None
                    local_text = cells[2].get_text(strip=True) if len(cells) > 2 and cells[2] else None
                    status_text = cells[3].get_text(strip=True) if len(cells) > 3 and cells[3] else None
                    obs_text = cells[4].get_text(strip=True) if len(cells) > 4 and cells[4] else None

                    if data_text or tipo_text:
                        audiencias.append(Audiencia(
                            data=data_text,
                            tipo=tipo_text,
                            local=local_text,
                            status=status_text,
                            observacoes=obs_text
                        ))

    # Strategy 2: Search for text containing "Audiência" as fallback
    if not audiencias:
        for elem in soup.find_all(string=re.compile(r"[Aa]udi[êe]ncia", re.IGNORECASE)):
            parent = elem.parent
            if parent and parent.name in ['td', 'div', 'span']:
                text = parent.get_text(strip=True)
                if len(text) < 500:
                    audiencias.append(Audiencia(
                        data=None,
                        tipo=None,
                        local=None,
                        status=None,
                        observacoes=text
                    ))
                    break  # Only take the first one to avoid duplicates

    # Extract publicações/intimações
    publicacoes = []
    # Look for sections with "publicação" or "intimação"
    pub_sections = soup.find_all(["div", "table"], id=re.compile(".*[Pp]ublica.*|.*[Ii]ntima.*", re.IGNORECASE)) + \
                   soup.find_all(["div", "table"], class_=re.compile(".*[Pp]ublica.*|.*[Ii]ntima.*", re.IGNORECASE))

    for section in pub_sections:
        table = section if section.name == "table" else section.find("table")
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 1:
                    text = row.get_text(strip=True)
                    # Extract date if present
                    data_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
                    data = data_match.group(1) if data_match else None

                    # Check for links
                    link_elem = row.find("a")
                    link = link_elem.get("href") if link_elem else None

                    if len(text) > 10 and len(text) < 1000:
                        publicacoes.append(Publicacao(
                            data=data,
                            tipo="Publicação",
                            destinatario=None,
                            descricao=text,
                            link=link
                        ))
        else:
            # Plain div with text
            text = section.get_text(strip=True)
            if len(text) > 10 and len(text) < 1000:
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
                publicacoes.append(Publicacao(
                    data=data_match.group(1) if data_match else None,
                    tipo="Publicação",
                    destinatario=None,
                    descricao=text,
                    link=None
                ))

    # Extract documentos/anexos
    documentos = []
    # Look for links with "documento", "petição", "download", "anexo"
    doc_links = soup.find_all("a", href=re.compile(".*[Dd]ocumento.*|.*[Pp]eti.*|.*[Dd]ownload.*|.*[Aa]nexo.*", re.IGNORECASE))

    for link in doc_links:
        nome = link.get_text(strip=True)
        if nome and len(nome) > 3:
            href = link.get("href", "")

            # Try to extract date from parent context
            parent = link.find_parent(["tr", "div"])
            data_match = None
            if parent:
                parent_text = parent.get_text(strip=True)
                data_match = re.search(r'(\d{2}/\d{2}/\d{4})', parent_text)

            # Determine document type based on name
            tipo = "Documento"
            nome_lower = nome.lower()
            if "petição" in nome_lower or "peticao" in nome_lower:
                tipo = "Petição"
            elif "decisão" in nome_lower or "decisao" in nome_lower:
                tipo = "Decisão"
            elif "sentença" in nome_lower or "sentenca" in nome_lower:
                tipo = "Sentença"

            documentos.append(Documento(
                nome=nome,
                tipo=tipo,
                data_juntada=data_match.group(1) if data_match else None,
                autor=None,
                link=href if href.startswith("http") else None
            ))

    # Also look for document sections by id/class
    doc_sections = soup.find_all(["div", "table"], id=re.compile(".*[Dd]ocumento.*|.*[Pp]eti.*", re.IGNORECASE)) + \
                   soup.find_all(["div", "table"], class_=re.compile(".*[Dd]ocumento.*|.*[Pp]eti.*", re.IGNORECASE))

    for section in doc_sections:
        # Find all spans or divs that might contain document names
        for elem in section.find_all(["span", "div", "td"]):
            text = elem.get_text(strip=True)
            # Skip if too short or too long
            if len(text) < 5 or len(text) > 200:
                continue
            # Skip if already added
            if any(doc.nome == text for doc in documentos):
                continue
            # Check if looks like a document name
            if any(keyword in text.lower() for keyword in ["petição", "peticao", "documento", "decisão", "decisao", "sentença", "sentenca", "despacho"]):
                documentos.append(Documento(
                    nome=text,
                    tipo="Documento",
                    data_juntada=None,
                    autor=None,
                    link=None
                ))

    # Extract valor da causa
    valor_causa = None
    for prop_view in property_views:
        label_div = prop_view.find("div", class_="name")
        if label_div and "Valor da causa" in label_div.get_text(strip=True):
            value_div = prop_view.find("div", class_="value")
            if value_div:
                valor_causa = value_div.get_text(strip=True)
                break

    return ProcessoPJE(
        numeroProcesso=numero_processo,
        classe=classe,
        dataDistribuicao=data_distribuicao,
        orgaoJulgador=orgao_julgador,
        secaoJudiciaria=secao_judiciaria,
        assuntos=assuntos,
        poloAtivo=polo_ativo,
        poloPassivo=polo_passivo,
        situacao=situacao,
        linkPublico=link_publico,
        movimentos=movimentos,
        audiencias=audiencias,
        publicacoes=publicacoes,
        documentos=documentos,
        valorCausa=valor_causa,
    )


def _extract_parties_from_table(section) -> List[PartePJE]:
    """
    Extrai informações das partes (polo ativo ou passivo) de uma seção HTML com tabela.
    """
    parties = []

    # Find table within the section
    table = section.find("table")
    if not table:
        return parties

    # Find all rows in table
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 1:
            continue

        # First cell contains party info (name, document, role)
        party_text = cells[0].get_text(strip=True)

        # Extract party name (before CNPJ/CPF or role)
        nome = party_text
        # Remove role in parentheses at the end
        if "(" in nome and nome.endswith(")"):
            nome = nome.rsplit("(", 1)[0].strip()

        # Extract document (CPF/CNPJ)
        documento = None
        doc_match = re.search(r'(?:CPF|CNPJ)[:\s]*(\d{2}\.?\d{3}\.?\d{3}/?(?:\d{4}-)?\d{2}-?\d{2})', party_text)
        if doc_match:
            documento = doc_match.group(1)
            # Remove document from name
            nome = nome.split("-")[0].strip() if "-" in nome else nome.split("CNPJ")[0].split("CPF")[0].strip()

        # Extract lawyers from the table
        # In PJE, lawyers can be in the same cell (separated by line breaks) or in adjacent cells
        advogados = []

        # Strategy 1: Check if there are additional cells with lawyer info
        if len(cells) > 1:
            # Second cell might contain lawyer information
            lawyer_text = cells[1].get_text(strip=True)
            if lawyer_text:
                # Parse multiple lawyers (can be separated by newlines or commas)
                lawyer_lines = [l.strip() for l in lawyer_text.split('\n') if l.strip()]
                for lawyer_line in lawyer_lines:
                    # Extract lawyer name and situacao
                    # Format can be: "Nome do Advogado" or "Nome do Advogado (Ativo)"
                    situacao = None
                    nome_adv = lawyer_line

                    if "(" in lawyer_line and lawyer_line.endswith(")"):
                        parts = lawyer_line.rsplit("(", 1)
                        nome_adv = parts[0].strip()
                        situacao = parts[1].rstrip(")").strip()

                    if nome_adv and len(nome_adv) > 3:
                        advogados.append(AdvogadoPJE(nome=nome_adv, situacao=situacao))

        # Strategy 2: Check within the first cell for lawyer info after line breaks
        if not advogados and "\n" in party_text:
            lines = [l.strip() for l in party_text.split('\n') if l.strip()]
            # First line is usually the party name, subsequent lines might be lawyers
            if len(lines) > 1:
                for line in lines[1:]:
                    # Skip if it looks like role or document info
                    if any(keyword in line.lower() for keyword in ['cpf', 'cnpj', 'autor', 'réu', 'requer']):
                        continue

                    # Extract situacao if present
                    situacao = None
                    nome_adv = line

                    if "(" in line and line.endswith(")"):
                        parts = line.rsplit("(", 1)
                        nome_adv = parts[0].strip()
                        situacao = parts[1].rstrip(")").strip()

                    # Check if this looks like a person's name (has at least 2 words)
                    if nome_adv and len(nome_adv.split()) >= 2:
                        advogados.append(AdvogadoPJE(nome=nome_adv, situacao=situacao))

        if nome and len(nome) > 3:
            parties.append(PartePJE(nome=nome, documento=documento, advogados=advogados))

    return parties
