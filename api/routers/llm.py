import secrets
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config import get_settings
from schemas.llm import ChatRequest, ChatResponse, ChatChoice, ChatMessage, UsageMetrics
from services.llm_client import MODEL_REGISTRY, chat_completion, chat_completion_stream
from services.llm_router import LLMRouter, LLMRoutingDecision, LLMTarget

router = APIRouter(prefix="/api/v1", tags=["llm"])
settings = get_settings()
router_engine = LLMRouter(strategy=settings.llm_routing_strategy)

MAX_CONTEXT_LENGTH = 32768  # Limite máximo do Qwen2.5 INT4


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion(payload: ChatRequest):
    prompt_tokens = sum(len(msg.content.split()) for msg in payload.messages)
    context_length = prompt_tokens + payload.max_tokens

    # Validação: rejeita se ultrapassar limite de 32k tokens
    if context_length > MAX_CONTEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Context length ({context_length} tokens) exceeds maximum allowed ({MAX_CONTEXT_LENGTH} tokens). "
                   f"Please reduce your message size or max_tokens parameter."
        )

    provider = payload.provider
    if provider == "openai":
        decision = LLMRoutingDecision(target=LLMTarget.OPENAI, reason="requested_provider")
    elif payload.model in MODEL_REGISTRY:
        forced_target = MODEL_REGISTRY[payload.model]["target"]
        decision = LLMRoutingDecision(target=forced_target, reason="requested_model")
    else:
        decision = router_engine.route(
            prompt_tokens=prompt_tokens,
            context_length=context_length,
            quality_priority=payload.quality_priority,
        )

    target_model = decision.target

    upstream_payload = payload.model_dump()

    if payload.stream:
        upstream_payload["stream"] = True
    else:
        upstream_payload.pop("stream", None)

    router_metadata = {
        "router_decision": decision.target.value,
        "router_reason": decision.reason,
    }

    start = time.perf_counter()

    if payload.stream:
        async def event_iterator():
            async for chunk in chat_completion_stream(
                upstream_payload,
                target_model,
                router_metadata=router_metadata,
            ):
                yield chunk

        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    upstream_response = await chat_completion(
        upstream_payload,
        target_model,
        router_metadata=router_metadata,
    )
    elapsed = time.perf_counter() - start

    usage = upstream_response.get("usage", {})
    choices = [
        ChatChoice(
            index=item.get("index", 0),
            message=ChatMessage(**item.get("message", {})),
            finish_reason=item.get("finish_reason", "stop"),
        )
        for item in upstream_response.get("choices", [])
    ]

    usage_metrics = UsageMetrics(
        prompt_tokens=usage.get("prompt_tokens", prompt_tokens),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)),
    )

    response_id = upstream_response.get("id", f"chatcmpl-{secrets.token_hex(8)}")
    model_name = upstream_response.get("model", payload.model)
    metadata = upstream_response.setdefault("metadata", {})
    metadata.setdefault("router_target", router_metadata["router_decision"])
    metadata["router_decision"] = router_metadata["router_decision"]
    metadata["router_reason"] = router_metadata["router_reason"]
    metadata["latency_ms"] = int(elapsed * 1000)

    return ChatResponse(id=response_id, model=model_name, choices=choices, usage=usage_metrics)
