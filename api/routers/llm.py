import json
import secrets
import time
from typing import List, Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import structlog

from config import get_settings
from schemas.llm import ChatRequest, ChatResponse, ChatChoice, ChatMessage, UsageMetrics, ToolCall, FunctionCall
from services.llm_client import MODEL_REGISTRY, chat_completion, chat_completion_stream
from services.llm_router import LLMRouter, LLMRoutingDecision, LLMTarget
from services.tool_executor import get_tool_executor
from services.tools.weather import get_weather
from services.tools.generic_http import age_predictor, external_api_call
from services.tools.unimed import unimed_consult
from services.tool_prompt_helper import tools_to_prompt, extract_function_call

LOGGER = structlog.get_logger(__name__)
JSON_DECODER = json.JSONDecoder()

DEFAULT_MAX_CONTEXT_LENGTH = 65536
MAX_TOOL_ITERATIONS = 3
MAX_PAGE_TEXT_CHARS = 4000
MAX_DOCUMENT_TEXT_CHARS = 60000
MAX_ENTITY_COUNT = 20
MIN_COMPACTION_LENGTH = 4000
HARD_MESSAGE_CHAR_LIMIT = 20000

def _truncate_tool_result(content: str, max_length: int = 3000) -> str:
    """
    Trunca ou resume resultado de tool para evitar payloads muito grandes.

    Args:
        content: Conteúdo do resultado da tool
        max_length: Tamanho máximo permitido

    Returns:
        Conteúdo truncado ou resumido
    """
    if len(content) <= max_length:
        return content

    # Tentar parsear como JSON e extrair campos importantes
    try:
        data = json.loads(content)

        # Se tem estrutura de sucesso/dados, criar resumo
        if isinstance(data, dict):
            summary = {}

            # Campos de controle
            if "success" in data:
                summary["success"] = data["success"]
            if "sucesso" in data:
                summary["sucesso"] = data["sucesso"]
            if "status_code" in data:
                summary["status_code"] = data["status_code"]
            if "error" in data:
                summary["error"] = data["error"]

            # Se tem dados, extrair apenas campos-chave
            if "dados" in data and isinstance(data["dados"], dict):
                dados = data["dados"]
                summary["dados"] = {}

                # Protocolo
                if "protocolo" in dados:
                    summary["dados"]["protocolo"] = dados["protocolo"]

                # Beneficiário - apenas campos principais
                if "beneficiario" in dados and isinstance(dados["beneficiario"], dict):
                    benef = dados["beneficiario"]
                    summary["dados"]["beneficiario"] = {
                        "nome_beneficiario": benef.get("nome_beneficiario", ""),
                        "cpf": benef.get("cpf", ""),
                        "nrCarteira": benef.get("nrCarteira", ""),
                        "pagador": benef.get("pagador", ""),
                    }

                # Contratos - resumo
                if "contratos" in dados and isinstance(dados["contratos"], dict):
                    contratos = dados["contratos"]
                    summary["dados"]["contratos"] = {
                        "cod_dependencia": contratos.get("cod_dependencia", ""),
                        "qtdDependentes": contratos.get("qtdDependentes", 0),
                    }

                    # Carteira
                    if "carteira" in contratos:
                        summary["dados"]["contratos"]["carteira"] = contratos["carteira"]

                    # Produto - apenas alguns campos
                    if "produto" in contratos and isinstance(contratos["produto"], dict):
                        prod = contratos["produto"]
                        summary["dados"]["contratos"]["produto"] = {
                            "descricao": prod.get("descricao", ""),
                            "codProduto": prod.get("codProduto", ""),
                        }

                    # Valores - apenas campos principais
                    if "valores" in contratos and isinstance(contratos["valores"], dict):
                        vals = contratos["valores"]
                        summary["dados"]["contratos"]["valores"] = {
                            "valorMensalidade": vals.get("valorMensalidade", 0),
                            "totalDebito": vals.get("totalDebito", 0),
                        }

            elif "data" in data:
                # Outra estrutura de dados
                if isinstance(data["data"], dict) and len(str(data["data"])) > max_length:
                    summary["data"] = "[Dados truncados - objeto muito grande]"
                    summary["data_keys"] = list(data["data"].keys()) if isinstance(data["data"], dict) else []
                else:
                    summary["data"] = data["data"]

            result = json.dumps(summary, ensure_ascii=False, indent=2)

            # Se ainda for muito grande, truncar
            if len(result) > max_length:
                result = result[:max_length] + "\n... [truncado por tamanho]"

            return result

    except (json.JSONDecodeError, Exception):
        # Se não for JSON válido, apenas truncar
        pass

    # Truncamento simples
    return content[:max_length] + "\n... [truncado - resposta muito grande]"


