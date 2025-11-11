"""
Camada de persistência para processos judiciais.
Gerencia armazenamento e consulta de processos coletados dos tribunais TJSP, PJE e TJRJ.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from services.db_client import get_db_connection

logger = logging.getLogger(__name__)


# ==============================================================================
# Funções de salvamento e atualização
# ==============================================================================

async def salvar_processo(
    dados: Dict[str, Any],
    tribunal: str,
    permitir_atualizacao: bool = True,
    nome_parte_referencia: Optional[str] = None,
) -> UUID:
    """
    Salva ou atualiza um processo judicial no banco de dados.

    - Se o processo não existe (por numero_processo + tribunal): INSERT
    - Se o processo existe mas mudou: UPDATE
    - Se o processo existe e não mudou: SKIP (retorna ID existente)

    Args:
        dados: Dicionário com dados do processo (ProcessoTJSP, ProcessoPJE ou ProcessoTJRJ)
        tribunal: String identificando o tribunal ("TJSP", "PJE" ou "TJRJ")
        permitir_atualizacao: Atualiza registros existentes quando True
        nome_parte_referencia: Termo usado para coleta (ex.: "Claro S.A")

    Returns:
        UUID do processo (novo ou existente)
    """
    # Extrair campos comuns
    numero_processo = dados.get("numeroProcesso")
    if not numero_processo:
        raise ValueError("numeroProcesso é obrigatório")

    # Campos que existem em todos os tribunais
    classe = dados.get("classe")
    assunto = dados.get("assunto")
    comarca = dados.get("comarca")
    vara = dados.get("vara")
    juiz = dados.get("juiz")
    valor_causa = dados.get("valorCausa")
    situacao = dados.get("situacao")
    link_publico = dados.get("linkPublico")
    uf = dados.get("uf")

    # Data de distribuição (pode estar em formatos diferentes)
    data_distribuicao = None
    data_dist_raw = dados.get("dataDistribuicao")
    if data_dist_raw:
        if isinstance(data_dist_raw, date):
            data_distribuicao = data_dist_raw
        elif isinstance(data_dist_raw, str):
            # Tentar parsear DD/MM/YYYY ou YYYY-MM-DD
            try:
                if "/" in data_dist_raw:
                    parts = data_dist_raw.split("/")
                    if len(parts) == 3:
                        # DD/MM/YYYY
                        data_distribuicao = date(int(parts[2]), int(parts[1]), int(parts[0]))
                elif "-" in data_dist_raw:
                    # YYYY-MM-DD
                    data_distribuicao = date.fromisoformat(data_dist_raw)
            except (ValueError, IndexError):
                logger.warning(f"Formato de data inválido: {data_dist_raw}")

    # JSON completo (serializar para armazenar no JSONB)
    if nome_parte_referencia:
        meta = dados.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        meta["nomeParteReferencia"] = nome_parte_referencia
        dados["meta"] = meta

    dados_completos = json.dumps(dados, default=str, ensure_ascii=False)

    async with get_db_connection() as conn:
        # Verificar se processo já existe
        row = await conn.fetchrow(
            """
            SELECT id, dados_completos
            FROM processos.processos_judiciais
            WHERE numero_processo = $1 AND tribunal = $2
            """,
            numero_processo, tribunal
        )

        if row:
            # Processo existe - verificar se mudou
            processo_id = row["id"]
            dados_antigos = row["dados_completos"]

            # Comparar se houve mudança (comparar JSONs)
            if dados_antigos == json.loads(dados_completos):
                logger.debug(f"Processo {numero_processo} ({tribunal}) não teve mudanças")
                return processo_id

            # Houve mudança - atualizar
            logger.info(f"Atualizando processo {numero_processo} ({tribunal})")
            await conn.execute(
                """
                UPDATE processos.processos_judiciais
                SET classe = $1, assunto = $2, comarca = $3, vara = $4, juiz = $5,
                    data_distribuicao = $6, valor_causa = $7, situacao = $8,
                    link_publico = $9, uf = $10, dados_completos = $11,
                    updated_at = NOW()
                WHERE id = $12
                """,
                classe, assunto, comarca, vara, juiz, data_distribuicao,
                valor_causa, situacao, link_publico, uf, dados_completos,
                processo_id
            )

            return processo_id

        else:
            # Processo novo - inserir
            logger.info(f"Inserindo novo processo {numero_processo} ({tribunal})")
            processo_id = uuid4()

            await conn.execute(
                """
                INSERT INTO processos.processos_judiciais (
                    id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                    data_distribuicao, valor_causa, situacao, link_publico, dados_completos
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                processo_id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                data_distribuicao, valor_causa, situacao, link_publico, dados_completos
            )

            # Salvar partes (autores, réus, advogados)
            await _salvar_partes(conn, processo_id, dados, tribunal)

            return processo_id


