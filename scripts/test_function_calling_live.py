#!/usr/bin/env python3
"""
Teste ao vivo de function calling com mock API Unimed
"""

import json
import httpx


def test_function_calling_with_mock():
    """Testa function calling completo com mock API"""

    print("=" * 80)
    print("TESTE DE FUNCTION CALLING - UNIMED CONSULT")
    print("=" * 80)
    print()

    # Payload da requisição
    payload = {
        "model": "paneas-q32b",
        "messages": [
            {
                "role": "user",
                "content": "Consulte o beneficiário com CPF 123.456.789-00 nascido em 01/01/1990 na Unimed de Natal_Tasy, tipo Contratos. Use a URL base http://localhost:9999"
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
                                "description": "URL base da API (ex: http://localhost:9999)"
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
                                "description": "CPF do beneficiário (apenas números)"
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
        "max_tokens": 800,
        "temperature": 0.7
    }

    url = "http://localhost:8000/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer token_abc123",
        "Content-Type": "application/json",
    }

    print("📤 REQUEST")
    print("-" * 80)
    print(f"URL: {url}")
    print(f"Model: {payload['model']}")
    print(f"User message: {payload['messages'][0]['content']}")
    print(f"Tools: {len(payload['tools'])} tool(s) disponível(is)")
    print(f"  - {payload['tools'][0]['function']['name']}")
    print()

    try:
        print("⏳ Aguardando resposta (pode demorar alguns segundos)...")
        print()

        response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        response.raise_for_status()
        data = response.json()

        print("=" * 80)
        print("📥 RESPONSE")
        print("=" * 80)
        print()

        # Informações básicas
        print("✅ Status Code:", response.status_code)
        print("✅ Response ID:", data.get("id"))
        print("✅ Model:", data.get("model"))
        print()

        # Usage
        usage = data.get("usage", {})
        print("📊 Token Usage:")
        print(f"  - Prompt tokens: {usage.get('prompt_tokens')}")
        print(f"  - Completion tokens: {usage.get('completion_tokens')}")
        print(f"  - Total tokens: {usage.get('total_tokens')}")
        print()

        # Metadata
        metadata = data.get("metadata", {})
        if metadata:
            print("🔧 Metadata:")
            for key, value in metadata.items():
                print(f"  - {key}: {value}")
            print()

        # Choices
        choices = data.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})

            print("💬 Assistant Response:")
            print("-" * 80)
            print(f"Role: {message.get('role')}")
            print(f"Finish reason: {choice.get('finish_reason')}")
            print()

            # Tool calls (se houver)
            tool_calls = message.get("tool_calls")
            if tool_calls:
                print("🔧 Tool Calls Executed:")
                for i, tc in enumerate(tool_calls, 1):
                    print(f"\n  [{i}] {tc['function']['name']}")
                    print(f"      ID: {tc['id']}")
                    print(f"      Arguments: {tc['function']['arguments']}")
                print()

            # Content final
            content = message.get("content")
            if content:
                print("📝 Final Content:")
                print("-" * 80)
                print(content)
                print("-" * 80)
            else:
                print("⚠️  No content in response (might still be processing tools)")

        print()
        print("=" * 80)
        print("✅ TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 80)
        print()

        # Mostrar JSON completo
        print("📄 JSON Completo da Resposta:")
        print("-" * 80)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print()

        return True

    except httpx.TimeoutException:
        print("❌ ERRO: Timeout na requisição")
        print("   A requisição demorou mais de 120 segundos")
        return False

    except httpx.HTTPStatusError as e:
        print(f"❌ ERRO HTTP: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        return False

    except Exception as e:
        print(f"❌ ERRO: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = test_function_calling_with_mock()
    exit(0 if success else 1)
