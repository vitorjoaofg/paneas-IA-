from fastapi import APIRouter

from schemas.scrapper import (
    ProcessoTJSP,
    TJSPProcessoListQuery,
    TJSPProcessoListResponse,
    TJSPProcessoQuery,
    PJEProcessoQuery,
    PJEProcessoListResponse,
    ProcessoPJE,
    TJRJProcessoQuery,
    TJRJProcessoListResponse,
    ProcessoTJRJ,
)
from services import scrapper_client, processos_db

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


@router.post("/scrapper/processos/tjrj/listar", response_model=TJRJProcessoListResponse)
async def listar_processos_tjrj(payload: TJRJProcessoQuery) -> TJRJProcessoListResponse:
    resultado = await scrapper_client.listar_processos_tjrj(
        payload.model_dump(mode="json", exclude_none=True, by_alias=True)
    )
    return TJRJProcessoListResponse.model_validate(resultado)


@router.post("/scrapper/processos/tjrj/consulta", response_model=ProcessoTJRJ)
async def consulta_processo_tjrj(payload: dict) -> ProcessoTJRJ:
    resultado = await scrapper_client.consulta_processo_tjrj(payload)
    return ProcessoTJRJ.model_validate(resultado)


@router.get("/scrapper/tools")
async def manifest_tools() -> dict:
    return await scrapper_client.obter_manifesto()


@router.post("/scrapper/processos/tjrj-pje-auth/test-page3-save")
async def test_tjrj_pje_auth_page3_and_save(payload: dict) -> dict:
    """
    Testa extração de processo da página 3 do TJRJ PJE autenticado E salva no banco.
    Payload: {"cpf": "...", "senha": "...", "nome_parte": "Claro S.A"}
    """
    # 1. Chamar scrapper para extrair dados
    resultado = await scrapper_client.test_tjrj_pje_auth_page3(payload)
    processo = ProcessoTJRJ.model_validate(resultado)

    # 2. Salvar no banco de dados
    processo_dict = processo.model_dump(mode="json")
    processo_id = await processos_db.salvar_processo(processo_dict, tribunal="TJRJ")

    # 3. Retornar processo + ID no banco
    return {
        "processo": processo_dict,
        "saved_to_db": True,
        "processo_id": str(processo_id),
        "message": f"Processo {processo.numeroProcesso} salvo com sucesso no banco"
    }
