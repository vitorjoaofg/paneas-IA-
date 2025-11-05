from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


class ProcessoResumoTJSP(BaseModel):
    numeroProcesso: str
    processoCodigo: Optional[str]
    foroId: Optional[str]
    linkPublico: str
    tipoParticipacao: Optional[str]
    partesRelacionadas: list[str] = Field(default_factory=list)
    classe: Optional[str]
    assunto: Optional[str]
    distribuicao: Optional[str]
    pagina: int = Field(description="Página da consulta de onde o processo foi extraído.")
    contrapartesEncontradas: list[str] = Field(
        default_factory=list,
        description="Lista de partes que corresponderam ao filtro 'contra_parte' (quando aplicado).",
    )


class TJSPProcessoQuery(BaseModel):
    """Input payload accepted by the scraping tool."""

    numero_processo: Optional[str] = Field(
        default=None,
        description="Número completo do processo (formato CNJ ou somente dígitos).",
        example="1014843-66.2025.8.26.0554",
    )
    nome_parte: Optional[str] = Field(default=None, description="Nome da parte.")
    nome_completo: bool = Field(
        default=False,
        description="Pesquisar por nome completo (evita resultados com nomes similares).",
    )
    documento_parte: Optional[str] = Field(
        default=None,
        description="CPF ou CNPJ da parte.",
        validation_alias=AliasChoices("documento_parte", "cnpj"),
    )
    nome_advogado: Optional[str] = Field(default=None, description="Nome completo do advogado.")
    numero_oab: Optional[str] = Field(default=None, description="Número da OAB.")
    numero_precatoria: Optional[str] = Field(default=None, description="Número da carta precatória na origem.")
    numero_documento_delegacia: Optional[str] = Field(
        default=None,
        description="Número do documento na delegacia.",
    )
    numero_cda: Optional[str] = Field(default=None, description="Número da CDA.")
    foro: Optional[str] = Field(
        default=None,
        description="Código do foro (ex.: 554). Se não informado, a consulta utilizará 'Todos os foros'.",
    )
    uf: Literal["SP"] = Field(default="SP", description="UF do tribunal consultado (somente SP suportado).")

    @model_validator(mode="before")
    def sanitize_numero_processo(cls, values: dict) -> dict:
        numero = values.get("numero_processo")
        if numero:
            digits = "".join(ch for ch in str(numero) if ch.isdigit())
            if len(digits) not in {20, 25}:  # 20 dígitos (CNJ) ou 25 incluindo formatação
                raise ValueError("Número do processo inválido.")
            values["numero_processo"] = digits
        return values

    @model_validator(mode="after")
    def ensure_at_least_one_filter(cls, model: "TJSPProcessoQuery") -> "TJSPProcessoQuery":
        filters = [
            model.numero_processo,
            model.nome_parte,
            model.documento_parte,
            model.nome_advogado,
            model.numero_oab,
            model.numero_precatoria,
            model.numero_documento_delegacia,
            model.numero_cda,
        ]
        if not any(filters):
            raise ValueError("É necessário informar ao menos um critério de busca.")
        return model


class Movimento(BaseModel):
    data: date
    descricao: str


class ProcessoTJSP(BaseModel):
    uf: Literal["SP"]
    numeroProcesso: str
    valorCausa: Optional[str]
    tipoJuizo: Optional[str]
    classe: Optional[str]
    assunto: Optional[str]
    foro: Optional[str]
    vara: Optional[str]
    juiz: Optional[str]
    requerente: Optional[str]
    advogadoConsumidor: Optional[str]
    dataAudiencia: Optional[str]
    situacaoProcessual: Optional[str]
    inicio: Optional[str]
    ultima_atualizacao: Optional[str]
    linkPublico: str
    movimentos: list[Movimento] = Field(default_factory=list)


class TJSPProcessoListQuery(TJSPProcessoQuery):
    contra_parte: Optional[str] = Field(
        default=None,
        description="Texto para filtrar processos em que a parte contrária contenha esse termo (case insensitive).",
    )
    max_paginas: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Número máximo de páginas da listagem a percorrer (cada página retorna até 25 processos).",
    )
    max_processos: Optional[int] = Field(
        default=None,
        ge=1,
        description="Limite máximo de processos a retornar após aplicar os filtros opcionais.",
    )


class TJSPProcessoListResponse(BaseModel):
    total_processos: Optional[int] = Field(
        default=None,
        description="Total de processos reportados pelo TJSP para a consulta informada.",
    )
    paginas_consultadas: int = Field(description="Quantidade de páginas navegadas na listagem do TJSP.")
    possui_mais_paginas: bool = Field(
        description="Indica se ainda existem mais páginas disponíveis além das consultadas.",
    )
    filtro_contra_parte: Optional[str] = Field(
        default=None,
        description="Valor aplicado no filtro de contraparte, se fornecido.",
    )
    processos: list[ProcessoResumoTJSP] = Field(default_factory=list)


# PJE Models
class ProcessoResumoPJE(BaseModel):
    numeroProcesso: str
    classe: Optional[str] = None
    partes: Optional[str] = None
    ultimaMovimentacao: Optional[str] = None
    linkPublico: str


class AdvogadoPJE(BaseModel):
    nome: str
    situacao: Optional[str] = None


class PartePJE(BaseModel):
    nome: str
    documento: Optional[str] = None
    advogados: list[AdvogadoPJE] = Field(default_factory=list)


class MovimentoPJE(BaseModel):
    data: str
    descricao: str


class ProcessoPJE(BaseModel):
    numeroProcesso: str
    classe: Optional[str] = None
    dataDistribuicao: Optional[str] = None
    orgaoJulgador: Optional[str] = None
    secaoJudiciaria: Optional[str] = None
    assuntos: list[str] = Field(default_factory=list)
    poloAtivo: list[PartePJE] = Field(default_factory=list)
    poloPassivo: list[PartePJE] = Field(default_factory=list)
    situacao: Optional[str] = None
    linkPublico: str
    movimentos: list[MovimentoPJE] = Field(default_factory=list)


class PJEProcessoQuery(BaseModel):
    """Input payload accepted by the PJE scraping tool."""

    numero_processo: Optional[str] = Field(
        default=None,
        description="Número completo do processo (formato CNJ).",
        example="0000786-87.1984.4.01.3800",
    )
    nome_parte: Optional[str] = Field(default=None, description="Nome da parte.")
    nome_advogado: Optional[str] = Field(default=None, description="Nome do advogado.")
    documento_parte: Optional[str] = Field(default=None, description="CPF ou CNPJ da parte.")

    @model_validator(mode="after")
    def ensure_at_least_one_filter(cls, model: "PJEProcessoQuery") -> "PJEProcessoQuery":
        filters = [
            model.numero_processo,
            model.nome_parte,
            model.documento_parte,
            model.nome_advogado,
        ]
        if not any(filters):
            raise ValueError("É necessário informar ao menos um critério de busca.")
        return model


class PJEProcessoListResponse(BaseModel):
    total_processos: Optional[int] = Field(
        default=None,
        description="Total de processos reportados pelo PJE para a consulta informada.",
    )
    processos: list[ProcessoResumoPJE] = Field(default_factory=list)
