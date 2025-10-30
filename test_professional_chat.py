#!/usr/bin/env python3
"""
Bateria completa de testes para atendente profissional Unimed
Simula conversa real cliente-atendente com 20 turnos
"""

import json
import requests
import time
from typing import Dict, List, Tuple

API_URL = "https://jota.ngrok.app/api/v1/chat/completions"
AUTH_TOKEN = "token_abc123"

# System prompt PROFISSIONAL - sem termos técnicos
SYSTEM_PROMPT = """Você é um atendente da Unimed Natal, especializado em consultas de contratos e benefícios.

## IDENTIDADE
Você é um(a) atendente humano(a) da Central de Atendimento Unimed Natal. Seja cordial, profissional e empático.

## COMPORTAMENTO ESSENCIAL
- Trate o cliente com respeito e cordialidade
- Use linguagem natural, como um atendente real usaria
- NUNCA mencione "funções", "ferramentas", "API" ou termos técnicos
- NUNCA invente dados ou informações
- Sempre proteja dados sensíveis (use CPF com máscara: 123.***.***-90)

## QUANDO PRECISAR DE DADOS PARA CONSULTA
Se o cliente quiser consultar contratos/benefícios mas não forneceu dados:
- Peça educadamente: "Para consultar seus dados, vou precisar do seu CPF e data de nascimento."
- NÃO mencione sistemas ou ferramentas
- Fale como se fosse verificar pessoalmente

## FORMATAÇÃO
- Use parágrafos curtos e claros
- Destaque informações importantes
- Seja objetivo mas cordial
- Termine sempre oferecendo mais ajuda

## PRIVACIDADE
- Sempre mascare CPFs ao exibir
- Nunca exponha dados completos de cartão
- Siga rigorosamente a LGPD"""

def create_payload(messages: List[Dict], include_tools: bool = True) -> Dict:
    """Cria payload para a API"""
    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "max_tokens": 256,
        "temperature": 0.7
    }

    if include_tools:
        payload["tools"] = [{
            "type": "function",
            "function": {
                "name": "unimed_consult",
                "description": "Consulta dados de beneficiário. Use APENAS quando o cliente fornecer CPF E data de nascimento explicitamente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base_url": {
                            "type": "string",
                            "default": "https://unimed-central-cobranca.paneas.net/api/v1"
                        },
                        "cidade": {
                            "type": "string",
                            "default": "Natal_Tasy"
                        },
                        "tipo": {
                            "type": "string",
                            "default": "Contratos"
                        },
                        "protocolo": {
                            "type": "string",
                            "default": "0"
                        },
                        "cpf": {
                            "type": "string",
                            "description": "CPF fornecido pelo cliente"
                        },
                        "data_nascimento": {
                            "type": "string",
                            "description": "Data nascimento fornecida"
                        }
                    },
                    "required": ["cpf", "data_nascimento"]
                }
            }
        }]
        payload["tool_choice"] = "auto"

    return payload