async def _salvar_partes(conn, processo_id: UUID, dados: Dict[str, Any], tribunal: str) -> None:
    """
    Salva partes e advogados relacionados ao processo.
    Estruturas variam por tribunal.
    """
    partes_para_inserir = []

    if tribunal == "TJSP":
        # TJSP tem requerente e advogadoConsumidor como strings simples
        if dados.get("requerente"):
            partes_para_inserir.append({
                "tipo": "autor",
                "nome": dados["requerente"],
                "documento": None,
                "dados_adicionais": None
            })

        if dados.get("advogadoConsumidor"):
            partes_para_inserir.append({
                "tipo": "advogado",
                "nome": dados["advogadoConsumidor"],
                "documento": None,
                "dados_adicionais": None
            })

        # partesRelacionadas pode ter mais informações
        if dados.get("partesRelacionadas"):
            for parte_str in dados["partesRelacionadas"]:
                # Tentar identificar tipo (Autor: nome, Réu: nome, etc)
                if parte_str.startswith("Autor:"):
                    nome = parte_str.replace("Autor:", "").strip()
                    partes_para_inserir.append({"tipo": "autor", "nome": nome, "documento": None, "dados_adicionais": None})
                elif parte_str.startswith("Réu:") or parte_str.startswith("Reu:"):
                    nome = parte_str.replace("Réu:", "").replace("Reu:", "").strip()
                    partes_para_inserir.append({"tipo": "reu", "nome": nome, "documento": None, "dados_adicionais": None})

    elif tribunal == "PJE":
        # PJE tem estrutura complexa com poloAtivo e poloPassivo
        for parte in dados.get("poloAtivo", []):
            partes_para_inserir.append({
                "tipo": "autor",
                "nome": parte.get("nome"),
                "documento": parte.get("documento"),
                "dados_adicionais": json.dumps(parte, default=str) if parte else None
            })

            # Advogados do polo ativo
            for adv in parte.get("advogados", []):
                partes_para_inserir.append({
                    "tipo": "advogado",
                    "nome": adv.get("nome"),
                    "documento": None,
                    "dados_adicionais": json.dumps(adv, default=str) if adv else None
                })

        for parte in dados.get("poloPassivo", []):
            partes_para_inserir.append({
                "tipo": "reu",
                "nome": parte.get("nome"),
                "documento": parte.get("documento"),
                "dados_adicionais": json.dumps(parte, default=str) if parte else None
            })

            # Advogados do polo passivo
            for adv in parte.get("advogados", []):
                partes_para_inserir.append({
                    "tipo": "advogado",
                    "nome": adv.get("nome"),
                    "documento": None,
                    "dados_adicionais": json.dumps(adv, default=str) if adv else None
                })

    elif tribunal == "TJRJ":
        # TJRJ tem autor, reu e advogados como campos simples
        if dados.get("autor"):
            partes_para_inserir.append({
                "tipo": "autor",
                "nome": dados["autor"],
                "documento": None,
                "dados_adicionais": None
            })

        if dados.get("reu"):
            partes_para_inserir.append({
                "tipo": "reu",
                "nome": dados["reu"],
                "documento": None,
                "dados_adicionais": None
            })

        for adv_nome in dados.get("advogados", []):
            if adv_nome:
                partes_para_inserir.append({
                    "tipo": "advogado",
                    "nome": adv_nome,
                    "documento": None,
                    "dados_adicionais": None
                })

    # Inserir todas as partes
    for parte in partes_para_inserir:
        if parte["nome"]:  # Só inserir se tem nome
            await conn.execute(
                """
                INSERT INTO processos.processos_partes (id, processo_id, tipo, nome, documento, dados_adicionais)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                uuid4(), processo_id, parte["tipo"], parte["nome"], parte["documento"], parte["dados_adicionais"]
            )


# ==============================================================================
# Funções de consulta
# ==============================================================================

async def buscar_processos(
    filtros: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    offset: int = 0,
    include_dados_completos: bool = True
) -> Dict[str, Any]:
    """
    Busca processos com filtros e paginação.

    Args:
        filtros: Dicionário com filtros opcionais:
            - tribunal: str (TJSP/PJE/TJRJ)
            - numero_processo: str (busca parcial com ILIKE)
            - classe: str
            - assunto: str
            - nome_parte: str (busca ILIKE nas partes associadas)
            - data_inicio: date
            - data_fim: date
            - comarca: str
            - uf: str
        limit: Máximo de resultados (1-500)
        offset: Número de resultados para pular (paginação)

    Returns:
        {
            "total": int,
            "processos": [lista de processos],
            "has_more": bool
        }
    """
    filtros = filtros or {}

    # Limitar o limit
    limit = min(max(1, limit), 500)

    async with get_db_connection() as conn:
        # Construir WHERE clause dinamicamente
        where_clauses = []
        params = []
        param_count = 1

        if filtros.get("tribunal"):
            where_clauses.append(f"tribunal = ${param_count}")
            params.append(filtros["tribunal"])
            param_count += 1

        if filtros.get("numero_processo"):
            where_clauses.append(f"numero_processo ILIKE ${param_count}")
            params.append(f"%{filtros['numero_processo']}%")
            param_count += 1

        if filtros.get("classe"):
            where_clauses.append(f"classe ILIKE ${param_count}")
            params.append(f"%{filtros['classe']}%")
            param_count += 1

        if filtros.get("assunto"):
            where_clauses.append(f"assunto ILIKE ${param_count}")
            params.append(f"%{filtros['assunto']}%")
            param_count += 1

        if filtros.get("comarca"):
            where_clauses.append(f"comarca ILIKE ${param_count}")
            params.append(f"%{filtros['comarca']}%")
            param_count += 1

        if filtros.get("uf"):
            where_clauses.append(f"uf = ${param_count}")
            params.append(filtros["uf"])
            param_count += 1

        if filtros.get("data_inicio"):
            where_clauses.append(f"data_distribuicao >= ${param_count}")
            params.append(filtros["data_inicio"])
            param_count += 1

        if filtros.get("data_fim"):
            where_clauses.append(f"data_distribuicao <= ${param_count}")
            params.append(filtros["data_fim"])
            param_count += 1

        if filtros.get("nome_parte"):
            nome_parte_raw = filtros["nome_parte"]
            raw_tokens = [token for token in re.split(r"[^0-9A-Za-z]+", nome_parte_raw) if token]
            search_terms = [token.lower() for token in raw_tokens if len(token) >= 3]

            if not search_terms:
                trimmed = nome_parte_raw.strip().lower()
                if trimmed:
                    search_terms = [trimmed]

            if search_terms:
                term_clauses = []
                for term in search_terms:
                    like_value = f"%{term}%"

                    partes_placeholder = param_count
                    params.append(like_value)
                    param_count += 1

                    meta_placeholder = param_count
                    params.append(like_value)
                    param_count += 1

                    term_clauses.append(
                        f"""(
                            EXISTS (
                                SELECT 1
                                FROM processos.processos_partes pp
                                WHERE pp.processo_id = processos.processos_judiciais.id
                                  AND lower(pp.nome) LIKE ${partes_placeholder}
                            )
                            OR lower(COALESCE(dados_completos->'meta'->>'nomeParteReferencia', '')) LIKE ${meta_placeholder}
                        )"""
                    )

                if term_clauses:
                    where_clauses.append("(" + " AND ".join(term_clauses) + ")")

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Contar total
        count_query = f"SELECT COUNT(*) FROM processos.processos_judiciais {where_sql}"
        total = await conn.fetchval(count_query, *params)

        # Buscar processos
        query = f"""
            SELECT
                id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                data_distribuicao, valor_causa, situacao, link_publico,
                dados_completos, created_at, updated_at
            FROM processos.processos_judiciais
            {where_sql}
            ORDER BY data_distribuicao DESC NULLS LAST, updated_at DESC
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        # Converter para dicionários
        processos = []
        for row in rows:
            proc = dict(row)

            # Parse dados_completos se for string
            if isinstance(proc.get("dados_completos"), str):
                try:
                    import json
                    proc["dados_completos"] = json.loads(proc["dados_completos"])
                except (json.JSONDecodeError, TypeError):
                    proc["dados_completos"] = {}

            # Se include_dados_completos, buscar partes também
            if include_dados_completos:
                partes_query = """
                    SELECT tipo, nome, documento, dados_adicionais
                    FROM processos.processos_partes
                    WHERE processo_id = $1
                    ORDER BY tipo, nome
                """
                partes = await conn.fetch(partes_query, row["id"])
                proc["partes"] = [dict(p) for p in partes]
            else:
                proc["partes"] = []

            processos.append(proc)

        return {
            "total": total,
            "processos": processos,
            "has_more": (offset + limit) < total
        }


async def buscar_processo_por_numero(numero: str, tribunal: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Busca um processo específico por número.

    Args:
        numero: Número do processo (completo ou parcial)
        tribunal: Tribunal específico (opcional)

    Returns:
        Dicionário com dados do processo ou None se não encontrado
    """
    async with get_db_connection() as conn:
        if tribunal:
            query = """
                SELECT
                    id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                    data_distribuicao, valor_causa, situacao, link_publico,
                    dados_completos, created_at, updated_at
                FROM processos.processos_judiciais
                WHERE numero_processo = $1 AND tribunal = $2
            """
            row = await conn.fetchrow(query, numero, tribunal)
        else:
            query = """
                SELECT
                    id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                    data_distribuicao, valor_causa, situacao, link_publico,
                    dados_completos, created_at, updated_at
                FROM processos.processos_judiciais
                WHERE numero_processo = $1
                LIMIT 1
            """
            row = await conn.fetchrow(query, numero)

        if not row:
            return None

        # Buscar partes relacionadas
        partes_query = """
            SELECT tipo, nome, documento, dados_adicionais
            FROM processos.processos_partes
            WHERE processo_id = $1
            ORDER BY tipo, nome
        """
        partes = await conn.fetch(partes_query, row["id"])

        # Montar resultado
        resultado = dict(row)
        resultado["partes"] = [dict(p) for p in partes]

        # Parse dados_completos se for string
        if isinstance(resultado.get("dados_completos"), str):
            try:
                resultado["dados_completos"] = json.loads(resultado["dados_completos"])
            except (json.JSONDecodeError, TypeError):
                resultado["dados_completos"] = {}

        return resultado


async def obter_estatisticas() -> Dict[str, Any]:
    """
    Retorna estatísticas gerais dos processos armazenados.

    Returns:
        {
            "total_processos": int,
            "por_tribunal": {tribunal: count},
            "por_ano": {ano: count},
            "ultima_atualizacao": datetime
        }
    """
    async with get_db_connection() as conn:
        # Total geral
        total = await conn.fetchval("SELECT COUNT(*) FROM processos.processos_judiciais")

        # Por tribunal
        por_tribunal_rows = await conn.fetch(
            "SELECT tribunal, COUNT(*) as total FROM processos.processos_judiciais GROUP BY tribunal"
        )
        por_tribunal = {row["tribunal"]: row["total"] for row in por_tribunal_rows}

        # Por ano de distribuição
        por_ano_rows = await conn.fetch(
            """
            SELECT EXTRACT(YEAR FROM data_distribuicao)::int as ano, COUNT(*) as total
            FROM processos.processos_judiciais
            WHERE data_distribuicao IS NOT NULL
            GROUP BY ano
            ORDER BY ano DESC
            """
        )
        por_ano = {row["ano"]: row["total"] for row in por_ano_rows}

        # Última atualização
        ultima_atualizacao = await conn.fetchval(
            "SELECT MAX(updated_at) FROM processos.processos_judiciais"
        )

        return {
            "total_processos": total,
            "por_tribunal": por_tribunal,
            "por_ano": por_ano,
            "ultima_atualizacao": ultima_atualizacao
        }


# ==============================================================================
# Funções de histórico de coletas
# ==============================================================================

async def registrar_inicio_coleta(tribunal: str) -> UUID:
    """
    Registra o início de uma execução de coleta.

    Returns:
        UUID da coleta (para usar em registrar_fim_coleta)
    """
    async with get_db_connection() as conn:
        coleta_id = uuid4()
        await conn.execute(
            """
            INSERT INTO processos.coletas_historico (id, tribunal, inicio, status)
            VALUES ($1, $2, NOW(), 'em_andamento')
            """,
            coleta_id, tribunal
        )

        return coleta_id


async def registrar_fim_coleta(
    coleta_id: UUID,
    status: str,
    stats: Optional[Dict[str, Any]] = None,
    erro: Optional[str] = None,
    erro_traceback: Optional[str] = None
) -> None:
    """
    Registra o fim de uma execução de coleta.

    Args:
        coleta_id: UUID retornado por registrar_inicio_coleta
        status: "sucesso", "erro" ou "parcial"
        stats: Estatísticas da execução (total_encontrados, novos, atualizados)
        erro: Mensagem de erro (se houver)
        erro_traceback: Stack trace do erro (se houver)
    """
    stats = stats or {}

    async with get_db_connection() as conn:
        await conn.execute(
            """
            UPDATE processos.coletas_historico
            SET fim = NOW(),
                status = $1,
                total_processos_encontrados = $2,
                total_processos_novos = $3,
                total_processos_atualizados = $4,
                total_processos_ignorados = $5,
                erro_mensagem = $6,
                erro_traceback = $7,
                detalhes = $8
            WHERE id = $9
            """,
            status,
            stats.get("total_processos_encontrados", 0),
            stats.get("total_processos_novos", 0),
            stats.get("total_processos_atualizados", 0),
            stats.get("total_processos_ignorados", 0),
            erro,
            erro_traceback,
            json.dumps(stats, default=str, ensure_ascii=False) if stats else None,
            coleta_id
        )


async def obter_historico_coletas(tribunal: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retorna histórico de coletas executadas.

    Args:
        tribunal: Filtrar por tribunal específico (opcional)
        limit: Máximo de registros

    Returns:
        Lista de dicionários com dados das coletas
    """
    async with get_db_connection() as conn:
        if tribunal:
            query = """
                SELECT * FROM processos.coletas_historico
                WHERE tribunal = $1
                ORDER BY inicio DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, tribunal, limit)
        else:
            query = """
                SELECT * FROM processos.coletas_historico
                ORDER BY inicio DESC
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)

        return [dict(row) for row in rows]


async def obter_ultima_coleta(tribunal: str) -> Optional[Dict[str, Any]]:
    """
    Retorna a última coleta bem-sucedida de um tribunal.
    Útil para coleta incremental.

    Returns:
        Dicionário com dados da última coleta ou None
    """
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM processos.coletas_historico
            WHERE tribunal = $1 AND status = 'sucesso'
            ORDER BY inicio DESC
            LIMIT 1
            """,
            tribunal
        )

        return dict(row) if row else None
