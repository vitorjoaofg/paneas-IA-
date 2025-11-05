"""
Router para endpoints de consulta de processos judiciais armazenados.
Permite buscar, filtrar e obter estatísticas dos processos coletados.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services import processos_db
from celery_app import celery_app

router = APIRouter(prefix="/api/v1/processos", tags=["processos"])


# ==============================================================================
# Modelos de resposta
# ==============================================================================

class ProcessoResumo(BaseModel):
    """Resumo de um processo para listagem."""
    id: UUID
    numero_processo: str
    tribunal: str
    uf: Optional[str] = None
    classe: Optional[str] = None
    assunto: Optional[str] = None
    comarca: Optional[str] = None
    vara: Optional[str] = None
    data_distribuicao: Optional[date] = None
    situacao: Optional[str] = None
    link_publico: str
    created_at: Any
    updated_at: Any


class ProcessoCompleto(BaseModel):
    """Processo completo com todos os detalhes."""
    id: UUID
    numero_processo: str
    tribunal: str
    uf: Optional[str] = None
    classe: Optional[str] = None
    assunto: Optional[str] = None
    comarca: Optional[str] = None
    vara: Optional[str] = None
    juiz: Optional[str] = None
    data_distribuicao: Optional[date] = None
    valor_causa: Optional[str] = None
    situacao: Optional[str] = None
    link_publico: str
    dados_completos: Dict[str, Any]
    partes: List[Dict[str, Any]]
    created_at: Any
    updated_at: Any


class ProcessosListResponse(BaseModel):
    """Resposta de listagem de processos."""
    total: int
    processos: List[ProcessoResumo]
    has_more: bool
    filtros_aplicados: Dict[str, Any]


class EstatisticasResponse(BaseModel):
    """Estatísticas gerais dos processos."""
    total_processos: int
    por_tribunal: Dict[str, int]
    por_ano: Dict[int, int]
    ultima_atualizacao: Optional[Any]


class ColetaHistoricoItem(BaseModel):
    """Item do histórico de coletas."""
    id: UUID
    tribunal: str
    inicio: Any
    fim: Optional[Any]
    duracao_segundos: Optional[int]
    status: str
    total_processos_encontrados: int
    total_processos_novos: int
    total_processos_atualizados: int


class ColetaTriggerResponse(BaseModel):
    """Resposta do trigger de coleta."""
    mensagem: str
    task_id: Optional[str] = None
    tribunal: str


# ==============================================================================
# Endpoints de consulta
# ==============================================================================

@router.get("", response_model=ProcessosListResponse)
async def listar_processos(
    tribunal: Optional[str] = Query(None, description="Tribunal (TJSP, PJE, TJRJ)"),
    numero_processo: Optional[str] = Query(None, description="Número do processo (busca parcial)"),
    classe: Optional[str] = Query(None, description="Classe do processo"),
    comarca: Optional[str] = Query(None, description="Comarca"),
    uf: Optional[str] = Query(None, description="UF (SP, RJ)"),
    data_inicio: Optional[date] = Query(None, description="Data de distribuição inicial (YYYY-MM-DD)"),
    data_fim: Optional[date] = Query(None, description="Data de distribuição final (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500, description="Máximo de resultados"),
    offset: int = Query(0, ge=0, description="Número de resultados para pular (paginação)"),
) -> ProcessosListResponse:
    """
    Lista processos com filtros opcionais e paginação.

    Exemplos:
    - Todos os processos: GET /processos
    - Processos do TJSP: GET /processos?tribunal=TJSP
    - Processos de 2024: GET /processos?data_inicio=2024-01-01&data_fim=2024-12-31
    - Paginação: GET /processos?limit=100&offset=100
    """
    filtros = {}
    if tribunal:
        filtros["tribunal"] = tribunal
    if numero_processo:
        filtros["numero_processo"] = numero_processo
    if classe:
        filtros["classe"] = classe
    if comarca:
        filtros["comarca"] = comarca
    if uf:
        filtros["uf"] = uf
    if data_inicio:
        filtros["data_inicio"] = data_inicio
    if data_fim:
        filtros["data_fim"] = data_fim

    resultado = await processos_db.buscar_processos(filtros, limit, offset)

    processos = [ProcessoResumo(**p) for p in resultado["processos"]]

    return ProcessosListResponse(
        total=resultado["total"],
        processos=processos,
        has_more=resultado["has_more"],
        filtros_aplicados=filtros
    )


@router.get("/{numero_processo}", response_model=ProcessoCompleto)
async def obter_processo_detalhes(
    numero_processo: str,
    tribunal: Optional[str] = Query(None, description="Tribunal específico (opcional)"),
) -> ProcessoCompleto:
    """
    Obtém detalhes completos de um processo pelo número.

    Exemplos:
    - GET /processos/0000000-00.0000.0.00.0000
    - GET /processos/0000000-00.0000.0.00.0000?tribunal=TJSP
    """
    processo = await processos_db.buscar_processo_por_numero(numero_processo, tribunal)

    if not processo:
        raise HTTPException(
            status_code=404,
            detail=f"Processo {numero_processo} não encontrado"
        )

    return ProcessoCompleto(**processo)


@router.get("/stats/geral", response_model=EstatisticasResponse)
async def obter_estatisticas() -> EstatisticasResponse:
    """
    Retorna estatísticas gerais dos processos armazenados.

    Inclui:
    - Total de processos
    - Distribuição por tribunal
    - Distribuição por ano de distribuição
    - Data da última atualização
    """
    stats = await processos_db.obter_estatisticas()

    return EstatisticasResponse(
        total_processos=stats["total_processos"],
        por_tribunal=stats["por_tribunal"],
        por_ano=stats["por_ano"],
        ultima_atualizacao=stats["ultima_atualizacao"]
    )


# ==============================================================================
# Endpoints de coleta (trigger manual)
# ==============================================================================

@router.post("/coletas/trigger", response_model=ColetaTriggerResponse)
async def trigger_coleta(
    tribunal: str = Query("TODOS", description="Tribunal (TJSP, PJE, TJRJ ou TODOS)")
) -> ColetaTriggerResponse:
    """
    Aciona manualmente uma coleta de processos.

    Parâmetros:
    - tribunal: TJSP, PJE, TJRJ ou TODOS (padrão)

    A coleta roda em background via Celery.
    Use GET /processos/coletas/historico para acompanhar o progresso.
    """
    tribunal_upper = tribunal.upper()

    # Mapear tribunal para nome da task
    task_names = {
        "TODOS": "coleta.todos_tribunais",
        "TJSP": "coleta.tjsp",
        "PJE": "coleta.pje",
        "TJRJ": "coleta.tjrj",
    }

    task_name = task_names.get(tribunal_upper)
    if not task_name:
        raise HTTPException(
            status_code=400,
            detail=f"Tribunal inválido: {tribunal}. Use TJSP, PJE, TJRJ ou TODOS."
        )

    # Enviar task via Celery
    task = celery_app.send_task(task_name)

    return ColetaTriggerResponse(
        mensagem=f"Coleta de {tribunal_upper} iniciada com sucesso",
        task_id=task.id,
        tribunal=tribunal_upper
    )


@router.get("/coletas/historico", response_model=List[ColetaHistoricoItem])
async def obter_historico_coletas(
    tribunal: Optional[str] = Query(None, description="Filtrar por tribunal (opcional)"),
    limit: int = Query(10, ge=1, le=100, description="Máximo de registros"),
) -> List[ColetaHistoricoItem]:
    """
    Retorna histórico de coletas executadas.

    Exemplos:
    - Últimas 10 coletas: GET /processos/coletas/historico
    - Últimas 20 coletas do TJSP: GET /processos/coletas/historico?tribunal=TJSP&limit=20
    """
    historico = await processos_db.obter_historico_coletas(tribunal, limit)

    return [ColetaHistoricoItem(**item) for item in historico]


@router.get("/coletas/ultima/{tribunal}", response_model=Optional[ColetaHistoricoItem])
async def obter_ultima_coleta(tribunal: str) -> Optional[ColetaHistoricoItem]:
    """
    Retorna a última coleta bem-sucedida de um tribunal.

    Útil para saber quando foi a última atualização.
    """
    coleta = await processos_db.obter_ultima_coleta(tribunal.upper())

    if not coleta:
        return None

    return ColetaHistoricoItem(**coleta)
