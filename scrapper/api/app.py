from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .models import ProcessoTJSP, TJSPProcessoListQuery, TJSPProcessoListResponse, TJSPProcessoQuery
from .scraper import fetch_tjsp_process, fetch_tjsp_process_list


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    yield


app = FastAPI(title="Scrapper API", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/tools/tjsp_consulta_processo", response_model=ProcessoTJSP)
async def tools_consulta_processo(payload: TJSPProcessoQuery) -> ProcessoTJSP:
    settings: Settings = app.state.settings
    try:
        return await fetch_tjsp_process(payload, settings=settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao consultar processo: {exc}") from exc


@app.post("/v1/processos/consulta", response_model=ProcessoTJSP)
async def consulta_processo(payload: TJSPProcessoQuery) -> ProcessoTJSP:
    return await tools_consulta_processo(payload)


@app.post("/tools/tjsp_listar_processos", response_model=TJSPProcessoListResponse)
async def tools_listar_processos(payload: TJSPProcessoListQuery) -> TJSPProcessoListResponse:
    settings: Settings = app.state.settings
    try:
        return await fetch_tjsp_process_list(payload, settings=settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao listar processos: {exc}") from exc


@app.post("/v1/processos/listar", response_model=TJSPProcessoListResponse)
async def listar_processos(payload: TJSPProcessoListQuery) -> TJSPProcessoListResponse:
    return await tools_listar_processos(payload)


@app.get("/tools")
async def tools_manifest() -> Any:
    settings: Settings = app.state.settings
    try:
        with open(settings.tools_manifest_path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Manifesto de ferramentas não encontrado.") from exc
