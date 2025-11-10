from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

MOVEMENT_LINE_PATTERN = re.compile(
    r"^(?P<data>\d{2}/\d{2}/\d{4})(?:\s+(?P<hora>\d{2}:\d{2}:\d{2}))?\s*-\s*(?P<descricao>.+)$"
)

PARTICIPANTE_PATTERN = re.compile(
    r"^(?P<nome>.+?)\s+-\s+(?:CPF|CNPJ):\s*(?P<documento>[\d./-]+).*\((?P<papel>[^)]+)\)",
    re.IGNORECASE,
)


def _parse_dados_completos(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    return {}


def _split_lines(text: str) -> List[str]:
    cleaned = text.replace("\xa0", " ").strip()
    if not cleaned:
        return []
    parts = []
    for line in cleaned.splitlines():
        val = line.strip().strip("«»").strip()
        if val:
            parts.append(val)
    return parts


def _iter_candidate_lines(entry: Any) -> Iterable[str]:
    if entry is None:
        return

    if isinstance(entry, list):
        for item in entry:
            yield from _iter_candidate_lines(item)
        return

    if isinstance(entry, dict):
        fields = [entry.get("data"), entry.get("descricao"), entry.get("texto")]
    else:
        fields = [entry]

    for field in fields:
        if field is None:
            continue
        for line in _split_lines(str(field)):
            yield line


def _parse_movement_line(line: str) -> Dict[str, str] | None:
    match = MOVEMENT_LINE_PATTERN.match(line)
    if not match:
        return None

    data = match.group("data")
    hora = match.group("hora")
    descricao = match.group("descricao").strip()

    try:
        if hora:
            dt = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M:%S")
        else:
            dt = datetime.strptime(data, "%d/%m/%Y")
    except ValueError:
        return None

    return {
        "data": dt.replace(microsecond=0).isoformat(),
        "descricao": descricao,
    }


def _sanitize_tjrj_movements(dados: Dict[str, Any]) -> List[Dict[str, str]]:
    sources: List[Any] = []
    raw_movs = dados.get("movimentos")
    if isinstance(raw_movs, list):
        sources.extend(raw_movs)

    detalhes = dados.get("detalhesPublicos") or {}
    detalhes_movs = detalhes.get("movimentacoes")
    if isinstance(detalhes_movs, list):
        sources.extend(detalhes_movs)

    cleaned: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    for entry in sources:
        for line in _iter_candidate_lines(entry):
            parsed = _parse_movement_line(line)
            if not parsed:
                continue
            key = (parsed["data"], parsed["descricao"])
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(parsed)

    cleaned.sort(key=lambda item: item["data"])
    return cleaned


def _normalize_part_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return value
    return []


def _append_simple_part(partes: List[Dict[str, Any]], nome: Any, papel: str) -> None:
    if not nome:
        return
    nome_lower = str(nome).strip().lower()
    if not nome_lower:
        return
    for existing in partes:
        if str(existing.get("nome", "")).strip().lower() == nome_lower:
            return
    partes.append({"nome": str(nome).strip(), "papel": papel})


def _infer_partes_from_text(dados: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    detalhes = dados.get("detalhesPublicos") or {}
    movimentacoes = detalhes.get("movimentacoes")
    if not isinstance(movimentacoes, list):
        return [], []

    ativos: List[Dict[str, Any]] = []
    passivos: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()

    for entry in movimentacoes:
        for line in _iter_candidate_lines(entry):
            match = PARTICIPANTE_PATTERN.match(line)
            if not match:
                continue

            papel = match.group("papel").strip().lower()
            nome = match.group("nome").strip()
            documento = match.group("documento").strip()
            registro = {
                "nome": nome,
                "documento": re.sub(r"\D", "", documento) or documento,
                "papel": papel,
            }
            key = (registro["nome"], registro["documento"], registro["papel"])
            if key in seen:
                continue
            seen.add(key)

            if "autor" in papel:
                ativos.append(registro)
            elif "réu" in papel or "reu" in papel:
                passivos.append(registro)

    return ativos, passivos


def _dedupe_partes(partes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str | None, str | None, str | None]] = set()
    deduped: List[Dict[str, Any]] = []
    for parte in partes:
        key = (parte.get("nome"), parte.get("documento"), parte.get("papel"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(parte)
    return deduped


def _infer_tjrj_polos(dados: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    polo_ativo = _normalize_part_list(dados.get("poloAtivo"))
    polo_passivo = _normalize_part_list(dados.get("poloPassivo"))

    if polo_ativo and polo_passivo:
        return _dedupe_partes(polo_ativo), _dedupe_partes(polo_passivo)

    parsed_ativos, parsed_passivos = _infer_partes_from_text(dados)

    if not polo_ativo:
        polo_ativo = parsed_ativos.copy()
        if not polo_ativo:
            _append_simple_part(polo_ativo, dados.get("autor"), "autor")

    if not polo_passivo:
        polo_passivo = parsed_passivos.copy()
        if not polo_passivo:
            _append_simple_part(polo_passivo, dados.get("reu"), "réu")

    return _dedupe_partes(polo_ativo), _dedupe_partes(polo_passivo)


def consolidar_dados_processo(processo: Dict[str, Any]) -> Dict[str, Any]:
    dados_completos = _parse_dados_completos(processo.get("dados_completos"))
    processo["dados_completos"] = dados_completos

    tribunal = (processo.get("tribunal") or "").upper()

    if tribunal == "TJRJ":
        processo["movimentos"] = _sanitize_tjrj_movements(dados_completos)
        dados_completos["movimentos"] = processo["movimentos"]

        polo_ativo, polo_passivo = _infer_tjrj_polos(dados_completos)
        processo["polo_ativo"] = polo_ativo
        processo["polo_passivo"] = polo_passivo
        dados_completos["poloAtivo"] = polo_ativo
        dados_completos["poloPassivo"] = polo_passivo
    else:
        processo["movimentos"] = _normalize_part_list(dados_completos.get("movimentos"))
        processo["polo_ativo"] = _normalize_part_list(dados_completos.get("poloAtivo"))
        processo["polo_passivo"] = _normalize_part_list(dados_completos.get("poloPassivo"))
        dados_completos["movimentos"] = processo["movimentos"]
        dados_completos["poloAtivo"] = processo["polo_ativo"]
        dados_completos["poloPassivo"] = processo["polo_passivo"]

    processo["audiencias"] = _normalize_part_list(dados_completos.get("audiencias"))
    dados_completos["audiencias"] = processo["audiencias"]

    processo["publicacoes"] = _normalize_part_list(dados_completos.get("publicacoes"))
    dados_completos["publicacoes"] = processo["publicacoes"]

    processo["documentos"] = _normalize_part_list(dados_completos.get("documentos"))
    dados_completos["documentos"] = processo["documentos"]

    detalhes_publicos = dados_completos.get("detalhesPublicos")
    if isinstance(detalhes_publicos, dict):
        detalhes_publicos["movimentacoes"] = processo["movimentos"]

    return processo


__all__ = ["consolidar_dados_processo"]
