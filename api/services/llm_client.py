from typing import Any, Dict

from config import get_settings
from services.http_client import get_http_client
from services.llm_router import LLMTarget

_settings = get_settings()


def _resolve_endpoint(target: LLMTarget) -> str:
    if target == LLMTarget.FP16:
        return f"http://{_settings.llm_fp16_host}:{_settings.llm_fp16_port}"
    return f"http://{_settings.llm_int4_host}:{_settings.llm_int4_port}"


async def chat_completion(payload: Dict[str, Any], target: LLMTarget) -> Dict[str, Any]:
    client = await get_http_client()
    endpoint = _resolve_endpoint(target)
    # Map public model names to the served vLLM identifiers.
    original_model = payload.get("model")
    if target == LLMTarget.FP16:
        payload["model"] = "/models/llama/fp16"
    else:
        payload["model"] = "/models/llama/int4-awq"

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
