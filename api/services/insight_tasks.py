from __future__ import annotations

from typing import Any, Dict

import httpx
import structlog

from celery_app import celery_app
from services.llm_client import resolve_endpoint, resolve_model_path
from services.llm_router import LLMTarget

LOGGER = structlog.get_logger(__name__)


@celery_app.task(name="insights.generate", bind=True)
def generate_insight_task(self, payload: Dict[str, Any], target: str) -> Dict[str, Any]:
    try:
        llm_target = LLMTarget[target]
    except KeyError as exc:  # pragma: no cover - guard for misconfiguration
        raise ValueError(f"Unknown LLM target '{target}'") from exc

    original_model = payload.get("model")
    request_payload = dict(payload)
    request_payload["model"] = resolve_model_path(original_model, llm_target)
    request_payload.pop("quality_priority", None)

    endpoint = resolve_endpoint(llm_target)

    LOGGER.info(
        "insight_task_dispatch",
        task_id=self.request.id if self.request else None,
        target=llm_target.name,
        model=original_model,
    )

    with httpx.Client(timeout=None) as client:
        response = client.post(f"{endpoint}/v1/chat/completions", json=request_payload)
        response.raise_for_status()
        data = response.json()

    if original_model:
        data["model"] = original_model
    return data
