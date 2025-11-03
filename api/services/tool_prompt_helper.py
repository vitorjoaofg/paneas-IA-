"""
Helper para converter tools em prompts e parsear respostas do LLM
Usa prompt engineering quando o modelo não tem suporte nativo a function calling
"""

import json
import re
from typing import Any, Dict, List, Optional

from schemas.llm import Tool


def tools_to_prompt(tools: List[Tool]) -> str:
    """
    Converte lista de tools em um system prompt que ensina o LLM a chamar funções

    Args:
        tools: Lista de Tool definitions

    Returns:
        System prompt formatado
    """
    tools_desc = []

    for tool in tools:
        func = tool.function
        params_str = json.dumps(func.parameters, indent=2)

        tools_desc.append(f"""
Função: {func.name}
Descrição: {func.description}
Parâmetros: {params_str}
""")

    system_prompt = f"""Você tem acesso às seguintes funções:

{chr(10).join(tools_desc)}

Para chamar uma função, responda EXATAMENTE no seguinte formato JSON:

```json
{{
  "function_call": {{
    "name": "nome_da_funcao",
    "arguments": {{
      "parametro1": "valor1",
      "parametro2": "valor2"
    }}
  }}
}}
```

IMPORTANTE:
- Retorne APENAS o JSON, sem texto adicional antes ou depois
- Use aspas duplas para strings
- Certifique-se de que o JSON seja válido
- Inclua TODOS os parâmetros obrigatórios
- Use os nomes exatos dos parâmetros conforme declarados acima
- Respeite o formato especificado na descrição de cada parâmetro (ex.: datas no padrão AAAAMMDD, CPFs apenas números)
- Não invente campos adicionais nem renomeie parâmetros
- Se não precisar chamar nenhuma função, responda normalmente com texto

Quando você retornar um function_call, eu executarei a função e retornarei o resultado para você processar."""

    return system_prompt


def extract_function_call(content: str) -> Optional[Dict[str, Any]]:
    """
    Extrai function call do conteúdo da resposta do LLM

    Args:
        content: Conteúdo da resposta do assistente

    Returns:
        Dict com function_call ou None se não houver
    """
    if not content:
        return None

    # Primeiro, tentar extrair todo o conteúdo do code block
    # Usando um método mais robusto para capturar JSON aninhado
    json_str = None

    # Método 1: Extrair de code block markdown
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()

    # Método 2: Se não achou em code block, tentar achar JSON direto
    if not json_str:
        # Procurar por JSON que começa com { e termina com } balanceado
        # Encontrar primeiro { e contar brackets para achar o fechamento correto
        start_idx = content.find('{')
        if start_idx >= 0:
            bracket_count = 0
            in_string = False
            escape_next = False

            for i in range(start_idx, len(content)):
                char = content[i]

                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_str = content[start_idx:i+1]
                            break

    if not json_str:
        return None

    try:
        parsed = json.loads(json_str)

        # Verificar se tem a estrutura esperada
        if "function_call" in parsed:
            fc = parsed["function_call"]
            if "name" in fc and "arguments" in fc:
                return {
                    "name": fc["name"],
                    "arguments": json.dumps(fc["arguments"])
                }
    except json.JSONDecodeError:
        return None

    return None


def inject_tools_in_messages(
    messages: List[Dict[str, Any]],
    tools: List[Tool]
) -> List[Dict[str, Any]]:
    """
    Injeta system prompt com tools nas mensagens

    Args:
        messages: Lista de mensagens originais
        tools: Lista de tools disponíveis

    Returns:
        Nova lista de mensagens com system prompt injetado
    """
    tools_prompt = tools_to_prompt(tools)

    # Procurar por system message existente
    new_messages = []
    system_found = False

    for msg in messages:
        if msg.get("role") == "system":
            # Combinar com tools prompt
            combined = msg["content"] + "\n\n" + tools_prompt
            new_messages.append({"role": "system", "content": combined})
            system_found = True
        else:
            new_messages.append(msg)

    # Se não há system message, adicionar no início
    if not system_found:
        new_messages.insert(0, {"role": "system", "content": tools_prompt})

    return new_messages
