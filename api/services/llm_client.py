import json
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import structlog
from config import get_settings
from services.http_client import get_http_client, request_with_retry
from services.llm_router import LLMTarget

_settings = get_settings()
LOGGER = structlog.get_logger(__name__)

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "paneas-v1-q14b": {"target": LLMTarget.INT4, "path": "/models/qwen2_5/int4-awq"},
    "paneas-q32b": {"target": LLMTarget.INT4, "path": "/models/qwen2_5/int4-awq-32b"},
    "gpt-4o-mini": {"target": LLMTarget.OPENAI, "path": "gpt-4o-mini"},
}


def _preferred_targets(primary: LLMTarget) -> List[LLMTarget]:
    # Por enquanto, apenas usar INT4 já que FP16 não está rodando
    order: List[LLMTarget] = [primary]
    # Comentado até termos FP16 disponível
    # if primary == LLMTarget.INT4:
    #     order.append(LLMTarget.FP16)
    # elif primary == LLMTarget.FP16:
    #     order.append(LLMTarget.INT4)
    return order


def resolve_endpoint(target: LLMTarget) -> str:
    if target == LLMTarget.FP16:
        return f"http://{_settings.llm_fp16_host}:{_settings.llm_fp16_port}"
    if target == LLMTarget.OPENAI:
        return str(_settings.openai_api_base)
    return f"http://{_settings.llm_int4_host}:{_settings.llm_int4_port}"


def resolve_model_path(model_name: Optional[str], target: LLMTarget) -> str:
    if target == LLMTarget.OPENAI:
        return _resolve_openai_chat_model(model_name)
    if model_name and model_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[model_name]["path"]
    if target == LLMTarget.FP16:
        return "/models/qwen2_5/fp16"
    return "/models/qwen2_5/int4-awq-32b"