def _has_tool_results(messages: List[Any]) -> bool:
    """Check if messages contain tool results from API Agno"""
    for msg in messages:
        # Handle both dict and ChatMessage objects
        if isinstance(msg, dict):
            if msg.get("role") == "tool":
                return True
            # Also check for assistant messages with tool_calls
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                return True
        else:
            if getattr(msg, "role", None) == "tool":
                return True
            if getattr(msg, "role", None) == "assistant" and getattr(msg, "tool_calls", None):
                return True
    return False


def _extract_embedded_json_segment(content: str) -> Optional[tuple[Any, int, int]]:
    """Retorna (objeto_json, início, fim) se houver JSON embutido na string."""
    if not content:
        return None

    for idx, char in enumerate(content):
        if char == "{":
            try:
                data, end = JSON_DECODER.raw_decode(content[idx:])
                return data, idx, idx + end
            except json.JSONDecodeError:
                continue
    return None


def _build_compact_document_payload(data: Any) -> Optional[Dict[str, Any]]:
    """Remove campos pesados (blocks/entities) mantendo apenas texto necessário para o LLM."""
    if not isinstance(data, dict):
        return None

    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        return None

    compact_pages = []
    total_chars = 0
    for page in pages:
        if not isinstance(page, dict):
            continue
        text = page.get("text")
        if not text:
            continue
        text = str(text)
        if len(text) > MAX_PAGE_TEXT_CHARS:
            text = text[:MAX_PAGE_TEXT_CHARS].rstrip() + " ...[trecho truncado]"
        compact_pages.append({
            "page_num": page.get("page_num"),
            "text": text,
        })
        total_chars += len(text)
        if total_chars >= MAX_DOCUMENT_TEXT_CHARS:
            break

    if not compact_pages:
        return None

    compact: Dict[str, Any] = {"pages": compact_pages}
    if "request_id" in data:
        compact["request_id"] = data["request_id"]

    doc_type = data.get("document_type")
    if isinstance(doc_type, dict):
        compact["document_type"] = {
            key: doc_type.get(key)
            for key in ("type", "confidence", "detected_by")
            if doc_type.get(key) is not None
        }
    elif doc_type:
        compact["document_type"] = doc_type

    entities = data.get("entities")
    if isinstance(entities, list) and entities:
        compact_entities = []
        for entity in entities[:MAX_ENTITY_COUNT]:
            if not isinstance(entity, dict):
                continue
            compact_entities.append({
                "type": entity.get("type"),
                "value": entity.get("value"),
                "confidence": entity.get("confidence"),
            })
        if compact_entities:
            compact["entities"] = compact_entities

    return compact


def _compact_json_in_message(content: str) -> Optional[str]:
    """Compacta JSONs grandes embutidos em mensagens, retornando nova string."""
    if not content or len(content) < MIN_COMPACTION_LENGTH:
        return None

    extracted = _extract_embedded_json_segment(content)
    if not extracted:
        return None

    data, start, end = extracted
    compact = _build_compact_document_payload(data)
    if not compact:
        return None

    compact_json = json.dumps(compact, ensure_ascii=False)
    if len(compact_json) >= (end - start):
        return None

    prefix = content[:start].rstrip()
    suffix = content[end:].strip()

    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(compact_json)
    if suffix:
        parts.append(suffix)

    return "\n\n".join(parts)


