from __future__ import annotations

import re
from typing import Dict, Optional, Type

from .base import DocumentInterpreter
from .boleto import BoletoInterpreter
from .cnh import CnhInterpreter
from .generic import GenericInterpreter
from .rg import RgInterpreter

_REGISTRY: Dict[str, Type[DocumentInterpreter]] = {
    "generic": GenericInterpreter,
    "cnh": CnhInterpreter,
    "rg": RgInterpreter,
    "boleto": BoletoInterpreter,
}

_ALIASES: Dict[str, str] = {
    "driver_license": "cnh",
    "habilitacao": "cnh",
    "cnh_digital": "cnh",
    "identity": "rg",
    "id": "rg",
}


def get_interpreter(doc_type: Optional[str] = None, *, text: Optional[str] = None) -> DocumentInterpreter:
    resolved = _resolve_doc_type(doc_type, text)
    interpreter_cls = _REGISTRY.get(resolved, GenericInterpreter)
    return interpreter_cls()


def detect_document_type_from_text(text: str) -> Optional[str]:
    scores = {
        "cnh": _score_cnh(text),
        "rg": _score_rg(text),
        "boleto": _score_boleto(text),
    }
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    # Require at least a minimal score to avoid random matches
    if best_score < 2:
        return None
    # Tie-breaker priority: CNH > RG > boleto
    sorted_candidates = sorted(
        scores.items(),
        key=lambda item: (item[1], 1 if item[0] == "cnh" else 0 if item[0] == "rg" else -1),
        reverse=True,
    )
    top_score = sorted_candidates[0][1]
    if top_score == 0:
        return None
    # Ensure we only return doc types matching the best score
    best = [doc for doc, score in sorted_candidates if score == top_score]
    return best[0] if best else None


def _resolve_doc_type(doc_type: Optional[str], text: Optional[str]) -> str:
    if doc_type:
        key = doc_type.strip().lower()
        resolved = _ALIASES.get(key, key)
        if resolved in _REGISTRY:
            return resolved
    if text:
        detected = detect_document_type_from_text(text)
        if detected:
            return detected
    return "generic"


def _score_cnh(text: str) -> int:
    normalized = text.lower()
    score = 0
    if "carteira nacional de habil" in normalized:
        score += 4
    if "carteira de habilit" in normalized or "permissão para dirigir" in normalized:
        score += 2
    if "habilita" in normalized or "condutor" in normalized:
        score += 2
    if "proibido plastificar" in normalized or "proibidoplastificar" in normalized:
        score += 1
    if "ssp/" in normalized or "detran" in normalized:
        score += 1
    if _count_dates(text) >= 3:
        score += 2
    if _has_pattern(r"\d{5,}\s*ssp/[a-z]{2}", normalized):
        score += 2
    if "1ª" in normalized and "habil" in normalized:
        score += 2
    if "validade" in normalized:
        score += 1
    digital_keywords = [
        "cnh digital",
        "qr-code",
        "documento assinado",
        "assinador serpro",
        "serpro",
        "denatran",
        "renach",
        "serpro/senatran",
    ]
    for keyword in digital_keywords:
        if keyword in normalized:
            score += 3
    return score


def _score_rg(text: str) -> int:
    normalized = text.lower()
    score = 0
    if "carteira de identidade" in normalized:
        score += 4
    if "registro geral" in normalized or "rg " in normalized or normalized.startswith("rg"):
        score += 2
    if "identidade" in normalized:
        score += 1
    if "ssp/" in normalized or "instituto de identificação" in normalized:
        score += 1
    if "proibido plastificar" in normalized:
        score += 1
    return score


def _score_boleto(text: str) -> int:
    normalized = text.lower()
    score = 0
    for keyword in ("linha digitavel", "linha digitável", "pagador", "cedente", "nosso número", "nosso numero", "sacado"):
        if keyword in normalized:
            score += 2
    if "boleto" in normalized:
        score += 3
    if _has_pattern(r"\d{11,}", normalized):
        score += 1
    return score


def _count_dates(text: str) -> int:
    date_regex = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
    return len(date_regex.findall(text))


def _has_pattern(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


__all__ = [
    "DocumentInterpreter",
    "GenericInterpreter",
    "CnhInterpreter",
    "RgInterpreter",
    "BoletoInterpreter",
    "get_interpreter",
    "detect_document_type_from_text",
]
