# Function Calling - Guia de Uso

## Visão Geral

A rota `/api/v1/chat/completions` agora suporta **function calling** seguindo o padrão OpenAI. Isso permite que o LLM execute funções localmente durante a conversação.

## Funcionalidades

- ✅ Suporte completo ao formato OpenAI de tools/function calling
- ✅ Execução local de funções com tratamento de erros
- ✅ Streaming desabilitado automaticamente quando tools estão presentes
- ✅ Loop automático de tool calling (até 5 iterações)
- ✅ Logs estruturados de cada execução

## Tools Disponíveis

### `unimed_consult`

Consulta dados de beneficiário na API Unimed.

**Parâmetros:**
- `base_url` (string, required): URL base da API
- `cidade` (string, required): Cidade do protocolo (ex: "Natal_Tasy")
- `tipo` (string, required): Tipo de consulta (ex: "Contratos")
- `protocolo` (string | null, required): Número do protocolo (opcional, pode ser null)
- `cpf` (string, required): CPF do beneficiário (apenas números)
- `data_nascimento` (string, required): Data de nascimento (formato: AAAAMMDD ou AAAA-MM-DD)

**Retorno:**
```json
{
  "success": true,
  "data": { ... },
  "status_code": 200
}
```

Em caso de erro:
```json
{
  "success": false,
  "error": "Descrição do erro",
  "details": "..."
}
```

## Exemplo de Uso

### Request

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer token_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "paneas-q32b",
    "messages": [
      {
        "role": "user",
        "content": "Consulte o beneficiário com CPF 12345678900 e data de nascimento 19900101 na Unimed de Natal_Tasy"
      }
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "unimed_consult",
          "description": "Consulta dados de beneficiário na API Unimed.",
          "parameters": {
            "type": "object",
            "properties": {
              "base_url": {
                "type": "string",
                "description": "URL base da API (ex: https://unimed-central-cobranca.paneas.net/api/v1)"
              },
              "cidade": {
                "type": "string",
                "description": "Cidade do protocolo (ex: Natal_Tasy)"
              },
              "tipo": {
                "type": "string",
                "description": "Tipo de consulta (ex: Contratos)"
              },
              "protocolo": {
                "anyOf": [
                  {"type": "string"},
                  {"type": "null"}
                ],
                "description": "Número do protocolo (opcional)"
              },
              "cpf": {
                "type": "string",
                "description": "CPF do beneficiário"
              },
              "data_nascimento": {
                "type": "string",
                "description": "Data de nascimento (formato: AAAAMMDD ou AAAA-MM-DD)"
              }
            },
            "required": [
              "base_url",
              "cidade",
              "tipo",
              "protocolo",
              "cpf",
              "data_nascimento"
            ]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "max_tokens": 500
  }'
```

### Response

```json
{
  "id": "chatcmpl-a1b2c3d4e5f6",
  "model": "paneas-q32b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Consultei o beneficiário com CPF 123.456.789-00. O status do contrato é ativo e o plano atual é..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 450,
    "completion_tokens": 125,
    "total_tokens": 575
  }
}
```

## Fluxo de Execução

1. **Request inicial**: Cliente envia mensagem com definições de tools
2. **Primeira chamada LLM**: LLM analisa e decide chamar uma função
3. **Execução da tool**: Gateway executa a função localmente
4. **Segunda chamada LLM**: LLM recebe resultado e gera resposta final
5. **Response ao cliente**: Resposta completa com conteúdo gerado

### Exemplo de Fluxo Interno

```
User: "Consulte CPF 123..."
  ↓
LLM (1ª chamada): Decide chamar unimed_consult()
  ↓
Gateway: Executa unimed_consult(cpf="123...", ...)
  ↓
API Unimed: Retorna {"status": "ativo", ...}
  ↓
LLM (2ª chamada): "O beneficiário está ativo..."
  ↓
Cliente: Recebe resposta final
```

## Parâmetros Adicionais

### `tool_choice`

Controla quando o LLM deve usar tools:

- `"auto"` (padrão): LLM decide quando usar
- `"none"`: Nunca usar tools
- `"required"`: Sempre usar uma tool
- `{"type": "function", "function": {"name": "unimed_consult"}}`: Forçar tool específica

### Streaming

**IMPORTANTE**: Quando `tools` está presente, streaming é **automaticamente desabilitado**.

```json
{
  "stream": true,  // Será ignorado se tools estiver presente
  "tools": [...]   // Streaming será false automaticamente
}
```

## Limitações

- **Máximo de 5 iterações**: Para evitar loops infinitos
- **Timeout de 30s**: Para cada requisição HTTP da tool
- **Sem streaming**: Tools e streaming não podem ser usados simultaneamente
- **Whitelist de funções**: Apenas funções registradas podem ser executadas

## Adicionando Novas Tools

### 1. Criar a função

Criar arquivo em `api/services/tools/sua_funcao.py`:

```python
async def minha_funcao(param1: str, param2: int) -> Dict[str, Any]:
    """Descrição da função"""
    # Implementação
    return {"resultado": "..."}
```

### 2. Exportar no `__init__.py`

Editar `api/services/tools/__init__.py`:

```python
from .sua_funcao import minha_funcao

__all__ = ["unimed_consult", "minha_funcao"]
```

### 3. Registrar no router

Editar `api/routers/llm.py`:

```python
from services.tools import unimed_consult, minha_funcao

# ...

tool_executor.register("minha_funcao", minha_funcao)
```

### 4. Usar no client

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "minha_funcao",
        "description": "Descrição clara do que faz",
        "parameters": {
          "type": "object",
          "properties": {
            "param1": {
              "type": "string",
              "description": "Descrição do param1"
            },
            "param2": {
              "type": "integer",
              "description": "Descrição do param2"
            }
          },
          "required": ["param1", "param2"]
        }
      }
    }
  ]
}
```

## Logs e Monitoramento

Cada execução de tool gera logs estruturados:

```json
{
  "event": "tool_execution_start",
  "tool_call_id": "call_123",
  "function": "unimed_consult",
  "arguments": "{...}"
}

{
  "event": "tool_execution_success",
  "tool_call_id": "call_123",
  "function": "unimed_consult"
}
```

Em caso de erro:

```json
{
  "event": "tool_execution_failed",
  "tool_call_id": "call_123",
  "function": "unimed_consult",
  "error": "type_error",
  "details": "..."
}
```

## Testes

Execute os testes automatizados:

```bash
python3 scripts/test_function_calling.py
```

Testes incluídos:
1. ✓ Completion básico sem tools (compatibilidade)
2. ✓ Function calling com unimed_consult
3. ✓ Streaming desabilitado automaticamente

## Troubleshooting

### Error: "Function not found"

A função não está registrada. Verifique:
- A função foi importada em `api/routers/llm.py`?
- `tool_executor.register()` foi chamado?

### Error: "Invalid arguments for function"

Argumentos não correspondem à assinatura da função. Verifique:
- Schema de `parameters` está correto?
- Tipos dos parâmetros correspondem?

### Error: "Maximum tool calling iterations exceeded"

Loop infinito detectado. Verifique:
- LLM está chamando tool repetidamente?
- Tool está retornando resultado válido?

### Response sem tool call

LLM não decidiu usar a tool. Verifique:
- `description` da tool é clara?
- User message menciona informações relevantes?
- `tool_choice` está como "auto" ou "required"?

## Referências

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [vLLM Function Calling](https://docs.vllm.ai/en/latest/features/function_calling.html)
