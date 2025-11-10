#!/usr/bin/env python3
"""
Importador rápido para processos TJSP (CPG) usando HTTP direto (sem Playwright).

Fluxo:
    1. Acessa /cpopg/open.do para obter cookies
    2. Executa search.do (página 1) com cbPesquisa/dados fornecidos
    3. Percorre páginas subsequentes com trocarPagina.do?paginaConsulta=N
    4. Persiste os resumos em processos.processos_judiciais com tribunal='TJSP'

Uso:
    python3 scripts/import_tjsp_cpopg.py --doc 40432544000147 --max-pages 0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import asyncpg
import httpx
from bs4 import BeautifulSoup

BASE_HOST = "https://esaj.tjsp.jus.br"
BASE_URL = f"{BASE_HOST}/cpopg"
SEARCH_URL = f"{BASE_URL}/search.do"
PAGE_URL = f"{BASE_URL}/trocarPagina.do"
OPEN_URL = f"{BASE_URL}/open.do"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": OPEN_URL,
}


@dataclass
class ProcessoResumoTJSPHTTP:
    numero_processo: str
    link_detalhe: str
    tipo_participacao: Optional[str]
    nomes_partes: List[str]
    classe: Optional[str]
    assunto: Optional[str]
    distribuicao_texto: Optional[str]
    pagina: int


def parse_listing(html: str, page_number: int) -> List[ProcessoResumoTJSPHTTP]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.row.unj-ai-c.home__lista-de-processos")
    resultados: List[ProcessoResumoTJSPHTTP] = []

    def norm(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = " ".join(text.split())
        return stripped or None

    for card in cards:
        anchor = card.select_one(".nuProcesso a")
        numero = norm(anchor.text) if anchor else None
        if not numero:
            continue
        href = anchor.get("href") if anchor else None
        tipo_node = card.select_one(".tipoDeParticipacao")
        tipo = norm(tipo_node.text if tipo_node else None)
        if tipo and tipo.endswith(":"):
            tipo = tipo[:-1].strip() or tipo
        partes_block = card.select_one(".nomeParte")
        nomes = []
        if partes_block:
            nomes = [line.strip() for line in partes_block.text.splitlines() if line.strip()]
        classe = norm(card.select_one(".classeProcesso").text if card.select_one(".classeProcesso") else None)
        assunto = norm(
            card.select_one(".assuntoPrincipalProcesso").text if card.select_one(".assuntoPrincipalProcesso") else None
        )
        dist = norm(
            card.select_one(".dataLocalDistribuicaoProcesso").text
            if card.select_one(".dataLocalDistribuicaoProcesso")
            else None
        )
        resultados.append(
            ProcessoResumoTJSPHTTP(
                numero_processo=numero,
                link_detalhe=urljoin(BASE_HOST, href) if href else "",
                tipo_participacao=tipo,
                nomes_partes=nomes,
                classe=classe,
                assunto=assunto,
                distribuicao_texto=dist,
                pagina=page_number,
            )
        )
    return resultados


async def get_db_pool() -> asyncpg.Pool:
    if os.path.exists("/app"):
        sys.path.insert(0, "/app")
    else:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

    from config import get_settings  # type: ignore

    settings = get_settings()
    db_host = settings.postgres_host if os.path.exists("/app") else "localhost"
    db_port = settings.postgres_port if os.path.exists("/app") else 5432
    db_url = (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}@"
        f"{db_host}:{db_port}/{settings.postgres_db}"
    )
    print(f"[DB] Connecting to: postgresql://***:***@{db_host}:{db_port}/{settings.postgres_db}")
    return await asyncpg.create_pool(db_url, min_size=5, max_size=20, command_timeout=60)


async def salvar_processo(pool: asyncpg.Pool, resumo: ProcessoResumoTJSPHTTP) -> Tuple[bool, str]:
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM processos.processos_judiciais WHERE numero_processo=$1 AND tribunal='TJSP'",
            resumo.numero_processo,
        )
        if existing:
            return False, str(existing)

        from uuid import uuid4

        processo_id = uuid4()
        dados = json.dumps(
            {
                "numeroProcesso": resumo.numero_processo,
                "classe": resumo.classe,
                "assunto": resumo.assunto,
                "tipoParticipacao": resumo.tipo_participacao,
                "nomesPartes": resumo.nomes_partes,
                "distribuicao": resumo.distribuicao_texto,
                "pagina": resumo.pagina,
                "link": resumo.link_detalhe,
            },
            ensure_ascii=False,
        )
        await conn.execute(
            """
            INSERT INTO processos.processos_judiciais (
                id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                data_distribuicao, valor_causa, situacao, link_publico, dados_completos
            )
            VALUES ($1, $2, 'TJSP', 'SP', $3, $4, NULL, NULL, NULL, NULL, NULL, NULL, $5, $6)
            """,
            processo_id,
            resumo.numero_processo,
            resumo.classe,
            resumo.assunto,
            resumo.link_detalhe,
            dados,
        )

        tipo_db = "outro"
        if resumo.tipo_participacao:
            tipo_lower = resumo.tipo_participacao.lower()
            if any(token in tipo_lower for token in ("autor", "autora", "exequente", "exeqte")):
                tipo_db = "autor"
            elif any(token in tipo_lower for token in ("réu", "reu", "executado", "executada", "exect", "executado")):
                tipo_db = "reu"
            elif "adv" in tipo_lower:
                tipo_db = "advogado"

            for nome in resumo.nomes_partes:
                await conn.execute(
                    "INSERT INTO processos.processos_partes (id, processo_id, tipo, nome) VALUES ($1, $2, $3, $4)",
                    uuid4(),
                    processo_id,
                    tipo_db,
                    nome,
                )
        return True, str(processo_id)


def map_parte_tipo(label: Optional[str]) -> str:
    if not label:
        return "outro"
    lbl = label.lower()
    if any(token in lbl for token in ("autor", "requerente", "reqte")):
        return "autor"
    if any(token in lbl for token in ("réu", "reu", "requerido", "reqdo", "reqda", "executado", "executada")):
        return "reu"
    if "adv" in lbl:
        return "advogado"
    return "outro"


def parse_detail_page(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    def text_by_id(elem_id: str) -> Optional[str]:
        node = soup.find(id=elem_id)
        if not node:
            return None
        value = node.get_text(strip=True)
        return value or None

    detail: Dict[str, Any] = {
        "classe": text_by_id("classeProcesso"),
        "assunto": text_by_id("assuntoProcesso"),
        "foro": text_by_id("foroProcesso"),
        "vara": text_by_id("varaProcesso"),
        "juiz": text_by_id("juizProcesso"),
        "dataDistribuicao": text_by_id("dataHoraDistribuicao"),
        "valorCausa": text_by_id("valorCausaProcesso"),
        "situacao": text_by_id("situacaoProcesso"),
    }

    partes: List[Dict[str, Any]] = []
    partes_table = soup.find("table", id="tablePartesPrincipais")
    if partes_table:
        rows = partes_table.find_all("tr", class_="fundoClaro")
        for row in rows:
            tipo_label = row.select_one(".tipoDeParticipacao")
            tipo = map_parte_tipo(tipo_label.get_text(strip=True) if tipo_label else None)
            bloco = row.select_one(".nomeParteEAdvogado")
            if not bloco:
                continue
            raw_text = bloco.get_text("\n", strip=True)
            partes_split = raw_text.split("Advogado:")
            nome = partes_split[0].strip()
            advogados: List[str] = []
            if len(partes_split) > 1:
                advogados = [seg.strip() for seg in partes_split[1].split("\n") if seg.strip()]
            partes.append(
                {
                    "tipo": tipo,
                    "nome": nome,
                    "advogados": advogados,
                }
            )
    detail["partes"] = partes

    movimentos: List[Dict[str, Any]] = []
    mov_header = soup.find("h2", string=lambda s: s and "Movimentações" in s)
    if mov_header:
        mov_table = mov_header.find_parent().find_next_sibling("table")
        if mov_table:
            for row in mov_table.select("tr.containerMovimentacao"):
                data = row.select_one(".dataMovimentacao")
                desc = row.select_one(".descricaoMovimentacao")
                data_text = data.get_text(strip=True) if data else None
                descricao = " ".join(desc.get_text(separator=" ").split()).strip() if desc else None
                if descricao:
                    movimentos.append({"data": data_text, "descricao": descricao})
    detail["movimentos"] = movimentos

    return detail


async def atualizar_processo_com_detalhes(
    pool: asyncpg.Pool,
    processo_id: str,
    detail: Dict[str, Any],
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE processos.processos_judiciais
            SET classe = COALESCE($2, classe),
                assunto = COALESCE($3, assunto),
                comarca = COALESCE($4, comarca),
                vara = COALESCE($5, vara),
                juiz = COALESCE($6, juiz),
                data_distribuicao = COALESCE($7, data_distribuicao),
                valor_causa = COALESCE($8, valor_causa),
                situacao = COALESCE($9, situacao),
                dados_completos = $10
            WHERE id = $1
            """,
            processo_id,
            detail.get("classe"),
            detail.get("assunto"),
            detail.get("foro"),
            detail.get("vara"),
            detail.get("juiz"),
            detail.get("dataDistribuicao"),
            detail.get("valorCausa"),
            detail.get("situacao"),
            json.dumps(detail, ensure_ascii=False),
        )
        if detail.get("partes"):
            await conn.execute("DELETE FROM processos.processos_partes WHERE processo_id=$1", processo_id)
            from uuid import uuid4

            for parte in detail["partes"]:
                await conn.execute(
                    "INSERT INTO processos.processos_partes (id, processo_id, tipo, nome, dados_adicionais) "
                    "VALUES ($1, $2, $3, $4, $5)",
                    uuid4(),
                    processo_id,
                    parte.get("tipo") or "outro",
                    parte.get("nome"),
                    json.dumps({"advogados": parte.get("advogados", [])}, ensure_ascii=False),
                )


