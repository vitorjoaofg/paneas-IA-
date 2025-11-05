"""
Tasks Celery para coleta automatizada de processos judiciais.
Coleta processos de TJSP, PJE e TJRJ para o cliente "Claro" e variações.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from celery import group

from celery_app import celery_app
from services import processos_db
from services.scrapper_client import (
    listar_processos,
    listar_processos_pje,
    listar_processos_tjrj,
)

logger = logging.getLogger(__name__)

# Variações do nome "Claro" para buscar
CLARO_VARIACOES = ["Claro", "Claro SA", "Claro S/A", "Claro S.A."]


# ==============================================================================
# Tasks individuais por tribunal
# ==============================================================================

@celery_app.task(name="coleta.tjsp", bind=True)
def coletar_tjsp(self) -> Dict[str, Any]:
    """
    Coleta processos do TJSP para o cliente Claro.
    Tenta todas as variações de nome e consolida resultados.
    """
    return asyncio.run(_coletar_tjsp_async())


async def _coletar_tjsp_async() -> Dict[str, Any]:
    """
    Lógica assíncrona de coleta TJSP.
    """
    tribunal = "TJSP"
    coleta_id = await processos_db.registrar_inicio_coleta(tribunal)

    logger.info(f"[TJSP] Iniciando coleta para Claro (ID: {coleta_id})")

    try:
        todos_processos: List[Dict[str, Any]] = []
        processos_vistos = set()  # Para deduplicar por número

        # Tentar cada variação de nome
        for nome_variacao in CLARO_VARIACOES:
            logger.info(f"[TJSP] Buscando processos para '{nome_variacao}'...")

            try:
                response = await listar_processos({
                    "nome_parte": nome_variacao,
                    "nome_completo": True,  # Pesquisar por nome completo
                    "max_paginas": 10,  # Buscar até 10 páginas (250 processos)
                    "max_processos": 500,  # Limitar a 500 por variação
                })

                processos = response.get("processos", [])
                logger.info(f"[TJSP] Encontrados {len(processos)} processos para '{nome_variacao}'")

                # Deduplicar
                for proc in processos:
                    numero = proc.get("numeroProcesso")
                    if numero and numero not in processos_vistos:
                        processos_vistos.add(numero)
                        todos_processos.append(proc)

            except Exception as e:
                logger.error(f"[TJSP] Erro ao buscar '{nome_variacao}': {e}")
                continue

        logger.info(f"[TJSP] Total de processos únicos encontrados: {len(todos_processos)}")

        # Salvar processos no banco
        stats = await _salvar_processos_batch(todos_processos, tribunal)

        # Registrar fim da coleta
        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="sucesso",
            stats=stats
        )

        logger.info(f"[TJSP] Coleta concluída: {stats}")
        return stats

    except Exception as e:
        erro_msg = str(e)
        erro_traceback = traceback.format_exc()
        logger.error(f"[TJSP] Erro fatal na coleta: {erro_msg}\n{erro_traceback}")

        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="erro",
            erro=erro_msg,
            erro_traceback=erro_traceback
        )

        raise


@celery_app.task(name="coleta.pje", bind=True)
def coletar_pje(self) -> Dict[str, Any]:
    """
    Coleta processos do PJE para o cliente Claro.
    """
    return asyncio.run(_coletar_pje_async())


async def _coletar_pje_async() -> Dict[str, Any]:
    """
    Lógica assíncrona de coleta PJE.
    """
    tribunal = "PJE"
    coleta_id = await processos_db.registrar_inicio_coleta(tribunal)

    logger.info(f"[PJE] Iniciando coleta para Claro (ID: {coleta_id})")

    try:
        # PJE já tem lógica interna de variações de nome
        # Basta chamar com "Claro" que ele tenta automaticamente
        logger.info(f"[PJE] Buscando processos para 'Claro'...")

        response = await listar_processos_pje({
            "nome_parte": "Claro"
        })

        processos = response.get("processos", [])
        logger.info(f"[PJE] Encontrados {len(processos)} processos")

        # Salvar processos no banco
        stats = await _salvar_processos_batch(processos, tribunal)

        # Registrar fim da coleta
        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="sucesso",
            stats=stats
        )

        logger.info(f"[PJE] Coleta concluída: {stats}")
        return stats

    except Exception as e:
        erro_msg = str(e)
        erro_traceback = traceback.format_exc()
        logger.error(f"[PJE] Erro fatal na coleta: {erro_msg}\n{erro_traceback}")

        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="erro",
            erro=erro_msg,
            erro_traceback=erro_traceback
        )

        raise


@celery_app.task(name="coleta.tjrj", bind=True)
def coletar_tjrj(self) -> Dict[str, Any]:
    """
    Coleta processos do TJRJ para o cliente Claro.
    """
    return asyncio.run(_coletar_tjrj_async())


async def _coletar_tjrj_async() -> Dict[str, Any]:
    """
    Lógica assíncrona de coleta TJRJ.
    """
    tribunal = "TJRJ"
    coleta_id = await processos_db.registrar_inicio_coleta(tribunal)

    logger.info(f"[TJRJ] Iniciando coleta para Claro (ID: {coleta_id})")

    try:
        # TJRJ também tem lógica interna de variações de nome
        logger.info(f"[TJRJ] Buscando processos para 'Claro'...")

        response = await listar_processos_tjrj({
            "nome_parte": "Claro"
            # Removidos instancia e competencia - causavam retorno vazio
        })

        processos = response.get("processos", [])
        logger.info(f"[TJRJ] Encontrados {len(processos)} processos")

        # Salvar processos no banco
        stats = await _salvar_processos_batch(processos, tribunal)

        # Registrar fim da coleta
        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="sucesso",
            stats=stats
        )

        logger.info(f"[TJRJ] Coleta concluída: {stats}")
        return stats

    except Exception as e:
        erro_msg = str(e)
        erro_traceback = traceback.format_exc()
        logger.error(f"[TJRJ] Erro fatal na coleta: {erro_msg}\n{erro_traceback}")

        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="erro",
            erro=erro_msg,
            erro_traceback=erro_traceback
        )

        raise


# ==============================================================================
# Task orquestradora
# ==============================================================================

@celery_app.task(name="coleta.todos_tribunais", bind=True)
def coletar_todos_tribunais(self) -> Dict[str, Any]:
    """
    Coleta processos de todos os tribunais em paralelo.
    Orquestra as 3 tasks individuais e consolida resultados.
    """
    return asyncio.run(_coletar_todos_tribunais_async())


async def _coletar_todos_tribunais_async() -> Dict[str, Any]:
    """
    Lógica assíncrona da coleta de todos os tribunais.
    """
    coleta_id = await processos_db.registrar_inicio_coleta("TODOS")

    logger.info(f"[TODOS] Iniciando coleta de todos os tribunais (ID: {coleta_id})")

    try:
        inicio = datetime.now()

        # Executar as 3 tasks em paralelo usando group
        job = group(
            coletar_tjsp.s(),
            coletar_pje.s(),
            coletar_tjrj.s(),
        )

        # Aplicar e aguardar resultados
        result = job.apply_async()
        resultados = result.get(timeout=600)  # 10 minutos de timeout

        # Consolidar estatísticas
        total_encontrados = sum(r.get("total_processos_encontrados", 0) for r in resultados)
        total_novos = sum(r.get("total_processos_novos", 0) for r in resultados)
        total_atualizados = sum(r.get("total_processos_atualizados", 0) for r in resultados)

        stats = {
            "total_processos_encontrados": total_encontrados,
            "total_processos_novos": total_novos,
            "total_processos_atualizados": total_atualizados,
            "por_tribunal": {
                "TJSP": resultados[0],
                "PJE": resultados[1],
                "TJRJ": resultados[2],
            },
            "duracao_segundos": (datetime.now() - inicio).total_seconds(),
        }

        # Registrar fim da coleta
        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="sucesso",
            stats=stats
        )

        logger.info(f"[TODOS] Coleta concluída: {stats}")
        return stats

    except Exception as e:
        erro_msg = str(e)
        erro_traceback = traceback.format_exc()
        logger.error(f"[TODOS] Erro fatal na coleta: {erro_msg}\n{erro_traceback}")

        await processos_db.registrar_fim_coleta(
            coleta_id,
            status="erro",
            erro=erro_msg,
            erro_traceback=erro_traceback
        )

        raise


# ==============================================================================
# Funções auxiliares
# ==============================================================================

async def _salvar_processos_batch(processos: List[Dict[str, Any]], tribunal: str) -> Dict[str, Any]:
    """
    Salva uma lista de processos no banco e retorna estatísticas.
    """
    total_encontrados = len(processos)
    total_novos = 0
    total_atualizados = 0
    total_ignorados = 0
    total_erros = 0

    for proc in processos:
        try:
            # Tentar salvar (função detecta se é novo ou atualização)
            processo_id = await processos_db.salvar_processo(proc, tribunal)

            # Como não temos como saber se foi INSERT ou UPDATE na resposta,
            # vamos consultar o created_at
            processo_salvo = await processos_db.buscar_processo_por_numero(
                proc.get("numeroProcesso"),
                tribunal
            )

            if processo_salvo:
                # Se created_at é recente (menos de 10 segundos), é novo
                created_at = processo_salvo["created_at"]
                updated_at = processo_salvo["updated_at"]

                # Comparar timestamps
                if (updated_at - created_at).total_seconds() < 10:
                    total_novos += 1
                else:
                    total_atualizados += 1

        except Exception as e:
            logger.error(f"Erro ao salvar processo {proc.get('numeroProcesso')}: {e}")
            total_erros += 1
            continue

    return {
        "total_processos_encontrados": total_encontrados,
        "total_processos_novos": total_novos,
        "total_processos_atualizados": total_atualizados,
        "total_processos_ignorados": total_ignorados,
        "total_processos_com_erro": total_erros,
    }
