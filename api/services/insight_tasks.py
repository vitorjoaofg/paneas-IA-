from __future__ import annotations

from typing import Any, Dict

import httpx
import structlog

from celery_app import celery_app
from config import get_settings
from services.llm_client import resolve_endpoint, resolve_model_path
from services.llm_router import LLMTarget

LOGGER = structlog.get_logger(__name__)
_settings = get_settings()


@celery_app.task(name="insights.generate", bind=True)
def generate_insight_task(self, payload: Dict[str, Any], target: str) -> Dict[str, Any]:
    try:
        llm_target = LLMTarget[target]
    except KeyError as exc:  # pragma: no cover - guard for misconfiguration
        raise ValueError(f"Unknown LLM target '{target}'") from exc

    original_model = payload.get("model")
    provider = (payload.get("provider") or "paneas").lower()
    request_payload = dict(payload)
    request_payload["model"] = resolve_model_path(original_model, llm_target)
    request_payload.pop("quality_priority", None)
    request_payload.pop("provider", None)

    endpoint = resolve_endpoint(llm_target).rstrip("/")

    LOGGER.info(
        "insight_task_dispatch",
        task_id=self.request.id if self.request else None,
        target=llm_target.name,
        model=original_model,
    )

    if llm_target == LLMTarget.OPENAI or provider == "openai":
        if not _settings.openai_api_key:
            raise RuntimeError("OpenAI API key is not configured")
        headers = {"Authorization": f"Bearer {_settings.openai_api_key}"}
        timeout = httpx.Timeout(_settings.openai_timeout, connect=min(10.0, _settings.openai_timeout))
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{endpoint}/chat/completions", json=request_payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    else:
        with httpx.Client(timeout=None) as client:
            response = client.post(f"{endpoint}/v1/chat/completions", json=request_payload)
            response.raise_for_status()
            data = response.json()

    if original_model:
        data["model"] = original_model
    return data