async def fetch_process_detail(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        print(f"[DETALHE] ✓ {url}")
        return parse_detail_page(resp.text)
    except Exception as exc:
        print(f"[DETALHE] ✗ Falha ao carregar {url}: {exc}")
        return None


async def import_tjsp(
    doc: str,
    cb_pesquisa: str,
    foro: str,
    start_page: int,
    max_pages: Optional[int],
    stop_after_duplicates: int,
    fetch_details: bool,
    detail_parallel: int,
) -> None:
    pool = await get_db_pool()
    stats_global = {"processados": 0, "salvos": 0, "duplicados": 0, "erros": 0}
    consecutive_duplicates = 0
    current_page = start_page

    detail_sem = asyncio.Semaphore(detail_parallel if detail_parallel > 0 else 1)

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=120, follow_redirects=True) as client:
        await client.get(OPEN_URL)
        while True:
            if max_pages and (current_page - start_page) >= max_pages:
                print(f"[FIM] Limite de páginas atingido ({max_pages}).")
                break

            params = {
                "cbPesquisa": cb_pesquisa,
                "dadosConsulta.valorConsulta": doc,
                "cdForo": foro,
            }
            url = SEARCH_URL if current_page == 1 else PAGE_URL
            if current_page > 1:
                params["paginaConsulta"] = str(current_page)
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            except Exception as exc:
                print(f"[HTTP] ✗ Falha ao buscar página {current_page}: {exc}")
                stats_global["erros"] += 1
                break

            processos = parse_listing(resp.text, current_page)
            if not processos:
                print(f"[HTTP] ✓ Página {current_page} vazia. Encerrando.")
                break

            print(f"[PÁGINA {current_page}] {len(processos)} processos.")
            salvos = 0
            duplicados = 0
            detail_tasks: List[asyncio.Task] = []

            async def schedule_detail(resumo_proc: ProcessoResumoTJSPHTTP, proc_id: str) -> None:
                async def _worker() -> None:
                    async with detail_sem:
                        detalhe = await fetch_process_detail(client, resumo_proc.link_detalhe)
                    if detalhe:
                        print(
                            f"[DETALHE] → processo={resumo_proc.numero_processo} "
                            f"partes={len(detalhe.get('partes', []))} "
                            f"movs={len(detalhe.get('movimentos', []))}"
                        )
                        await atualizar_processo_com_detalhes(pool, proc_id, detalhe)

                detail_tasks.append(asyncio.create_task(_worker()))

            for resumo in processos:
                inserted, processo_id = await salvar_processo(pool, resumo)
                stats_global["processados"] += 1
                if inserted:
                    salvos += 1
                    stats_global["salvos"] += 1
                else:
                    duplicados += 1
                    stats_global["duplicados"] += 1

                if fetch_details and resumo.link_detalhe:
                    await schedule_detail(resumo, processo_id)

            if detail_tasks:
                print(f"[DETALHE] Processando {len(detail_tasks)} requisições em paralelo...")
                await asyncio.gather(*detail_tasks, return_exceptions=True)

            print(
                f"[PÁGINA {current_page}] ✓{salvos} salvos | ⊙{duplicados} duplicados | "
                f"Total acumulado: {stats_global['salvos']}"
            )

            if salvos == 0:
                consecutive_duplicates += duplicados
                if consecutive_duplicates >= stop_after_duplicates:
                    print(f"[STOP] {consecutive_duplicates} duplicados consecutivos. Encerrando.")
                    break
            else:
                consecutive_duplicates = 0

            current_page += 1

    await pool.close()
    print(
        f"==== IMPORTAÇÃO TJSP CONCLUÍDA ====\n"
        f"Processados: {stats_global['processados']} | Salvos: {stats_global['salvos']} | "
        f"Duplicados: {stats_global['duplicados']} | Erros: {stats_global['erros']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Importar processos TJSP (CPG) via HTTP direto.")
    parser.add_argument("--doc", required=True, help="Valor para dadosConsulta.valorConsulta (ex.: CNPJ).")
    parser.add_argument("--cb-pesquisa", default="DOCPARTE", help="Código cbPesquisa (default: DOCPARTE).")
    parser.add_argument("--foro", default="-1", help="Código do foro (default: -1).")
    parser.add_argument("--start-page", type=int, default=1, help="Página inicial (1-index).")
    parser.add_argument("--max-pages", type=int, default=None, help="Máximo de páginas a percorrer (opcional).")
    parser.add_argument("--stop-after-duplicates", type=int, default=500, help="Parar após N duplicados consecutivos.")
    parser.add_argument("--details", action="store_true", help="Buscar detalhes completos de cada processo.")
    parser.add_argument(
        "--detail-parallel",
        type=int,
        default=10,
        help="Número máximo de requisições simultâneas para detalhes (default: 10).",
    )
    args = parser.parse_args()
    asyncio.run(
        import_tjsp(
            doc=args.doc,
            cb_pesquisa=args.cb_pesquisa,
            foro=args.foro,
            start_page=args.start_page,
            max_pages=args.max_pages,
            stop_after_duplicates=args.stop_after_duplicates,
            fetch_details=args.details,
            detail_parallel=args.detail_parallel,
        )
    )


if __name__ == "__main__":
    main()
