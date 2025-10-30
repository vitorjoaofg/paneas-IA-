"""
Exemplo completo do fluxo de conversação com tools
Demonstra o ciclo completo de decisão semântica e execução
"""

import json
import requests
from typing import Dict, List

def simulate_complete_flow():
    """Simula o fluxo completo de uma conversa com decisão de tools"""

    api_url = "https://jota.ngrok.app/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer token_abc123"
    }

    print("=" * 80)
    print("FLUXO COMPLETO DE CONVERSAÇÃO COM TOOLS - EXEMPLO PRÁTICO")
    print("=" * 80)

    # =========== EXEMPLO 1: CONSULTA QUE PRECISA DE TOOL ===========
    print("\n🔹 EXEMPLO 1: Consulta Unimed (DEVE usar tool)")
    print("-" * 60)

    user_message = "Quero ver os contratos do CPF 00835690490, nascido em 28/03/1979, de Natal"

    print(f"👤 USUÁRIO: {user_message}\n")

    # PASSO 1: Primeira chamada ao modelo
    print("📤 PASSO 1: Enviando ao modelo com tools disponíveis...")

    initial_payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "user", "content": user_message}
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
                            "cidade": {"type": "string", "description": "Cidade (ex: Natal_Tasy)"},
                            "cpf": {"type": "string", "description": "CPF do beneficiário"},
                            "data_nascimento": {"type": "string", "description": "Data nascimento AAAAMMDD"}
                        },
                        "required": ["cidade", "cpf", "data_nascimento"]
                    }
                }
            }
        ]
        # NÃO incluir tool_choice - deixar o modelo decidir!
    }

    print("Payload (simplificado):")
    print(json.dumps({
        "messages": initial_payload["messages"],
        "tools": "[definições...]",
        "tool_choice": "NÃO INCLUÍDO (auto)"
    }, indent=2))

    # Resposta simulada do modelo
    print("\n📥 RESPOSTA DO MODELO:")
    model_response_1 = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,  # Null quando há tool_calls
                "tool_calls": [{
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "unimed_consult",
                        "arguments": json.dumps({
                            "cidade": "Natal_Tasy",
                            "cpf": "00835690490",
                            "data_nascimento": "19790328"
                        })
                    }
                }]
            },
            "finish_reason": "tool_calls"
        }]
    }

    print("✅ Modelo decidiu usar a tool 'unimed_consult'")
    print("📋 Argumentos extraídos do contexto:")
    args = json.loads(model_response_1["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
    print(json.dumps(args, indent=2))

    # PASSO 2: Executar a ferramenta
    print("\n🔧 PASSO 2: Executando a função Python real...")

    def unimed_consult_function(cidade, cpf, data_nascimento):
        """Simulação da função real"""
        # Aqui faria a chamada real à API
        return {
            "success": True,
            "data": {
                "beneficiario": {
                    "nome": "João Silva",
                    "cpf": cpf,
                    "data_nascimento": data_nascimento
                },
                "contratos": [
                    {"numero": "123456", "plano": "Bronze", "status": "Ativo"},
                    {"numero": "789012", "plano": "Prata", "status": "Ativo"}
                ]
            }
        }

    tool_result = unimed_consult_function(**args)
    print("📊 Resultado da execução:")
    print(json.dumps(tool_result, indent=2))

    # PASSO 3: Enviar resultado de volta ao modelo
    print("\n📤 PASSO 3: Enviando resultado da tool de volta ao modelo...")

    # Construir nova conversa com o resultado
    followup_messages = [
        {"role": "user", "content": user_message},
        model_response_1["choices"][0]["message"],  # Mensagem com tool_calls
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "content": json.dumps(tool_result)
        }
    ]

    print("Mensagens acumuladas:")
    for i, msg in enumerate(followup_messages, 1):
        role = msg.get("role")
        if role == "tool":
            print(f"  {i}. role: tool (resultado da execução)")
        elif msg.get("tool_calls"):
            print(f"  {i}. role: assistant (com tool_calls)")
        else:
            print(f"  {i}. role: {role}")

    # Resposta final simulada
    print("\n📥 RESPOSTA FINAL DO MODELO:")
    final_response = """Encontrei os contratos do beneficiário João Silva (CPF: 008.356.904-90):

    📋 Contratos ativos:
    • Contrato nº 123456 - Plano Bronze (Ativo)
    • Contrato nº 789012 - Plano Prata (Ativo)

    Ambos os contratos estão ativos e em dia."""

    print(f"🤖 ASSISTENTE: {final_response}")

    # =========== EXEMPLO 2: SAUDAÇÃO SIMPLES ===========
    print("\n" + "=" * 80)
    print("🔹 EXEMPLO 2: Saudação (NÃO deve usar tool)")
    print("-" * 60)

    user_message_2 = "Oi, bom dia!"
    print(f"👤 USUÁRIO: {user_message_2}\n")

    print("📤 Enviando ao modelo (com tools disponíveis mas não forçadas)...")

    # Resposta simulada - SEM tool_calls
    print("\n📥 RESPOSTA DO MODELO:")
    model_response_2 = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Olá! Bom dia! Como posso ajudar você hoje? Posso consultar informações sobre contratos e beneficiários da Unimed se precisar."
            },
            "finish_reason": "stop"  # Não "tool_calls"
        }]
    }

    print("✅ Modelo decidiu NÃO usar tools")
    print(f"🤖 ASSISTENTE: {model_response_2['choices'][0]['message']['content']}")

    # =========== RESUMO ===========
    print("\n" + "=" * 80)
    print("📊 RESUMO DO FLUXO CORRETO")
    print("=" * 80)

    print("""
    1️⃣ DECISÃO SEMÂNTICA:
       • O modelo analisa o contexto e DECIDE se precisa de tools
       • NÃO forçamos com tool_choice pré-preenchido

    2️⃣ EXTRAÇÃO DE ARGUMENTOS:
       • Se decidir usar tool, o modelo EXTRAI os argumentos do contexto
       • Exemplo: "CPF 00835690490" → {"cpf": "00835690490"}

    3️⃣ EXECUÇÃO REAL:
       • O runtime executa a função Python real
       • Retorna resultado estruturado

    4️⃣ RESPOSTA HUMANIZADA:
       • Modelo recebe o resultado e gera resposta em linguagem natural
       • Transforma JSON em texto compreensível

    ❌ ERRO COMUM:
       Usar tool_choice com arguments já preenchidos força o uso sempre

    ✅ SOLUÇÃO:
       Omitir tool_choice ou usar "auto" - deixar o modelo decidir!
    """)


if __name__ == "__main__":
    simulate_complete_flow()