from typing import Any, Dict, Optional

from config import get_settings
from services.http_client import get_http_client
from services.llm_router import LLMTarget

_settings = get_settings()

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "qwen2.5-14b-instruct": {"target": LLMTarget.INT4, "path": "/models/qwen2_5/int4-awq"},
    "qwen2.5-14b-instruct-awq": {"target": LLMTarget.INT4, "path": "/models/qwen2_5/int4-awq"},
    # Legacy aliases kept for backward compatibility; both point to the new Qwen deployment.
    "llama-3.1-8b-instruct": {"target": LLMTarget.FP16, "path": "/models/qwen2_5/fp16"},
    "llama-3.1-8b-instruct-awq": {"target": LLMTarget.INT4, "path": "/models/qwen2_5/int4-awq"},
    "llama-3.1-8b-instruct-int4": {"target": LLMTarget.INT4, "path": "/models/qwen2_5/int4-awq"},
}


def resolve_endpoint(target: LLMTarget) -> str:
    if target == LLMTarget.FP16:
        return f"http://{_settings.llm_fp16_host}:{_settings.llm_fp16_port}"
    return f"http://{_settings.llm_int4_host}:{_settings.llm_int4_port}"


def resolve_model_path(model_name: Optional[str], target: LLMTarget) -> str:
    if model_name and model_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_name]["path"]
    if target == LLMTarget.FP16:
        return "/models/qwen2_5/fp16"
    return "/models/qwen2_5/int4-awq"


async def chat_completion(payload: Dict[str, Any], target: LLMTarget) -> Dict[str, Any]:
    client = await get_http_client()
    endpoint = resolve_endpoint(target)
    original_model = payload.get("model")
    payload["model"] = resolve_model_path(original_model, target)

    # Remove internal-only keys that the upstream OpenAI-compatible API
    # does not accept.
    payload.pop("quality_priority", None)

    response = await client.post(
        f"{endpoint}/v1/chat/completions",
        json=payload,
        timeout=None,
    )
    response.raise_for_status()
    data = response.json()
    # Restore the original model name for downstream consumers.
    if original_model:
        data["model"] = original_model
    return data