def test_conversation(messages: List[Dict], test_name: str, expected_behavior: str) -> Tuple[bool, str]:
    """Testa um turno da conversa"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    payload = create_payload(messages)

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        result = response.json()

        if "choices" not in result:
            return False, "Erro na resposta"

        message = result["choices"][0]["message"]
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        # Verificar se há termos técnicos proibidos
        forbidden_terms = ["função", "function", "API", "tool", "executar", "unimed_consult", "parâmetro", "JSON"]
        content_lower = content.lower()

        for term in forbidden_terms:
            if term.lower() in content_lower:
                return False, f"❌ Termo técnico encontrado: '{term}'"

        # Verificar comportamento esperado
        if expected_behavior == "no_tool":
            if tool_calls:
                return False, "❌ Chamou ferramenta quando não deveria"
            return True, content

        elif expected_behavior == "use_tool":
            if not tool_calls:
                return False, "❌ Não chamou ferramenta quando deveria"
            return True, f"✅ Chamou ferramenta corretamente"

        elif expected_behavior == "ask_data":
            if tool_calls:
                return False, "❌ Não deveria chamar ferramenta sem dados"
            # Verificar se está pedindo dados de forma profissional
            if "cpf" in content_lower and "data" in content_lower:
                return True, content
            return False, "❌ Não pediu os dados necessários"

        return True, content

    except Exception as e:
        return False, f"Erro: {str(e)}"

def run_complete_conversation():
    """Executa conversa completa de 20 turnos"""
    print("="*80)
    print("🏥 TESTE COMPLETO - ATENDIMENTO UNIMED NATAL")
    print("="*80)
    print("\n📋 Simulando conversa real entre cliente e atendente\n")

    # Conversa completa
    test_scenarios = [
        # Início
        {
            "user": "oi",
            "expected": "no_tool",
            "description": "Saudação inicial"
        },
        {
            "user": "bom dia",
            "expected": "no_tool",
            "description": "Saudação formal"
        },
        {
            "user": "preciso de ajuda com meu plano",
            "expected": "no_tool",
            "description": "Pedido genérico de ajuda"
        },
        {
            "user": "quero ver meu contrato",
            "expected": "ask_data",
            "description": "Consulta sem dados"
        },
        {
            "user": "meu cpf é 12345678901",
            "expected": "ask_data",
            "description": "Apenas CPF fornecido"
        },
        {
            "user": "nasci em 15/06/1985",
            "expected": "use_tool",
            "description": "Data fornecida (completa dados)"
        },
        {
            "user": "qual o telefone da unimed?",
            "expected": "no_tool",
            "description": "Pergunta informativa"
        },
        {
            "user": "quais planos vocês tem?",
            "expected": "no_tool",
            "description": "Informação sobre produtos"
        },
        {
            "user": "consultar cpf 98765432100 nascido em 01/01/1990",
            "expected": "use_tool",
            "description": "Consulta com todos os dados"
        },
        {
            "user": "obrigado pela ajuda",
            "expected": "no_tool",
            "description": "Agradecimento"
        },
        {
            "user": "quanto custa o plano bronze?",
            "expected": "no_tool",
            "description": "Pergunta sobre valores"
        },
        {
            "user": "posso marcar consulta?",
            "expected": "no_tool",
            "description": "Pergunta sobre serviços"
        },
        {
            "user": "verificar contrato do cpf 111.222.333-44, nascimento 20/12/2000",
            "expected": "use_tool",
            "description": "CPF formatado com dados completos"
        },
        {
            "user": "qual horário de atendimento?",
            "expected": "no_tool",
            "description": "Informação operacional"
        },
        {
            "user": "tenho uma reclamação",
            "expected": "no_tool",
            "description": "Início de reclamação"
        },
        {
            "user": "como faço para incluir dependente?",
            "expected": "no_tool",
            "description": "Dúvida processual"
        },
        {
            "user": "meu filho precisa de autorização",
            "expected": "no_tool",
            "description": "Caso específico sem dados"
        },
        {
            "user": "pode consultar cpf 55566677788? nasceu em 10/10/1995",
            "expected": "use_tool",
            "description": "Consulta de terceiro"
        },
        {
            "user": "até logo",
            "expected": "no_tool",
            "description": "Despedida"
        },
        {
            "user": "tchau, bom trabalho!",
            "expected": "no_tool",
            "description": "Despedida cordial"
        }
    ]

    messages = []
    all_passed = True
    results_log = []

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*60}")
        print(f"TURNO {i}/20: {scenario['description']}")
        print(f"{'='*60}")
        print(f"👤 CLIENTE: {scenario['user']}")

        # Adicionar mensagem do usuário
        messages.append({"role": "user", "content": scenario["user"]})

        # Testar
        success, response = test_conversation(messages, f"Turno {i}", scenario["expected"])

        # Adicionar resposta do assistente para próximo turno
        if success:
            print(f"🤖 ATENDENTE: {response[:200]}{'...' if len(response) > 200 else ''}")
            messages.append({"role": "assistant", "content": response})
            status = "✅ PASSOU"
        else:
            print(f"❌ PROBLEMA: {response}")
            all_passed = False
            status = "❌ FALHOU"
            # Adicionar resposta genérica para continuar teste
            messages.append({"role": "assistant", "content": "Entendi. Como posso ajudar?"})

        results_log.append({
            "turno": i,
            "user": scenario["user"],
            "expected": scenario["expected"],
            "status": status,
            "response": response[:100] if success else response
        })

        time.sleep(0.5)  # Evitar rate limiting

    # Resumo final
    print("\n" + "="*80)
    print("📊 RESUMO DOS RESULTADOS")
    print("="*80)

    passed = sum(1 for r in results_log if "✅" in r["status"])
    total = len(results_log)

    print(f"\n{'Turno':<6} {'Status':<12} {'Cliente':<40} {'Comportamento':<20}")
    print("-"*80)
    for r in results_log:
        user_msg = r["user"][:37] + "..." if len(r["user"]) > 40 else r["user"]
        print(f"{r['turno']:<6} {r['status']:<12} {user_msg:<40} {r['expected']:<20}")

    print(f"\n✅ Taxa de sucesso: {passed}/{total} ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 SUCESSO TOTAL! Salvando configuração final...")

        # Salvar configuração final
        final_config = {
            "curl_command": f"""curl -X POST "{API_URL}" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {AUTH_TOKEN}" \\
  -d @payload.json""",
            "payload": create_payload([]),
            "system_prompt": SYSTEM_PROMPT,
            "test_results": {
                "total_tests": total,
                "passed": passed,
                "success_rate": f"{passed/total*100:.1f}%",
                "results": results_log
            }
        }

        with open("/home/jota/tools/paneas-col/final_validated_config.json", "w") as f:
            json.dump(final_config, f, indent=2, ensure_ascii=False)

        print("✅ Configuração salva em: final_validated_config.json")
    else:
        print(f"\n⚠️ {total - passed} testes falharam. Ajustes necessários.")

    return all_passed

if __name__ == "__main__":
    success = run_complete_conversation()

    if not success:
        print("\n🔧 Recomendações:")
        print("1. Ajustar system prompt para ser mais natural")
        print("2. Remover qualquer menção a termos técnicos")
        print("3. Treinar respostas mais humanas")