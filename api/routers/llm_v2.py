import json
import secrets
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import structlog

from config import get_settings
from schemas.llm import ChatRequest, ChatResponse, ChatChoice, ChatMessage, UsageMetrics, ToolCall, FunctionCall
from services.llm_client import MODEL_REGISTRY, chat_completion, chat_completion_stream
from services.llm_router import LLMRouter, LLMRoutingDecision, LLMTarget
from services.tool_executor import get_tool_executor
from services.tools import unimed_consult
from services.tool_prompt_helper import tools_to_prompt, extract_function_call, inject_tools_in_messages

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["llm"])
settings = get_settings()
router_engine = LLMRouter(strategy=settings.llm_routing_strategy)

MAX_CONTEXT_LENGTH = 32768
MAX_TOOL_ITERATIONS = 5

# Registrar tools disponíveis
tool_executor = get_tool_executor()
tool_executor.register("unimed_consult", unimed_consult)


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion(payload: ChatRequest):
    # Desabilitar streaming automaticamente se tools estão presentes
    has_tools = payload.tools is not None and len(payload.tools) > 0
    if has_tools and payload.stream:
        LOGGER.info("auto_disable_streaming", reason="tools_present")
        payload.stream = False

    prompt_tokens = sum(len(msg.content.split()) for msg in payload.messages if msg.content)
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

    router_metadata = {
        "router_decision": decision.target.value,
        "router_reason": decision.reason,
    }

    start = time.perf_counter()

    # Se streaming sem tools, usar fluxo antigo
    if payload.stream and not has_tools:
        upstream_payload = payload.model_dump()
        upstream_payload["stream"] = True

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

    # Se não tem tools, usar fluxo simples (uma única chamada)
    if not has_tools:
        upstream_payload = payload.model_dump()
        upstream_payload.pop("stream", None)

        LOGGER.info("llm_call_simple", has_tools=False)

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

    # Fluxo COM TOOLS - usar prompt engineering
    LOGGER.info("llm_call_with_tools", num_tools=len(payload.tools))

    # Converter messages para dicts e injetar system prompt com tools
    messages = [msg.model_dump() for msg in payload.messages]
    messages = inject_tools_in_messages(messages, payload.tools)

    total_prompt_tokens = 0
    total_completion_tokens = 0
    iteration = 0
    response_id = f"chatcmpl-{secrets.token_hex(8)}"

    # Loop de tool calling com prompt engineering
    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        # Preparar payload para esta iteração (SEM tools, usamos prompt engineering)
        current_payload = {
            "model": payload.model,
            "messages": messages,
            "max_tokens": payload.max_tokens,
            "temperature": payload.temperature,
        }

        LOGGER.info(
            "llm_call_iteration",
            iteration=iteration,
            num_messages=len(messages),
        )

        # Fazer chamada ao LLM
        upstream_response = await chat_completion(
            current_payload,
            target_model,
            router_metadata=router_metadata,
        )

        # Acumular tokens
        usage = upstream_response.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)

        # Extrair primeira choice
        choices_raw = upstream_response.get("choices", [])
        if not choices_raw:
            raise HTTPException(status_code=500, detail="No choices returned from LLM")

        first_choice = choices_raw[0]
        message_dict = first_choice.get("message", {})
        content = message_dict.get("content", "")
        finish_reason = first_choice.get("finish_reason", "stop")

        LOGGER.info(
            "llm_response",
            iteration=iteration,
            content_preview=content[:200] if content else None,
            finish_reason=finish_reason,
        )

        # Tentar extrair function call do conteúdo
        function_call_data = extract_function_call(content)

        if not function_call_data:
            # Não há function call, retornar resposta final
            elapsed = time.perf_counter() - start

            choices = [
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason=finish_reason,
                )
            ]

            usage_metrics = UsageMetrics(
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                total_tokens=total_prompt_tokens + total_completion_tokens,
            )

            model_name = upstream_response.get("model", payload.model)
            metadata = upstream_response.setdefault("metadata", {})
            metadata.setdefault("router_target", router_metadata["router_decision"])
            metadata["router_decision"] = router_metadata["router_decision"]
            metadata["router_reason"] = router_metadata["router_reason"]
            metadata["latency_ms"] = int(elapsed * 1000)
            metadata["tool_iterations"] = iteration

            return ChatResponse(
                id=response_id,
                model=model_name,
                choices=choices,
                usage=usage_metrics,
            )

        # Há function call, executar
        LOGGER.info(
            "tool_call_detected",
            iteration=iteration,
            function_name=function_call_data["name"],
        )

        # Criar ToolCall object
        tool_call_id = f"call_{secrets.token_hex(12)}"
        tool_call = ToolCall(
            id=tool_call_id,
            type="function",
            function=FunctionCall(
                name=function_call_data["name"],
                arguments=function_call_data["arguments"],
            )
        )

        # Adicionar mensagem do assistente com function call
        messages.append({
            "role": "assistant",
            "content": content,
        })

        # Executar tool
        tool_result = await tool_executor.execute(tool_call)

        LOGGER.info(
            "tool_executed",
            iteration=iteration,
            function_name=function_call_data["name"],
            result_preview=tool_result[:200] if tool_result else None,
        )

        # Adicionar resultado como mensagem do usuário
        messages.append({
            "role": "user",
            "content": f"Resultado da função {function_call_data['name']}:\n{tool_result}\n\nAgora responda ao usuário original com base neste resultado."
        })

        # Continuar loop para fazer nova chamada ao LLM

    # Se chegou aqui, excedeu max iterations
    raise HTTPException(
        status_code=500,
        detail=f"Maximum tool calling iterations ({MAX_TOOL_ITERATIONS}) exceeded. "
               f"Possible infinite loop detected."
    )
