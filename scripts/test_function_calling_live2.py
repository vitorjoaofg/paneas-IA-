#!/usr/bin/env python3
"""
Teste ao vivo de function calling com mock API Unimed - Versão 2 com prompt mais direto
"""

import json
import httpx


def test_function_calling_with_mock():
    """Testa function calling completo com mock API"""

    print("=" * 80)
    print("TESTE DE FUNCTION CALLING - UNIMED CONSULT (v2)")
    print("=" * 80)
    print()

    # Payload da requisição com prompt mais imperativo
    payload = {
        "model": "paneas-q32b",
        "messages": [
            {
                "role": "system",
                "content": "Você é um assistente que tem acesso a ferramentas para consultar sistemas. Quando o usuário pedir para consultar dados, você DEVE usar a ferramenta disponível."
            },
            {
                "role": "user",
                "content": "Por favor, execute a consulta do beneficiário João com CPF 12345678900 e data de nascimento 19900101 na base de Natal_Tasy, tipo Contratos. A URL base é http://localhost:9999 e o protocolo é null."
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "unimed_consult",
                    "description": "Consulta dados de beneficiário na API Unimed. Use esta função sempre que precisar buscar informações de beneficiários.",
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
                                "type": ["string", "null"],
                                "description": "Número do protocolo (pode ser null se não disponível)"
                            },
                            "cpf": {
                                "type": "string",
                                "description": "CPF do beneficiário (apenas números, sem formatação)"
                            },
                            "data_nascimento": {
                                "type": "string",
                                "description": "Data de nascimento no formato AAAAMMDD (ex: 19900101)"
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
        "tool_choice": "required",  # Forçar uso de tool
        "max_tokens": 1000,
        "temperature": 0.1  # Baixa temperatura para ser mais determinístico
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
    print(f"Tool choice: {payload['tool_choice']} (forçando uso de tool)")
    print(f"System message: {payload['messages'][0]['content'][:60]}...")
    print(f"User message: {payload['messages'][1]['content']}")
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
                    args = json.loads(tc['function']['arguments'])
                    print(f"      Arguments:")
                    for k, v in args.items():
                        print(f"        - {k}: {v}")
                print()

            # Content final
            content = message.get("content")
            if content:
                print("📝 Final Content:")
                print("-" * 80)
                print(content)
                print("-" * 80)
            else:
                print("⚠️  No final content (tool was called but may not have returned result)")

        print()
        print("=" * 80)
        print("✅ TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 80)
        print()

        # Mostrar JSON completo (truncado se muito grande)
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        if len(json_str) > 3000:
            print("📄 JSON Completo da Resposta (truncado):")
            print("-" * 80)
            print(json_str[:3000] + "\n... (truncado)")
        else:
            print("📄 JSON Completo da Resposta:")
            print("-" * 80)
            print(json_str)
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
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_function_calling_with_mock()
    exit(0 if success else 1)
