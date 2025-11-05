from fastapi import APIRouter

from schemas.scrapper import (
    ProcessoTJSP,
    TJSPProcessoListQuery,
    TJSPProcessoListResponse,
    TJSPProcessoQuery,
    PJEProcessoQuery,
    PJEProcessoListResponse,
    ProcessoPJE,
)
from services import scrapper_client

router = APIRouter(prefix="/api/v1", tags=["scrapper"])


@router.post("/scrapper/processos/consulta", response_model=ProcessoTJSP)
async def consulta_processo(payload: TJSPProcessoQuery) -> ProcessoTJSP:
    resultado = await scrapper_client.consulta_processo(
        payload.model_dump(mode="json", exclude_none=True, by_alias=True)
    )
    return ProcessoTJSP.model_validate(resultado)


@router.post("/scrapper/processos/listar", response_model=TJSPProcessoListResponse)
async def listar_processos(payload: TJSPProcessoListQuery) -> TJSPProcessoListResponse:
    resultado = await scrapper_client.listar_processos(
        payload.model_dump(mode="json", exclude_none=True, by_alias=True)
    )
    return TJSPProcessoListResponse.model_validate(resultado)


@router.post("/scrapper/processos/pje/listar", response_model=PJEProcessoListResponse)
async def listar_processos_pje(payload: PJEProcessoQuery) -> PJEProcessoListResponse:
    resultado = await scrapper_client.listar_processos_pje(
        payload.model_dump(mode="json", exclude_none=True, by_alias=True)
    )
    return PJEProcessoListResponse.model_validate(resultado)


@router.post("/scrapper/processos/pje/consulta", response_model=ProcessoPJE)
async def consulta_processo_pje(payload: dict) -> ProcessoPJE:
    resultado = await scrapper_client.consulta_processo_pje(payload)
    return ProcessoPJE.model_validate(resultado)


@router.get("/scrapper/tools")
async def manifest_tools() -> dict:
    return await scrapper_client.obter_manifesto()
