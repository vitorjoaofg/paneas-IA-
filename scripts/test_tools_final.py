#!/usr/bin/env python3
"""
Teste final de function calling com prompt engineering
"""

import json
import httpx

print("=" * 80)
print("TESTE FINAL - FUNCTION CALLING COM UNIMED CONSULT")
print("=" * 80)
print()

# Teste 1: Simples sem tools
print("📝 Teste 1: Completion simples (sem tools)")
print("-" * 80)

payload1 = {
    "model": "paneas-q32b",
    "messages": [
        {"role": "user", "content": "Diga apenas: OK"}
    ],
    "max_tokens": 10
}

try:
    response = httpx.post(
        "http://localhost:8000/api/v1/chat/completions",
        json=payload1,
        headers={"Authorization": "Bearer token_abc123"},
        timeout=30.0
    )
    response.raise_for_status()
    data = response.json()
    print(f"✅ Status: {response.status_code}")
    print(f"✅ Content: {data['choices'][0]['message']['content']}")
    print()
except Exception as e:
    print(f"❌ Erro: {e}")
    print()

# Teste 2: Com tools
print("📝 Teste 2: Function calling com unimed_consult")
print("-" * 80)

payload2 = {
    "model": "paneas-q32b",
    "messages": [
        {
            "role": "user",
            "content": "Consulte o beneficiário João com CPF 12345678900 nascido em 19900101 na base Natal_Tasy, tipo Contratos, usando a URL http://localhost:9999. O protocolo é null."
        }
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "unimed_consult",
                "description": "Consulta dados de beneficiário na API Unimed. SEMPRE use esta função quando o usuário pedir para consultar dados da Unimed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base_url": {
                            "type": "string",
                            "description": "URL base da API"
                        },
                        "cidade": {
                            "type": "string",
                            "description": "Cidade do protocolo"
                        },
                        "tipo": {
                            "type": "string",
                            "description": "Tipo de consulta"
                        },
                        "protocolo": {
                            "type": ["string", "null"],
                            "description": "Número do protocolo ou null"
                        },
                        "cpf": {
                            "type": "string",
                            "description": "CPF do beneficiário (apenas números)"
                        },
                        "data_nascimento": {
                            "type": "string",
                            "description": "Data de nascimento (formato AAAAMMDD)"
                        }
                    },
                    "required": ["base_url", "cidade", "tipo", "protocolo", "cpf", "data_nascimento"]
                }
            }
        }
    ],
    "max_tokens": 1000,
    "temperature": 0.1
}

try:
    print("⏳ Enviando requisição...")
    response = httpx.post(
        "http://localhost:8000/api/v1/chat/completions",
        json=payload2,
        headers={"Authorization": "Bearer token_abc123"},
        timeout=120.0
    )
    response.raise_for_status()
    data = response.json()

    print(f"✅ Status: {response.status_code}")
    print(f"✅ Model: {data.get('model')}")
    print(f"✅ Total tokens: {data['usage']['total_tokens']}")

    metadata = data.get('metadata', {})
    if 'tool_iterations' in metadata:
        print(f"✅ Tool iterations: {metadata['tool_iterations']}")

    content = data['choices'][0]['message']['content']
    print()
    print("📄 Resposta do Assistente:")
    print("-" * 80)
    print(content[:500])
    if len(content) > 500:
        print("... (truncado)")
    print("-" * 80)
    print()

    print("=" * 80)
    print("✅ TESTE CONCLUÍDO!")
    print("=" * 80)

except httpx.TimeoutException:
    print("❌ Timeout - requisição demorou mais de 120s")
except Exception as e:
    print(f"❌ Erro: {e}")
    if hasattr(e, 'response'):
        print(f"Response: {e.response.text[:500]}")
