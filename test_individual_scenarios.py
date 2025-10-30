#!/usr/bin/env python3
"""
Teste individual de cenários críticos para ajustar comportamento
"""

import json
import requests
import time

API_URL = "https://jota.ngrok.app/api/v1/chat/completions"
AUTH_TOKEN = "token_abc123"

def test_scenario(user_message: str, scenario_name: str):
    """Testa um cenário específico"""

    print(f"\n{'='*60}")
    print(f"📝 {scenario_name}")
    print(f"{'='*60}")
    print(f"👤 Cliente: {user_message}")

    # System prompt aprimorado
    system_prompt = """Você é um atendente da Central de Atendimento Unimed Natal.

IMPORTANTE:
- Seja cordial e profissional
- Fale como um atendente humano, não como um robô
- Para consultar contratos, você precisa do CPF e data de nascimento do cliente
- Se o cliente não fornecer esses dados, peça educadamente
- NUNCA mencione termos técnicos, sistemas ou ferramentas
- Quando tiver os dados, diga que vai consultar no sistema

COMO RESPONDER:
- Saudações: Responda cordialmente e ofereça ajuda
- Pedido de consulta SEM dados: "Para consultar seus dados, vou precisar do seu CPF e data de nascimento."
- Pedido de consulta COM dados: Use a ferramenta disponível e depois responda com os resultados
- Perguntas gerais: Responda com informações úteis sobre a Unimed Natal"""

    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 256,
        "temperature": 0.7,
        "tools": [{
            "type": "function",
            "function": {
                "name": "unimed_consult",
                "description": "Consulta dados do beneficiário quando CPF e data de nascimento são fornecidos",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "default": "https://unimed-central-cobranca.paneas.net/api/v1"},
                        "cidade": {"type": "string", "default": "Natal_Tasy"},
                        "tipo": {"type": "string", "default": "Contratos"},
                        "protocolo": {"type": "string", "default": "0"},
                        "cpf": {"type": "string"},
                        "data_nascimento": {"type": "string"}
                    },
                    "required": ["cpf", "data_nascimento"]
                }
            }
        }],
        "tool_choice": "auto"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        result = response.json()

        if "choices" in result:
            message = result["choices"][0]["message"]
            content = message.get("content")
            tool_calls = message.get("tool_calls")

            if tool_calls:
                print("🔧 AÇÃO: Consultando sistema...")
                func = tool_calls[0]["function"]
                print(f"   Função: {func['name']}")
                try:
                    args = json.loads(func["arguments"])
                    print(f"   CPF: {args.get('cpf', 'N/A')}")
                    print(f"   Data: {args.get('data_nascimento', 'N/A')}")
                except:
                    print(f"   Argumentos: {func['arguments'][:50]}...")
            elif content:
                print(f"🤖 Atendente: {content}")

                # Verificar qualidade da resposta
                forbidden = ["função", "executar", "API", "tool", "unimed_consult", "parâmetro"]
                issues = [term for term in forbidden if term.lower() in content.lower()]
                if issues:
                    print(f"⚠️  PROBLEMA: Termos técnicos encontrados: {issues}")
                else:
                    print("✅ Resposta profissional!")
            else:
                print("❌ Sem resposta")
        else:
            print(f"❌ Erro: {result}")

    except Exception as e:
        print(f"❌ Erro na requisição: {e}")

def run_critical_tests():
    """Executa testes dos cenários mais importantes"""

    print("="*80)
    print("🔍 TESTES CRÍTICOS - COMPORTAMENTO PROFISSIONAL")
    print("="*80)

    scenarios = [
        ("oi", "Saudação simples"),
        ("preciso ver meu contrato", "Consulta sem dados"),
        ("meu cpf é 12345678901 e nasci em 15/06/1985", "Consulta com dados completos"),
        ("cpf 98765432100, data nascimento 01/01/1990", "Dados em formato diferente"),
        ("pode verificar o cpf 111.222.333-44? nasceu em 20/12/2000", "CPF formatado"),
        ("obrigado", "Agradecimento"),
    ]

    for message, name in scenarios:
        test_scenario(message, name)
        time.sleep(1)  # Evitar rate limiting

    print("\n" + "="*80)
    print("💡 ANÁLISE")
    print("="*80)
    print("""
    Pontos a verificar:
    1. Respostas sem termos técnicos ✓
    2. Pedido educado de dados quando faltam ✓
    3. Uso correto da ferramenta quando tem dados ✓
    4. Linguagem profissional e humana ✓
    """)

if __name__ == "__main__":
    run_critical_tests()