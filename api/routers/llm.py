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
from services.tools.generic_http import age_predictor, external_api_call
from services.tool_prompt_helper import tools_to_prompt, extract_function_call

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["llm"])
settings = get_settings()
router_engine = LLMRouter(strategy=settings.llm_routing_strategy)

MAX_CONTEXT_LENGTH = 32768
MAX_TOOL_ITERATIONS = 3

# Registrar tools disponíveis
tool_executor = get_tool_executor()
tool_executor.register("unimed_consult", unimed_consult)
tool_executor.register("age_predictor", age_predictor)
tool_executor.register("external_api_call", external_api_call)


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion(payload: ChatRequest):
    LOGGER.info("DEBUG: Request received", model=payload.model, has_tools=bool(payload.tools))

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
        LOGGER.info("DEBUG: Using streaming flow")
        upstream_payload = payload.model_dump(exclude_none=True, exclude_unset=True)
        upstream_payload["stream"] = True

        # Remove fields not supported by vLLM
        upstream_payload.pop("tools", None)
        upstream_payload.pop("tool_choice", None)
        upstream_payload.pop("provider", None)
        upstream_payload.pop("quality_priority", None)

        # Clean up messages to remove None fields
        if "messages" in upstream_payload:
            clean_messages = []
            for msg in upstream_payload["messages"]:
                clean_msg = {"role": msg["role"]}
                if "content" in msg and msg["content"] is not None:
                    clean_msg["content"] = msg["content"]
                clean_messages.append(clean_msg)
            upstream_payload["messages"] = clean_messages

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
        LOGGER.info("DEBUG: Simple completion without tools")
        upstream_payload = payload.model_dump(exclude_none=True, exclude_unset=True)
        upstream_payload.pop("stream", None)

        # Remove tools from payload if present but empty
        upstream_payload.pop("tools", None)
        upstream_payload.pop("tool_choice", None)
        # Remove fields not supported by vLLM
        upstream_payload.pop("provider", None)
        upstream_payload.pop("quality_priority", None)

        # Clean up messages to remove None fields
        if "messages" in upstream_payload:
            clean_messages = []
            for msg in upstream_payload["messages"]:
                clean_msg = {"role": msg["role"]}
                if "content" in msg and msg["content"] is not None:
                    clean_msg["content"] = msg["content"]
                clean_messages.append(clean_msg)
            upstream_payload["messages"] = clean_messages

        LOGGER.info("DEBUG: Calling LLM", payload_keys=list(upstream_payload.keys()))

        try:
            upstream_response = await chat_completion(
                upstream_payload,
                target_model,
                router_metadata=router_metadata,
            )
            LOGGER.info("DEBUG: LLM response received", response_keys=list(upstream_response.keys()))
        except Exception as e:
            LOGGER.error("DEBUG: LLM call failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

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

        response = ChatResponse(id=response_id, model=model_name, choices=choices, usage=usage_metrics)
        LOGGER.info("DEBUG: Returning response", response_id=response_id)
        return response

    # Fluxo COM TOOLS - usar prompt engineering
    LOGGER.info("DEBUG: Using tools flow", num_tools=len(payload.tools))

    # Preparar mensagens - CORRIGIDO
    # Gerar prompt de tools e injetar nas mensagens existentes
    tools_prompt = tools_to_prompt(payload.tools)
    messages = []
    system_injected = False

    for msg in payload.messages:
        msg_dict = msg.model_dump()
        if msg_dict["role"] == "system" and not system_injected:
            combined_content = (msg_dict.get("content") or "") + "\n\n" + tools_prompt
            messages.append({"role": "system", "content": combined_content})
            system_injected = True
        else:
            messages.append({
                "role": msg_dict["role"],
                "content": msg_dict.get("content", "")
            })

    if not system_injected:
        messages.insert(0, {"role": "system", "content": tools_prompt})

    # Detectar se há tool choice forçado para execução direta
    forced_tool_choice = None
    forced_tool_used = False

    if isinstance(payload.tool_choice, dict):
        tool_choice_dict = payload.tool_choice
        if tool_choice_dict.get("type") == "function":
            function_choice = tool_choice_dict.get("function", {})
            forced_name = function_choice.get("name")
            if forced_name:
                raw_arguments = function_choice.get("arguments")

                if isinstance(raw_arguments, str):
                    try:
                        parsed_arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError:
                        parsed_arguments = raw_arguments
                elif raw_arguments is None:
                    parsed_arguments = {}
                else:
                    parsed_arguments = raw_arguments

                if isinstance(parsed_arguments, str):
                    arguments_str = parsed_arguments
                else:
                    arguments_str = json.dumps(parsed_arguments, ensure_ascii=False)

                forced_tool_choice = {
                    "name": forced_name,
                    "arguments_payload": parsed_arguments,
                    "arguments_str": arguments_str,
                }
                LOGGER.info(
                    "DEBUG: Forced tool_choice detected",
                    function_name=forced_name,
                )

    total_prompt_tokens = 0
    total_completion_tokens = 0
    iteration = 0
    response_id = f"chatcmpl-{secrets.token_hex(8)}"

    # Loop de tool calling com prompt engineering
    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        # Preparar payload para esta iteração
        current_payload = {
            "model": payload.model,
            "messages": messages,
            "max_tokens": payload.max_tokens,
            "temperature": 0.3,  # Baixa temperatura para melhor seguir instruções
        }

        LOGGER.info(
            "DEBUG: Tool iteration",
            iteration=iteration,
            num_messages=len(messages),
        )

        use_forced_tool = bool(forced_tool_choice) and not forced_tool_used
        function_call_data = None

        if use_forced_tool:
            forced_tool_used = True
            content_payload = {
                "function_call": {
                    "name": forced_tool_choice["name"],
                    "arguments": forced_tool_choice["arguments_payload"],
                }
            }
            content = json.dumps(content_payload, ensure_ascii=False)
            finish_reason = "tool_calls"
            function_call_data = {
                "name": forced_tool_choice["name"],
                "arguments": forced_tool_choice["arguments_str"],
            }
            LOGGER.info(
                "DEBUG: Applying forced tool_choice",
                iteration=iteration,
                function_name=forced_tool_choice["name"],
            )
        else:
            # Fazer chamada ao LLM
            try:
                upstream_response = await chat_completion(
                    current_payload,
                    target_model,
                    router_metadata=router_metadata,
                )
            except Exception as e:
                LOGGER.error("DEBUG: Tool LLM call failed", error=str(e), iteration=iteration)
                raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

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
            "DEBUG: Tool response",
            iteration=iteration,
            content_preview=content[:200] if content else None,
            finish_reason=finish_reason,
        )

        if not use_forced_tool:
            # Tentar extrair function call do conteúdo
            function_call_data = extract_function_call(content)

            if not function_call_data:
                # Não há function call, retornar resposta final
                elapsed = time.perf_counter() - start

                # Se é a primeira iteração e não detectou tool call, vamos ajudar o modelo
                if iteration == 1 and has_tools:
                    # Verificar se o usuário mencionou consultar algo
                    user_msg = payload.messages[-1].content.lower()
                    if any(word in user_msg for word in ["consulte", "consultar", "buscar", "verificar", "checar"]):
                        # Adicionar hint mais específico
                        messages.append({
                            "role": "assistant",
                            "content": content
                        })
                        messages.append({
                            "role": "user",
                            "content": "Por favor, use a função unimed_consult para fazer a consulta solicitada. Responda no formato JSON especificado."
                        })
                        continue  # Tentar novamente

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
            "DEBUG: Tool call detected",
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

        # Adicionar mensagem do assistente
        messages.append({
            "role": "assistant",
            "content": content,
        })

        # Executar tool
        tool_result = await tool_executor.execute(tool_call)

        LOGGER.info(
            "DEBUG: Tool executed",
            iteration=iteration,
            function_name=function_call_data["name"],
            result_preview=tool_result[:200] if tool_result else None,
        )

        # Adicionar resultado como mensagem do usuário
        messages.append({
            "role": "user",
            "content": f"Resultado da função {function_call_data['name']}:\n{tool_result}\n\nAgora responda ao usuário original de forma completa e útil com base neste resultado."
        })

        # Continuar loop para fazer nova chamada ao LLM

    # Se chegou aqui, excedeu max iterations
    raise HTTPException(
        status_code=500,
        detail=f"Maximum tool calling iterations ({MAX_TOOL_ITERATIONS}) exceeded. "
               f"Possible infinite loop detected."
    )
