from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


LOGGER = logging.getLogger(__name__)


def refine_with_llm(text: str, doc_type: Optional[str], structured: Dict[str, Any]) -> Dict[str, Any]:
    prompt = _build_prompt(text, doc_type, structured)
    response = _dispatch_llm(prompt)
    if not response:
        return structured
    parsed = _parse_llm_response(response)
    return parsed if isinstance(parsed, dict) else structured


def _build_prompt(text: str, doc_type: Optional[str], structured: Dict[str, Any]) -> str:
    summary = json.dumps(structured, ensure_ascii=False, default=str)
    doc_label = doc_type or structured.get("document_type") or "document"
    return (
        f"Você é responsável por interpretar documentos do tipo '{doc_label}'. "
        f"Melhore o JSON estruturado mantendo o mesmo formato de chave/valor sempre que possível. "
        f"Texto OCR completo:\n{text}\n"
        f"Estrutura atual:\n{summary}\n"
        "Responda apenas com JSON válido."
    )


def _dispatch_llm(prompt: str) -> Optional[str]:
    api_key = os.environ.get("OCR_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    api_base = os.environ.get("OCR_LLM_API_URL") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
    model = os.environ.get("OCR_LLM_MODEL") or os.environ.get("OPENAI_INSIGHTS_MODEL") or "gpt-4o-mini"
    timeout = _safe_float(os.environ.get("OCR_LLM_TIMEOUT"), 30.0)

    if not api_key:
        LOGGER.info("llm_api_key_missing")
        return None

    endpoint = api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Você retorna apenas JSON válido sem comentários adicionais."},
            {"role": "user", "content": prompt},
        ],
        "temperature": _safe_float(os.environ.get("OCR_LLM_TEMPERATURE"), 0.1),
    }
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(endpoint, data=data, method="POST")
    request.add_header("Authorization", f"Bearer {api_key}")
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        LOGGER.warning("llm_request_failed: %s", exc)
        return None

    try:
        body = json.loads(raw)
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        LOGGER.warning("llm_invalid_response: %s", exc)
        return None
    return _strip_code_fences(content)


def _parse_llm_response(response: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _strip_code_fences(content: str) -> str:
    trimmed = content.strip()
    if not trimmed.startswith("```"):
        return trimmed
    lines = trimmed.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _safe_float(value: Optional[str], default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