async def chat_completion(
    payload: Dict[str, Any],
    target: LLMTarget,
    router_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = dict(payload)
    provider = (payload.pop("provider", None) or "paneas").lower()
    payload.pop("quality_priority", None)

    # Preserve tools/tool_choice for OpenAI, remove for vLLM
    if target == LLMTarget.OPENAI or provider == "openai":
        request_payload = dict(payload)
        original_model = request_payload.get("model")
        request_payload["model"] = _resolve_openai_chat_model(original_model)
        data = await _chat_completion_openai(request_payload)
        if original_model:
            data["model"] = original_model
        metadata = data.setdefault("metadata", {})
        if router_metadata:
            metadata.update(router_metadata)
        metadata["router_target"] = LLMTarget.OPENAI.value
        return data

    # For vLLM (paneas) - remove tools/tool_choice as vLLM 0.4.2 doesn't support them
    # Will use prompt engineering instead in the router
    payload.pop("tools", None)
    payload.pop("tool_choice", None)

    preferred_order = _preferred_targets(target)
    last_error: Exception | None = None
    original_model = payload.get("model")
    for current_target in preferred_order:
        request_payload = dict(payload)
        request_payload["model"] = resolve_model_path(original_model, current_target)

        # Clean up messages to remove None fields
        if "messages" in request_payload:
            clean_messages = []
            for msg in request_payload["messages"]:
                # Skip tool messages and messages with empty role
                role = msg.get("role", "")
                if role == "tool":
                    LOGGER.info("DEBUG: Skipping tool message", tool_name=msg.get("name", "unknown"))
                    continue

                clean_msg = {"role": role}

                # CORRIGIDO: Garantir que sempre tem content, mesmo que vazio
                # vLLM não aceita mensagens assistant sem content
                if "content" in msg and msg["content"] is not None:
                    clean_msg["content"] = msg["content"]
                elif role in ["assistant", "user"]:
                    # Se assistant ou user não tem content, adicionar string vazia
                    clean_msg["content"] = ""
                    LOGGER.info("DEBUG: Adding empty content", role=role)
                else:
                    clean_msg["content"] = msg.get("content", "")

                # Only add optional fields if they exist and are not None
                if msg.get("name"):
                    clean_msg["name"] = msg["name"]

                clean_messages.append(clean_msg)
            request_payload["messages"] = clean_messages

            LOGGER.info("DEBUG: Cleaned messages",
                        original_count=len(payload.get("messages", [])),
                        cleaned_count=len(clean_messages),
                        roles=[m.get("role") for m in clean_messages])

        client = await get_http_client()
        endpoint = resolve_endpoint(current_target)
        LOGGER.info("DEBUG: Sending to vLLM", endpoint=endpoint, payload=request_payload)
        try:
            response = await request_with_retry(
                "POST",
                f"{endpoint}/v1/chat/completions",
                client=client,
                json=request_payload,
                timeout=_settings.llm_timeout,
                retry_attempts=3,
            )
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            LOGGER.warning(
                "llm_chat_retry_failed",
                target=current_target.value,
                endpoint=endpoint,
                error=str(exc),
            )
            continue

        if original_model:
            data["model"] = original_model
        metadata = data.setdefault("metadata", {})
        if router_metadata:
            metadata.update(router_metadata)
        metadata["router_target"] = current_target.value
        return data

    if last_error:
        raise last_error
    raise RuntimeError("No LLM backend available")


async def chat_completion_stream(
    payload: Dict[str, Any],
    target: LLMTarget,
    router_metadata: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[bytes, None]:
    payload = dict(payload)
    provider = (payload.pop("provider", None) or "paneas").lower()
    payload.pop("quality_priority", None)
    payload.setdefault("stream", True)
    original_model = payload.get("model")
    metadata_base = router_metadata or {}

    LOGGER.info(
        "llm_stream_start",
        provider=provider,
        target=target.value,
        requested_model=original_model,
    )
    if target == LLMTarget.OPENAI or provider == "openai":
        request_payload = dict(payload)
        request_payload["model"] = _resolve_openai_chat_model(original_model)
        async for chunk in _stream_openai_chat(
            request_payload,
            original_model=original_model,
            router_metadata=metadata_base,
        ):
            yield chunk
        return

    preferred_order = _preferred_targets(target)
    last_error: Exception | None = None
    for current_target in preferred_order:
        request_payload = dict(payload)
        request_payload["model"] = resolve_model_path(original_model, current_target)

        # Clean up messages to remove None fields (same as non-streaming)
        if "messages" in request_payload:
            clean_messages = []
            for msg in request_payload["messages"]:
                # Skip tool messages and messages with empty role
                if msg["role"] == "tool":
                    continue

                clean_msg = {"role": msg["role"]}

                # CORRIGIDO: Garantir que sempre tem content, mesmo que vazio
                # vLLM não aceita mensagens assistant sem content
                if "content" in msg and msg["content"] is not None:
                    clean_msg["content"] = msg["content"]
                elif msg["role"] in ["assistant", "user"]:
                    # Se assistant ou user não tem content, adicionar string vazia
                    clean_msg["content"] = ""
                else:
                    clean_msg["content"] = msg.get("content", "")

                # Only add optional fields if they exist and are not None
                if msg.get("name"):
                    clean_msg["name"] = msg["name"]

                clean_messages.append(clean_msg)
            request_payload["messages"] = clean_messages

        client = await get_http_client()
        endpoint = resolve_endpoint(current_target)
        timeout = httpx.Timeout(_settings.llm_timeout, connect=min(10.0, _settings.llm_timeout))
        headers = {"Accept": "text/event-stream"}

        try:
            async with client.stream(
                "POST",
                f"{endpoint}/v1/chat/completions",
                json=request_payload,
                headers=headers,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                async for event in _augment_sse_stream(
                    response,
                    original_model=original_model,
                    router_metadata=metadata_base,
                    current_target=current_target,
                ):
                    yield event
                LOGGER.info(
                    "llm_stream_completed",
                    target=current_target.value,
                    requested_model=original_model,
                )
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            LOGGER.warning(
                "llm_chat_stream_failed",
                target=current_target.value,
                endpoint=endpoint,
                error=str(exc),
            )
            continue

    if last_error:
        LOGGER.error(
            "llm_stream_exhausted",
            target=target.value,
            error=str(last_error),
        )
        raise last_error
    raise RuntimeError("No LLM backend available")


async def _chat_completion_openai(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")

    headers = {
        "Authorization": f"Bearer {_settings.openai_api_key}",
    }
    client = await get_http_client()
    timeout = httpx.Timeout(_settings.openai_timeout, connect=min(10.0, _settings.openai_timeout))
    base_url = str(_settings.openai_api_base).rstrip("/")
    response = await request_with_retry(
        "POST",
        f"{base_url}/chat/completions",
        client=client,
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    return response.json()


async def _stream_openai_chat(
    payload: Dict[str, Any],
    *,
    original_model: Optional[str],
    router_metadata: Dict[str, Any],
) -> AsyncGenerator[bytes, None]:
    if not _settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")

    headers = {
        "Authorization": f"Bearer {_settings.openai_api_key}",
        "Accept": "text/event-stream",
    }
    client = await get_http_client()
    timeout = httpx.Timeout(_settings.openai_timeout, connect=min(10.0, _settings.openai_timeout), read=_settings.openai_timeout)
    base_url = str(_settings.openai_api_base).rstrip("/")
    async with client.stream(
        "POST",
        f"{base_url}/chat/completions",
        json=payload,
        headers=headers,
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        async for event in _augment_sse_stream(
            response,
            original_model=original_model,
            router_metadata=router_metadata,
            current_target=LLMTarget.OPENAI,
        ):
            yield event


async def _augment_sse_stream(
    response: httpx.Response,
    *,
    original_model: Optional[str],
    router_metadata: Dict[str, Any],
    current_target: LLMTarget,
) -> AsyncGenerator[bytes, None]:
    event_lines: List[str] = []
    async for raw_line in response.aiter_lines():
        if raw_line is None:
            continue
        line = raw_line.rstrip("\r")
        if line == "":
            formatted = _format_sse_event(
                event_lines,
                original_model=original_model,
                router_metadata=router_metadata,
                current_target=current_target,
            )
            if formatted:
                yield formatted
            event_lines = []
            continue
        event_lines.append(line)
    if event_lines:
        formatted = _format_sse_event(
            event_lines,
            original_model=original_model,
            router_metadata=router_metadata,
            current_target=current_target,
        )
        if formatted:
            yield formatted


def _format_sse_event(
    lines: List[str],
    *,
    original_model: Optional[str],
    router_metadata: Dict[str, Any],
    current_target: LLMTarget,
) -> Optional[bytes]:
    if not lines:
        return None

    processed_lines: List[str] = []
    for line in lines:
        if not line.startswith("data:"):
            processed_lines.append(line)
            continue

        payload_str = line[5:].lstrip()
        if payload_str == "[DONE]":
            processed_lines.append("data: [DONE]")
            continue

        try:
            parsed = json.loads(payload_str)
        except json.JSONDecodeError:
            processed_lines.append(line.strip())
            continue

        if original_model:
            parsed["model"] = original_model

        metadata = parsed.setdefault("metadata", {})
        if router_metadata:
            metadata.update(router_metadata)
        metadata["router_target"] = current_target.value

        processed_lines.append(f"data: {json.dumps(parsed, separators=(',', ':'))}")

    if not processed_lines:
        return None
    return ("\n".join(processed_lines) + "\n\n").encode("utf-8")


def _resolve_openai_chat_model(requested_model: Optional[str]) -> str:
    if not requested_model:
        return _settings.openai_insights_model
    lowered = requested_model.lower()
    if lowered.startswith("openai/"):
        return requested_model.split("/", 1)[1]
    if lowered == "paneas-v1-q14b":
        return _settings.openai_insights_model
    return requested_model
