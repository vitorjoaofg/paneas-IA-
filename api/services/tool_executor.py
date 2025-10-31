import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

import httpx
import structlog

from schemas.llm import ToolCall

LOGGER = structlog.get_logger(__name__)


class ToolExecutor:
    """Executa tool calls de forma segura e gerencia o registro de funções disponíveis"""

    def __init__(self):
        self.registry: Dict[str, Callable] = {}
        self._max_recursion = 5  # Limite de chamadas sequenciais para evitar loops

    def register(self, name: str, func: Callable) -> None:
        """
        Registra uma função disponível para ser chamada pelo LLM

        Args:
            name: Nome da função (deve corresponder ao name no tool definition)
            func: Função async ou sync a ser executada
        """
        self.registry[name] = func
        LOGGER.info("tool_registered", name=name)

    async def execute(self, tool_call: ToolCall) -> str:
        """
        Executa uma tool call e retorna o resultado como JSON string

        Args:
            tool_call: ToolCall contendo nome da função e argumentos

        Returns:
            JSON string com o resultado ou erro
        """
        func_name = tool_call.function.name

        LOGGER.info(
            "tool_execution_start",
            tool_call_id=tool_call.id,
            function=func_name,
            arguments=tool_call.function.arguments,
        )

        func = self.registry.get(func_name)
        if not func:
            # Se não tem função registrada, tentar executor genérico HTTP
            LOGGER.info("tool_not_registered", function=func_name, trying_generic=True)
            return await self._execute_generic_http(tool_call)

        try:
            # Parse arguments
            args = json.loads(tool_call.function.arguments)

            # Execute function
            if callable(func):
                # Check if async
                if asyncio.iscoroutinefunction(func):
                    result = await func(**args)
                else:
                    result = func(**args)
            else:
                raise ValueError(f"Registered function '{func_name}' is not callable")

            LOGGER.info(
                "tool_execution_success",
                tool_call_id=tool_call.id,
                function=func_name,
            )

            # Ensure result is serializable
            if isinstance(result, str):
                return result
            return json.dumps(result)

        except json.JSONDecodeError as e:
            error_result = {
                "error": "Invalid JSON in function arguments",
                "details": str(e),
            }
            LOGGER.error(
                "tool_execution_failed",
                tool_call_id=tool_call.id,
                function=func_name,
                error="json_decode_error",
                details=str(e),
            )
            return json.dumps(error_result)

        except TypeError as e:
            # Se der erro de tipo (argumentos incorretos), tentar executor genérico HTTP
            LOGGER.info(
                "tool_type_error_fallback_to_generic",
                function=func_name,
                error=str(e),
            )
            return await self._execute_generic_http(tool_call)

        except Exception as e:
            error_result = {
                "error": f"Function execution failed: {type(e).__name__}",
                "details": str(e),
            }
            LOGGER.error(
                "tool_execution_failed",
                tool_call_id=tool_call.id,
                function=func_name,
                error=type(e).__name__,
                details=str(e),
            )
            return json.dumps(error_result)

    async def execute_all(self, tool_calls: List[ToolCall]) -> List[Dict[str, Any]]:
        """
        Executa múltiplas tool calls e retorna lista de mensagens de resultado

        Args:
            tool_calls: Lista de ToolCall para executar

        Returns:
            Lista de dicts formatados como mensagens de role=tool
        """
        results = []

        for tool_call in tool_calls:
            content = await self.execute(tool_call)

            # Format as tool message
            results.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.function.name,
                "content": content,
            })

        return results

    async def _execute_generic_http(self, tool_call: ToolCall) -> str:
        """
        Executor genérico para chamadas HTTP quando a função não está registrada
        """
        func_name = tool_call.function.name

        try:
            # Parse arguments
            args = json.loads(tool_call.function.arguments)

            # Verificar se tem URL para chamar
            url_template = args.get("url_template")
            url = args.get("base_url") or args.get("url", "")

            # Rastrear quais parâmetros foram usados no template
            used_in_template = set()

            # Se tem url_template, processar placeholders
            if url_template:
                url = url_template
                # Substituir placeholders {param} pelos valores
                for key, value in args.items():
                    if key not in ["url_template", "method", "headers", "body", "data"]:
                        placeholder = f"{{{key}}}"
                        if placeholder in url:
                            url = url.replace(placeholder, str(value))
                            used_in_template.add(key)

            if not url:
                return json.dumps({
                    "error": f"Function '{func_name}' not registered and no base_url/url/url_template provided for generic HTTP call"
                })

            LOGGER.info(
                "generic_http_execution",
                function=func_name,
                url=url,
                args=args
            )

            # Extrair método HTTP (default GET)
            method = args.get("method", "GET").upper()

            # Headers se fornecidos
            headers = args.get("headers", {})

            # Body/data para POST/PUT/PATCH
            body = args.get("body") or args.get("data")

            # Parâmetros adicionais viram query params (excluir os já usados no template)
            params = {}
            excluded_keys = {"base_url", "url", "url_template", "method", "headers", "body", "data"} | used_in_template
            for key, value in args.items():
                if key not in excluded_keys:
                    params[key] = value

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fazer a requisição
                if method in ["POST", "PUT", "PATCH"] and body:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=body,
                        params=params if params else None
                    )
                else:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params if params else None
                    )

                LOGGER.info(
                    "generic_http_response",
                    function=func_name,
                    status_code=response.status_code,
                    url=url
                )

                # Tentar retornar JSON se possível
                try:
                    data = response.json()
                    return json.dumps({
                        "success": True,
                        "status_code": response.status_code,
                        "data": data
                    }, ensure_ascii=False)
                except:
                    # Se não for JSON, retornar texto
                    return json.dumps({
                        "success": response.status_code < 400,
                        "status_code": response.status_code,
                        "text": response.text[:1000]  # Limitar tamanho
                    }, ensure_ascii=False)

        except json.JSONDecodeError as e:
            return json.dumps({
                "error": "Invalid JSON in function arguments",
                "details": str(e)
            })

        except Exception as e:
            LOGGER.error(
                "generic_http_error",
                function=func_name,
                error=str(e)
            )
            return json.dumps({
                "error": f"HTTP call failed for '{func_name}'",
                "details": str(e)
            })


# Singleton instance
_tool_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Retorna a instância singleton do ToolExecutor"""
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor()
    return _tool_executor
