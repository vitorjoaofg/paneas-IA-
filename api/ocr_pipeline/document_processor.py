from __future__ import annotations

from typing import Any, Dict, Optional

from .interpreters import get_interpreter
from .llm_refiner import refine_with_llm


def process_document(
    ocr_json: Dict[str, Any],
    doc_type: Optional[str] = None,
    use_llm: bool = False,
) -> Dict[str, Any]:
    text = _extract_text(ocr_json)
    resolved_type = doc_type or _infer_doc_type(ocr_json)
    interpreter = get_interpreter(resolved_type, text=text)
    structured = interpreter.interpret(ocr_json)
    if use_llm:
        structured = refine_with_llm(text, resolved_type, structured)
    return structured


def _infer_doc_type(ocr_json: Dict[str, Any]) -> Optional[str]:
    metadata = ocr_json.get("metadata")
    if isinstance(metadata, dict):
        doc_type = metadata.get("document_type") or metadata.get("type")
        normalized = _normalize_doc_type(doc_type)
        if normalized:
            return normalized
    for page in ocr_json.get("pages", []):
        if isinstance(page, dict):
            page_type = page.get("document_type") or page.get("type")
            normalized = _normalize_doc_type(page_type)
            if normalized:
                return normalized
    return None


def _normalize_doc_type(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered in {"generico", "generic", "unknown"}:
        return None
    return cleaned


def _extract_text(ocr_json: Dict[str, Any]) -> str:
    text = ocr_json.get("text")
    if isinstance(text, str) and text.strip():
        return text
    pages = ocr_json.get("pages") or []
    texts = []
    for page in pages:
        if isinstance(page, dict):
            page_text = page.get("text")
            if isinstance(page_text, str) and page_text.strip():
                texts.append(page_text.strip())
    return "\n".join(texts)
