#!/usr/bin/env python3
"""
Script de teste para function calling na rota /api/v1/chat/completions
"""

import json
import sys
import httpx


def test_basic_completion_without_tools():
    """Testa completion básico sem tools (deve funcionar como antes)"""
    print("\n=== Test 1: Basic completion without tools ===")

    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "user", "content": "Diga olá em uma palavra"}
        ],
        "max_tokens": 50,
    }

    url = "http://localhost:8000/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer token_abc123",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()

        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response ID: {data.get('id')}")
        print(f"✓ Model: {data.get('model')}")
        print(f"✓ Content: {data['choices'][0]['message']['content']}")
        print(f"✓ Finish reason: {data['choices'][0]['finish_reason']}")
        print(f"✓ Usage: {data.get('usage')}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response.text}")
        return False


def test_function_calling_unimed():
    """Testa function calling com a tool unimed_consult"""
    print("\n=== Test 2: Function calling with unimed_consult ===")

    payload = {
        "model": "paneas-q32b",
        "messages": [
            {
                "role": "user",
                "content": "Consulte o beneficiário com CPF 12345678900 e data de nascimento 19900101 na API Unimed de Natal_Tasy para Contratos. Use a URL base https://unimed-central-cobranca.paneas.net/api/v1"
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
        "max_tokens": 500,
    }

    url = "http://localhost:8000/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer token_abc123",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        data = response.json()

        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response ID: {data.get('id')}")
        print(f"✓ Model: {data.get('model')}")

        message = data['choices'][0]['message']
        print(f"✓ Message role: {message.get('role')}")

        if message.get('tool_calls'):
            print(f"✓ Tool calls detected: {len(message['tool_calls'])}")
            for tc in message['tool_calls']:
                print(f"  - Function: {tc['function']['name']}")
                print(f"  - Arguments: {tc['function']['arguments']}")

        if message.get('content'):
            print(f"✓ Content: {message['content'][:200]}...")

        print(f"✓ Finish reason: {data['choices'][0]['finish_reason']}")
        print(f"✓ Usage: {data.get('usage')}")

        metadata = data.get('metadata', {})
        if 'tool_iterations' in metadata:
            print(f"✓ Tool iterations: {metadata['tool_iterations']}")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response.text}")
        return False


def test_streaming_disabled_with_tools():
    """Testa que streaming é desabilitado automaticamente quando tools estão presentes"""
    print("\n=== Test 3: Streaming auto-disabled with tools ===")

    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "user", "content": "Diga olá"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "unimed_consult",
                    "description": "Consulta dados na API Unimed",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_url": {"type": "string"},
                            "cidade": {"type": "string"},
                            "tipo": {"type": "string"},
                            "protocolo": {"type": ["string", "null"]},
                            "cpf": {"type": "string"},
                            "data_nascimento": {"type": "string"}
                        },
                        "required": ["base_url", "cidade", "tipo", "protocolo", "cpf", "data_nascimento"]
                    }
                }
            }
        ],
        "stream": True,  # Tentando forçar streaming
        "max_tokens": 50,
    }

    url = "http://localhost:8000/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer token_abc123",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()

        # Se retornar JSON (não streaming), sucesso
        content_type = response.headers.get('content-type', '')

        if 'application/json' in content_type:
            data = response.json()
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Streaming was disabled (returned JSON)")
            print(f"✓ Response ID: {data.get('id')}")
            return True
        else:
            print(f"✗ Expected JSON but got: {content_type}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        if hasattr(e, 'response'):
            print(f"  Response: {e.response.text}")
        return False


def main():
    print("=" * 60)
    print("Function Calling Test Suite")
    print("=" * 60)

    results = []

    # Test 1: Basic completion
    results.append(("Basic completion without tools", test_basic_completion_without_tools()))

    # Test 2: Function calling
    results.append(("Function calling with unimed_consult", test_function_calling_unimed()))

    # Test 3: Streaming disabled
    results.append(("Streaming auto-disabled with tools", test_streaming_disabled_with_tools()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{len(results)} tests passed")
    print("=" * 60)

    # Exit with appropriate code
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