def _reduce_large_documents(messages: List[ChatMessage]) -> None:
    """Tenta remover metadados pesados antes de contar tokens."""
    for idx, msg in enumerate(messages):
        if not getattr(msg, "content", None):
            continue
        compacted = _compact_json_in_message(msg.content)
        if compacted:
            LOGGER.info(
                "llm_payload_compacted",
                message_index=idx,
                message_role=msg.role,
                original_chars=len(msg.content),
                new_chars=len(compacted),
            )
            msg.content = compacted


def _truncate_plain_text(content: str) -> str:
    """Corta mensagens muito longas mantendo um aviso no final."""
    if len(content) <= HARD_MESSAGE_CHAR_LIMIT:
        return content
    return content[:HARD_MESSAGE_CHAR_LIMIT].rstrip() + "\n... [conteúdo reduzido automaticamente para caber no limite]"


def _count_prompt_tokens(messages: List[ChatMessage]) -> int:
    """Contador simples de tokens baseado em palavras (suficiente para a validação)."""
    total = 0
    for msg in messages:
        if msg.content:
            total += len(msg.content.split())
    return total


def _resolve_context_limit(model_name: Optional[str], provider: Optional[str]) -> int:
    """Resolve context limit based on requested model/provider."""
    if provider and provider.lower() == "openai":
        return DEFAULT_MAX_CONTEXT_LENGTH

    if model_name and model_name in MODEL_REGISTRY:
        limit = MODEL_REGISTRY[model_name].get("context_length")
        if isinstance(limit, int) and limit > 0:
            return limit

    return DEFAULT_MAX_CONTEXT_LENGTH


def _apply_aggressive_truncation(
    messages: List[ChatMessage],
    max_tokens: int,
    context_limit: int,
) -> int:
    """Aplica truncamento progressivo nas mensagens mais longas até atingir o limite."""
    ordered_indexes = sorted(
        range(len(messages)),
        key=lambda idx: len(messages[idx].content or ""),
        reverse=True,
    )

    for idx in ordered_indexes:
        msg = messages[idx]
        if not msg.content:
            continue
        truncated = _truncate_plain_text(msg.content)
        if truncated == msg.content:
            continue
        LOGGER.info(
            "llm_payload_truncated",
            message_index=idx,
            message_role=msg.role,
            original_chars=len(msg.content),
            new_chars=len(truncated),
        )
        msg.content = truncated
        prompt_tokens = _count_prompt_tokens(messages)
        if prompt_tokens + max_tokens <= context_limit:
            return prompt_tokens

    return _count_prompt_tokens(messages)


def normalize_messages_for_llm(raw_messages):
    """Converte mensagens possivelmente com tool_calls em formato aceito pelo vLLM."""
    LOGGER = structlog.get_logger(__name__)
    LOGGER.info("DEBUG normalize: Starting", message_count=len(raw_messages))

    normalized = []
    for idx, msg in enumerate(raw_messages):
        msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else dict(msg)
        role = msg_dict.get("role", "user")
        content = msg_dict.get("content")

        LOGGER.info(f"DEBUG normalize: Processing message {idx}", role=role, has_content=content is not None)

        if role == "tool":
            tool_name = msg_dict.get("name") or "tool"
            tool_call_id = msg_dict.get("tool_call_id") or ""
            payload = msg_dict.get("content", "") or ""

            LOGGER.info("DEBUG normalize: Converting tool to user", tool_name=tool_name)

            # CORRIGIDO: Truncar payload grande para evitar erro 400
            payload = _truncate_tool_result(payload)

            hint = "Agora responda ao usuário original de forma completa e útil com base neste resultado."
            prefix = f"Resultado da função {tool_name}"
            if tool_call_id and tool_call_id not in prefix:
                prefix += f" (execução {tool_call_id})"
            normalized.append({
                "role": "user",
                "content": f"{prefix}:\n{payload}\n\n{hint}"
            })
            continue

        # Se assistant não tem content, pular a mensagem
        if role == "assistant" and not content:
            LOGGER.info("DEBUG normalize: Skipping assistant without content")
            continue

        message = {"role": role, "content": content or ""}
        normalized.append(message)

    LOGGER.info("DEBUG normalize: Done", original_count=len(raw_messages), normalized_count=len(normalized))
    return normalized

