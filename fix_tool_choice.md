# Correção do Problema de Tool Choice

## 🔴 O PROBLEMA

Você estava forçando o uso da ferramenta com `tool_choice` contendo argumentos pré-definidos:

```json
"tool_choice": {
  "type": "function",
  "function": {
    "name": "unimed_consult",
    "arguments": {  // ❌ ERRO AQUI!
      "base_url": "https://...",
      "cidade": "Natal_Tasy",
      "cpf": "00835690490",
      // etc...
    }
  }
}
```

Isso faz o modelo SEMPRE retornar aquela `tool_call` exata, independente do input.

## 🟢 A SOLUÇÃO

### Opção 1: Omitir `tool_choice` completamente (recomendado)

```bash
curl -X POST https://jota.ngrok.app/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -d '{
    "model": "paneas-q32b",
    "messages": [
      {
        "role": "user",
        "content": "oi"
      }
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "unimed_consult",
          "description": "Consulta dados de beneficiário e contratos na API Unimed",
          "parameters": {
            "type": "object",
            "properties": {
              "cidade": {"type": "string"},
              "cpf": {"type": "string"},
              "data_nascimento": {"type": "string"}
            },
            "required": ["cidade", "cpf", "data_nascimento"]
          }
        }
      }
    ]
  }'
```

### Opção 2: Usar `tool_choice: "auto"`

```json
{
  "model": "paneas-q32b",
  "messages": [...],
  "tools": [...],
  "tool_choice": "auto"  // Deixa o modelo decidir
}
```

### Opção 3: Forçar uso de tool SEM argumentos (quando necessário)

Se você REALMENTE precisa forçar o uso de uma tool específica:

```json
{
  "tool_choice": {
    "type": "function",
    "function": {
      "name": "unimed_consult"
      // SEM "arguments" - o modelo vai gerar baseado no contexto
    }
  }
}
```

## 📋 Comportamento Esperado

### Input: "oi"
- **Resposta**: Mensagem de saudação normal
- **tool_calls**: Nenhuma

### Input: "Consulta CPF 00835690490 nascido 28/03/1979 em Natal"
- **Resposta**: `tool_calls` com a função `unimed_consult`
- **Argumentos gerados pelo modelo**:
  ```json
  {
    "cidade": "Natal_Tasy",
    "cpf": "00835690490",
    "data_nascimento": "19790328"
  }
  ```

### Input: "Qual a capital do Brasil?"
- **Resposta**: "A capital do Brasil é Brasília"
- **tool_calls**: Nenhuma

## 🔄 Fluxo Completo Correto

```python
# 1. Usuário envia mensagem
user_input = "Consulta CPF 00835690490..."

# 2. Enviar ao modelo COM tools disponíveis, SEM forçar
response = llm.chat({
    "messages": [{"role": "user", "content": user_input}],
    "tools": tools_definitions,
    # "tool_choice": omitido ou "auto"
})

# 3. Verificar se há tool_calls
if response.has_tool_calls():
    # 4. Executar a ferramenta
    tool_result = execute_tool(response.tool_calls)

    # 5. Enviar resultado de volta
    final_response = llm.chat({
        "messages": [
            user_message,
            response,  # Com tool_calls
            {"role": "tool", "content": tool_result}
        ]
    })

    # 6. Retornar resposta final humanizada
    return final_response.content
else:
    # Não precisou de tool, retornar direto
    return response.content
```

## ✅ Resumo

- **NÃO** force `tool_choice` com `arguments` pré-definidos
- **DEIXE** o modelo decidir quando usar tools (decisão semântica)
- **DEIXE** o modelo extrair argumentos do contexto
- **USE** `tool_choice: "auto"` ou omita completamente

Com isso, o modelo vai:
1. Responder "Olá!" para "oi"
2. Chamar a tool apenas quando relevante
3. Extrair argumentos do contexto do usuário