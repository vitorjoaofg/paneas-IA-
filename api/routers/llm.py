import secrets
import time

from fastapi import APIRouter

from config import get_settings
from schemas.llm import ChatRequest, ChatResponse, ChatChoice, ChatMessage, UsageMetrics
from services.llm_client import chat_completion
from services.llm_router import LLMRouter, LLMTarget

router = APIRouter(prefix="/api/v1", tags=["llm"])
settings = get_settings()
router_engine = LLMRouter(strategy=settings.llm_routing_strategy)


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion(payload: ChatRequest):
    prompt_tokens = sum(len(msg.content.split()) for msg in payload.messages)
    context_length = prompt_tokens + payload.max_tokens
    decision = router_engine.route(
        prompt_tokens=prompt_tokens,
        context_length=context_length,
        quality_priority=payload.quality_priority,
    )

    target_model = LLMTarget.FP16 if decision.target == LLMTarget.FP16 else LLMTarget.INT4

    upstream_payload = payload.model_dump()

    start = time.perf_counter()
    upstream_response = await chat_completion(upstream_payload, target_model)
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
    metadata.update({
        "router_target": decision.target.value,
        "router_reason": decision.reason,
        "latency_ms": int(elapsed * 1000),
    })

    return ChatResponse(id=response_id, model=model_name, choices=choices, usage=usage_metrics)