router = APIRouter(prefix="/api/v1", tags=["llm"])
settings = get_settings()
router_engine = LLMRouter(strategy=settings.llm_routing_strategy)

# Registrar tools disponíveis
tool_executor = get_tool_executor()
tool_executor.register("unimed_consult", unimed_consult)
tool_executor.register("get_weather", get_weather)
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

    context_limit = _resolve_context_limit(payload.model, payload.provider)
    _reduce_large_documents(payload.messages)
    prompt_tokens = _count_prompt_tokens(payload.messages)
    context_length = prompt_tokens + payload.max_tokens

    if context_length > context_limit:
        prompt_tokens = _apply_aggressive_truncation(
            payload.messages,
            payload.max_tokens,
            context_limit,
        )
        context_length = prompt_tokens + payload.max_tokens

    # Validação: rejeita se ultrapassar limite de 32k tokens
    if context_length > context_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Context length ({context_length} tokens) exceeds maximum allowed ({context_limit} tokens) "
                "even after automatic compaction. Reduza o tamanho do documento ou envie em partes menores."
            ),
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
    raw_payload = payload.model_dump(exclude_none=True, exclude_unset=True)
    normalized_messages = normalize_messages_for_llm(raw_payload.get("messages", []))

    # Se streaming sem tools, usar fluxo antigo
    if payload.stream and not has_tools:
        LOGGER.info("DEBUG: Using streaming flow")
        upstream_payload = dict(raw_payload)
        upstream_payload["stream"] = True

        # Remove fields not supported by vLLM
        upstream_payload.pop("tools", None)
        upstream_payload.pop("tool_choice", None)
        upstream_payload.pop("provider", None)
        upstream_payload.pop("quality_priority", None)

        upstream_payload["messages"] = normalized_messages
        LOGGER.info(
            "DEBUG: Normalized messages for simple flow",
            roles=[msg.get("role") for msg in upstream_payload["messages"]],
        )

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
        upstream_payload = dict(raw_payload)
        upstream_payload.pop("stream", None)

        # Remove tools from payload if present but empty
        upstream_payload.pop("tools", None)
        upstream_payload.pop("tool_choice", None)
        # Remove fields not supported by vLLM
        upstream_payload.pop("provider", None)
        upstream_payload.pop("quality_priority", None)

        upstream_payload["messages"] = normalized_messages
        LOGGER.info(
            "DEBUG: Normalized messages for simple flow",
            roles=[msg.get("role") for msg in upstream_payload["messages"]],
        )

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

    # Fluxo COM TOOLS - usar prompt engineering (vLLM antigo)
    LOGGER.info("DEBUG: Using tools flow (PROMPT ENGINEERING)", num_tools=len(payload.tools))

    # Preparar mensagens COM prompt engineering de tools
    tools_prompt = tools_to_prompt(payload.tools)
    messages = []
    system_injected = False

    for msg in payload.messages:
        msg_dict = msg.model_dump()
        role = msg_dict["role"]

        if role == "system" and not system_injected:
            combined_content = (msg_dict.get("content") or "") + "\n\n" + tools_prompt
            messages.append({"role": "system", "content": combined_content})
            system_injected = True
        elif role == "tool":
            tool_name = msg_dict.get("name") or "tool"
            tool_call_id = msg_dict.get("tool_call_id") or ""
            tool_content = msg_dict.get("content", "")

            tool_content = _truncate_tool_result(tool_content)

            hint = "Agora responda ao usuário com base no resultado."
            prefix = f"Resultado da função {tool_name}"
            messages.append({
                "role": "user",
                "content": f"{prefix}:\n{tool_content}\n\n{hint}"
            })
        else:
            messages.append({
                "role": role,
                "content": msg_dict.get("content", "")
            })

    if not system_injected:
        messages.insert(0, {"role": "system", "content": tools_prompt})

    # Check if this is a second request with tool results
    has_tool_results = _has_tool_results(payload.messages)

    LOGGER.info(
        "DEBUG: Tool flow check",
        has_tool_results=has_tool_results,
        num_messages=len(messages)
    )

    # If we have tool results, just generate the final response
    if has_tool_results:
        # This is the second request from API Agno with tool results
        # We just need to generate the final response
        LOGGER.info("DEBUG: Processing tool results for final response")

        # Make call to LLM for final response
        try:
            current_payload = {
                "model": payload.model,
                "messages": messages,
                "max_tokens": payload.max_tokens,
                "temperature": payload.temperature,
            }

            upstream_response = await chat_completion(
                current_payload,
                target_model,
                router_metadata=router_metadata,
            )
        except Exception as e:
            LOGGER.error("DEBUG: Final response LLM call failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

        # Extract and return the response
        choices_raw = upstream_response.get("choices", [])
        if not choices_raw:
            raise HTTPException(status_code=500, detail="No choices returned from LLM")

        first_choice = choices_raw[0]
        message_dict = first_choice.get("message", {})
        content = message_dict.get("content", "")
        finish_reason = first_choice.get("finish_reason", "stop")

        elapsed = time.perf_counter() - start
        usage = upstream_response.get("usage", {})

        choices = [
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=content),
                finish_reason=finish_reason,
            )
        ]

        usage_metrics = UsageMetrics(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        model_name = upstream_response.get("model", payload.model)
        metadata = upstream_response.setdefault("metadata", {})
        metadata.setdefault("router_target", router_metadata["router_decision"])
        metadata["router_decision"] = router_metadata["router_decision"]
        metadata["router_reason"] = router_metadata["router_reason"]
        metadata["latency_ms"] = int(elapsed * 1000)

        return ChatResponse(
            id=response_id,
            model=model_name,
            choices=choices,
            usage=usage_metrics,
        )

    # This is the first request - check if we need to call tools
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
    response_id = f"chatcmpl-{secrets.token_hex(8)}"

    # Process first request to detect tool calls
    use_forced_tool = bool(forced_tool_choice)
    function_call_data = None
    content = ""

    if use_forced_tool:
        # Use forced tool choice
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
            function_name=forced_tool_choice["name"],
        )
    else:
        # Make call to LLM to check for tool calls
        current_payload = {
            "model": payload.model,
            "messages": messages,
            "max_tokens": payload.max_tokens,
            "temperature": payload.temperature,
            "tools": raw_payload.get("tools", []),  # Pass tools natively
            "tool_choice": raw_payload.get("tool_choice", "auto"),
        }

        LOGGER.info(
            "DEBUG: Calling LLM to check for tool calls",
            num_messages=len(messages),
        )

        try:
            upstream_response = await chat_completion(
                current_payload,
                target_model,
                router_metadata=router_metadata,
            )
        except Exception as e:
            LOGGER.error("DEBUG: Tool LLM call failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")

        # Accumulate tokens
        usage = upstream_response.get("usage", {})
        total_prompt_tokens += usage.get("prompt_tokens", 0)
        total_completion_tokens += usage.get("completion_tokens", 0)

        # Extract first choice
        choices_raw = upstream_response.get("choices", [])
        if not choices_raw:
            raise HTTPException(status_code=500, detail="No choices returned from LLM")

        first_choice = choices_raw[0]
        message_dict = first_choice.get("message", {})
        content = message_dict.get("content", "")
        finish_reason = first_choice.get("finish_reason", "stop")

        # Extract function call from content (prompt engineering)
        function_call_data = extract_function_call(content)

    LOGGER.info(
        "DEBUG: Tool detection result",
        has_function_call=bool(function_call_data),
        content_preview=content[:200] if content else None,
        finish_reason=finish_reason if not use_forced_tool else "tool_calls",
    )

    # If no function call detected, return normal response
    if not function_call_data:
        elapsed = time.perf_counter() - start

        choices = [
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=content),
                finish_reason=finish_reason if not use_forced_tool else "stop",
            )
        ]

        usage_metrics = UsageMetrics(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
        )

        model_name = upstream_response.get("model", payload.model) if not use_forced_tool else payload.model
        metadata = {}
        metadata["router_target"] = router_metadata["router_decision"]
        metadata["router_decision"] = router_metadata["router_decision"]
        metadata["router_reason"] = router_metadata["router_reason"]
        metadata["latency_ms"] = int(elapsed * 1000)

        return ChatResponse(
            id=response_id,
            model=model_name,
            choices=choices,
            usage=usage_metrics,
        )

    # Function call detected - return tool_calls to API Agno
    LOGGER.info(
        "DEBUG: Returning tool_calls to API Agno",
        function_name=function_call_data["name"],
    )

    # Apply defaults from tool definition if available
    function_name = function_call_data["name"]
    arguments_dict = json.loads(function_call_data["arguments"])

    # Look for tool definition in original payload
    if payload.tools:
        for tool in payload.tools:
            if tool.function.name == function_name:
                # Apply parameter defaults
                if tool.function.parameters and "properties" in tool.function.parameters:
                    properties = tool.function.parameters["properties"]
                    for param_name, param_def in properties.items():
                        # If parameter has default and was not provided by LLM
                        if "default" in param_def and param_name not in arguments_dict:
                            arguments_dict[param_name] = param_def["default"]
                            LOGGER.info(
                                "applying_tool_default",
                                function=function_name,
                                parameter=param_name,
                                default_value=param_def["default"]
                            )
                break

    # Serialize back to JSON
    arguments_json = json.dumps(arguments_dict)

    # Create ToolCall object
    tool_call_id = f"call_{secrets.token_hex(12)}"
    tool_call = ToolCall(
        id=tool_call_id,
        type="function",
        function=FunctionCall(
            name=function_name,
            arguments=arguments_json,
        )
    )

    # Return response with tool_calls
    # NOTE: We do NOT execute the tool here - API Agno will do it
    elapsed = time.perf_counter() - start

    choices = [
        ChatChoice(
            index=0,
            message=ChatMessage(
                role="assistant",
                content=None,  # No content when returning tool_calls
                tool_calls=[tool_call]  # Return the tool call
            ),
            finish_reason="tool_calls",  # Important: finish_reason must be "tool_calls"
        )
    ]

    usage_metrics = UsageMetrics(
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_prompt_tokens + total_completion_tokens,
    )

    model_name = payload.model
    metadata = {}
    metadata["router_target"] = router_metadata["router_decision"]
    metadata["router_decision"] = router_metadata["router_decision"]
    metadata["router_reason"] = router_metadata["router_reason"]
    metadata["latency_ms"] = int(elapsed * 1000)

    LOGGER.info(
        "DEBUG: Returning tool_calls response",
        tool_call_id=tool_call_id,
        function_name=function_name,
        arguments_preview=arguments_json[:200] if arguments_json else None,
    )

    return ChatResponse(
        id=response_id,
        model=model_name,
        choices=choices,
        usage=usage_metrics,
    )
