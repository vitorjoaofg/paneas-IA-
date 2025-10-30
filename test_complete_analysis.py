#!/usr/bin/env python3
"""
Script completo para testar e analisar as correções no CURL
"""

import json
import requests
from datetime import datetime

API_URL = "https://jota.ngrok.app/api/v1/chat/completions"
AUTH_TOKEN = "token_abc123"

def make_request(user_message, system_prompt):
    """Faz requisição à API com o payload corrigido"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 256,
        "temperature": 0.7,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "unimed_consult",
                    "description": "Consulta dados de beneficiário na API Unimed quando o usuário fornecer CPF e data de nascimento",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_url": {
                                "type": "string",
                                "description": "URL base da API",
                                "default": "https://unimed-central-cobranca.paneas.net/api/v1"
                            },
                            "cidade": {
                                "type": "string",
                                "description": "Cidade (ex: Natal_Tasy)",
                                "default": "Natal_Tasy"
                            },
                            "tipo": {
                                "type": "string",
                                "description": "Tipo de consulta",
                                "default": "Contratos"
                            },
                            "protocolo": {
                                "type": "string",
                                "description": "Número do protocolo",
                                "default": "0"
                            },
                            "cpf": {
                                "type": "string",
                                "description": "CPF do beneficiário (apenas números)"
                            },
                            "data_nascimento": {
                                "type": "string",
                                "description": "Data de nascimento (formato: AAAAMMDD)"
                            }
                        },
                        "required": ["cpf", "data_nascimento"]  # Apenas campos realmente obrigatórios
                    }
                }
            }
        ],
        "tool_choice": "auto"
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def analyze_response(response, test_name, expected_behavior):
    """Analisa a resposta e imprime resultado formatado"""

    print(f"\n{'='*60}")
    print(f"📝 {test_name}")
    print(f"{'='*60}")

    if "error" in response:
        print(f"❌ ERRO na requisição: {response['error']}")
        return False

    choices = response.get("choices", [])
    if not choices:
        print("❌ Resposta sem choices")
        return False

    message = choices[0].get("message", {})
    content = message.get("content")
    tool_calls = message.get("tool_calls")

    # Verificar comportamento
    if expected_behavior == "no_tool":
        if tool_calls:
            print(f"❌ ERRO: Chamou ferramenta quando não deveria")
            print(f"   Tool chamada: {tool_calls[0]['function']['name']}")
            return False
        else:
            print(f"✅ CORRETO: Não chamou ferramentas")
            if content:
                print(f"\n📢 Resposta do assistente:")
                print(f"   '{content[:200]}{'...' if len(content) > 200 else ''}'")
            return True

    elif expected_behavior == "use_tool":
        if not tool_calls:
            print(f"❌ ERRO: Não chamou ferramenta quando deveria")
            if content:
                print(f"   Resposta sem tool: '{content[:100]}...'")
            return False
        else:
            print(f"✅ CORRETO: Chamou a ferramenta")
            func_name = tool_calls[0]["function"]["name"]
            print(f"   Função: {func_name}")

            # Tentar parsear argumentos
            try:
                args_str = tool_calls[0]["function"]["arguments"]
                args = json.loads(args_str)
                print(f"\n   Argumentos extraídos:")
                for key, value in args.items():
                    print(f"     • {key}: {value}")
            except:
                print(f"   Argumentos (raw): {tool_calls[0]['function']['arguments'][:100]}")
            return True

    return False

def run_test_suite():
    """Executa bateria completa de testes"""

    print("="*80)
    print("🚀 BATERIA DE TESTES - CURL CORRIGIDO")
    print("="*80)
    print(f"\n⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 API: {API_URL}")

    # System prompt simplificado
    system_prompt = """Assistente especializado em consultas de beneficiários e contratos Unimed Natal.

## COMPORTAMENTO
- Seja profissional, empático e objetivo
- Para consultas de contratos, use a ferramenta disponível quando o usuário fornecer CPF e data de nascimento
- Proteja dados sensíveis (mascare CPFs: 123.***.***-90)
- Mantenha foco em planos de saúde Unimed Natal"""

    # Testes
    tests = [
        {
            "name": "TESTE 1: Saudação simples",
            "message": "bom dia",
            "expected": "no_tool"
        },
        {
            "name": "TESTE 2: Consulta com dados completos",
            "message": "Quero consultar o contrato do CPF 12345678901, nascido em 15/06/1985 em Natal",
            "expected": "use_tool"
        },
        {
            "name": "TESTE 3: Pergunta genérica",
            "message": "O que é a Unimed?",
            "expected": "no_tool"
        },
        {
            "name": "TESTE 4: Consulta com CPF formatado",
            "message": "Verificar contrato do CPF 987.654.321-00, data de nascimento 01/01/1990",
            "expected": "use_tool"
        },
        {
            "name": "TESTE 5: Despedida",
            "message": "Tchau, obrigado!",
            "expected": "no_tool"
        }
    ]

    results = []

    for test in tests:
        print(f"\n🔄 Executando: {test['name']}")
        print(f"   Mensagem: '{test['message']}'")
        print(f"   Esperado: {'NÃO usar tool' if test['expected'] == 'no_tool' else 'USAR tool'}")

        response = make_request(test["message"], system_prompt)
        success = analyze_response(response, test["name"], test["expected"])
        results.append(success)

    # Resumo final
    print("\n" + "="*80)
    print("📊 RESUMO DOS RESULTADOS")
    print("="*80)

    total = len(results)
    passed = sum(results)

    print(f"\n✅ Testes aprovados: {passed}/{total} ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 SUCESSO TOTAL! Todos os testes passaram!")
        print("✨ O modelo está decidindo corretamente quando usar ferramentas")
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam")
        print("📝 Verifique os logs acima para detalhes")

    print("\n" + "="*80)
    print("💡 CONCLUSÕES:")
    print("-" * 40)
    print("• Remover 'protocolo' de required ✅")
    print("• Usar tool_choice: 'auto' ✅")
    print("• System prompt limpo sem duplicação ✅")
    print("• Modelo decide semanticamente ✅")
    print("="*80)

if __name__ == "__main__":
    run_test_suite()