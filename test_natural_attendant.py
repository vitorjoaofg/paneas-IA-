#!/usr/bin/env python3
"""
Teste de atendente natural - respostas curtas e conversacionais
Simula a conversa mostrada pelo usuário
"""

import json
import requests
import time

API_URL = "http://localhost:8000/api/v1/chat/completions"

# System prompt NATURAL E CONCISO
SYSTEM_PROMPT = """Você é um atendente da Central de Atendimento Unimed Natal.

REGRAS DE OURO:
1. Seja breve e natural - fale como um atendente humano real
2. NUNCA despeje todos os dados do contrato de uma vez
3. Responda APENAS o que foi perguntado
4. Use linguagem conversacional, não formal demais
5. Se já consultou dados, NÃO repita tudo - use o contexto

COLETA DE DADOS:
- Se o cliente não forneceu CPF e data de nascimento, peça educadamente
- NUNCA invente ou assuma valores como 01/01/1990 ou 00000000000
- Só consulte quando tiver AMBOS os dados reais

APÓS CONSULTA BEM-SUCEDIDA:
- Confirme que encontrou: "Encontrei seu cadastro, [Nome]. Como posso ajudar?"
- NÃO liste todos os campos (cpf, carteira, pagador, etc)
- Responda perguntas específicas de forma direta

QUANDO NÃO SOUBER:
- Se a pergunta não é sobre dados do contrato (ex: empréstimos, segunda via)
- Seja direto: "Essa informação não está disponível no sistema que tenho acesso."
- Ofereça alternativa: "Posso transferir para o setor específico."

SAUDAÇÕES:
- Cumprimente de forma natural: "Olá! Como posso ajudar?"
- Não peça dados logo de cara, só se o cliente pedir consulta"""


def call_api(messages, include_tools=True):
    """Faz chamada à API"""
    payload = {
        "model": "paneas-q32b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "max_tokens": 150,  # Limitar para respostas curtas
        "temperature": 0.7
    }

    if include_tools:
        payload["tools"] = [{
            "type": "function",
            "function": {
                "name": "unimed_consult",
                "description": "Consulta dados do beneficiário Unimed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base_url": {
                            "type": "string",
                            "default": "https://unimed-central-cobranca.paneas.net/api/v1"
                        },
                        "cidade": {"type": "string", "default": "Natal_Tasy"},
                        "tipo": {"type": "string", "default": "Contratos"},
                        "protocolo": {"type": "string", "default": "0"},
                        "cpf": {"type": "string"},
                        "data_nascimento": {"type": "string", "description": "Formato DDMMAAAA"}
                    },
                    "required": ["cpf", "data_nascimento"]
                }
            }
        }]
        payload["tool_choice"] = "auto"

    return payload


def simulate_conversation():
    """Simula a conversa exata do exemplo do usuário"""

    print("="*80)
    print("🧪 TESTE: CONVERSA NATURAL E CONCISA")
    print("="*80)

    # Histórico de mensagens
    messages = []

    # Turno 1: Bom dia
    print("\n" + "="*60)
    print("TURNO 1: Saudação")
    print("="*60)
    user_msg = "bom dia"
    print(f"👤 USER: {user_msg}")

    messages.append({"role": "user", "content": user_msg})
    payload = call_api(messages)

    print("\n📤 Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500])

    # Simular resposta esperada
    expected = "Olá! Como posso ajudar?"
    print(f"\n✅ ESPERADO: {expected}")
    print(f"❌ ATUAL: Para realizar a consulta, eu preciso do CPF e da data de nascimento...")
    print("⚠️  PROBLEMA: Pede dados logo de cara, sem esperar o cliente dizer o que quer")

    messages.append({"role": "assistant", "content": expected})

    # Turno 2: Fornece CPF e nascimento
    print("\n" + "="*60)
    print("TURNO 2: Cliente fornece dados")
    print("="*60)
    user_msg = "Meu cpf é 00835690490 e nascimento 28031979"
    print(f"👤 USER: {user_msg}")

    messages.append({"role": "user", "content": user_msg})
    payload = call_api(messages)

    print("\n📤 Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500])

    expected = "Encontrei seu cadastro, Kelly. Como posso ajudar?"
    print(f"\n✅ ESPERADO: {expected}")
    print(f"❌ ATUAL: Lista TODOS os dados (Nome, CPF, Carteira, Pagador, Plano...)")
    print("⚠️  PROBLEMA: Despeja tudo, não é natural")

    # Simular que já consultou
    messages.append({"role": "assistant", "content": expected})

    # Turno 3: Pergunta sobre vencimento
    print("\n" + "="*60)
    print("TURNO 3: Pergunta específica")
    print("="*60)
    user_msg = "Poderia me informar a data de vencimento do meu contrato?"
    print(f"👤 USER: {user_msg}")

    messages.append({"role": "user", "content": user_msg})
    payload = call_api(messages)

    print("\n📤 Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500])

    expected = "Seu contrato é cobrado por boleto mensal, Kelly. A data de vencimento vem impressa no boleto. Posso ajudar com mais algo?"
    print(f"\n✅ ESPERADO: {expected}")
    print(f"❌ ATUAL: Repete explicação longa sobre boletos + 'Estou aqui para ajudar!'")
    print("⚠️  PROBLEMA: Muito formal e longo")

    messages.append({"role": "assistant", "content": expected})

    # Turno 4: Pergunta fora do escopo
    print("\n" + "="*60)
    print("TURNO 4: Pergunta fora do escopo")
    print("="*60)
    user_msg = "Quero saber sobre empréstimos consignados"
    print(f"👤 USER: {user_msg}")

    messages.append({"role": "user", "content": user_msg})
    payload = call_api(messages)

    print("\n📤 Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500])

    expected = "Não tenho acesso a informações sobre empréstimos consignados aqui. Posso transferir você para o financeiro. Quer que eu faça isso?"
    print(f"\n✅ ESPERADO: {expected}")
    print(f"❌ ATUAL: Repete TODOS os dados do contrato novamente + tenta explicar empréstimos")
    print("⚠️  PROBLEMA: Repete dados desnecessariamente, não é direto")

    messages.append({"role": "assistant", "content": expected})

    # Turno 5: Segunda via carteirinha
    print("\n" + "="*60)
    print("TURNO 5: Outra pergunta fora do escopo")
    print("="*60)
    user_msg = "Como posso emitir a segunda via da carteirinha?"
    print(f"👤 USER: {user_msg}")

    messages.append({"role": "user", "content": user_msg})
    payload = call_api(messages)

    print("\n📤 Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500])

    expected = "Você pode emitir pelo app Unimed ou no site na área do cliente. Precisa de ajuda com o acesso?"
    print(f"\n✅ ESPERADO: {expected}")
    print(f"❌ ATUAL: Repete TODOS os dados do contrato NOVAMENTE")
    print("⚠️  PROBLEMA: Completamente fora de contexto, repetitivo")

    messages.append({"role": "assistant", "content": expected})

    # Turno 6: Incluir dependente
    print("\n" + "="*60)
    print("TURNO 6: Pergunta processual")
    print("="*60)
    user_msg = "Como faço para incluir um dependente?"
    print(f"👤 USER: {user_msg}")

    messages.append({"role": "user", "content": user_msg})
    payload = call_api(messages)

    print("\n📤 Payload enviado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500])

    expected = "Para incluir dependente no seu plano coletivo empresarial, você precisa solicitar através do RH da empresa (CEI). Eles fazem a inclusão. Mais alguma dúvida?"
    print(f"\n✅ ESPERADO: {expected}")
    print(f"❌ ATUAL: [preciso testar para ver]")

    print("\n" + "="*80)
    print("📋 RESUMO DOS PROBLEMAS IDENTIFICADOS")
    print("="*80)
    print("""
1. ❌ Pede dados logo na saudação (deveria cumprimentar naturalmente)
2. ❌ Despeja TODOS os dados do contrato após consulta (deveria só confirmar)
3. ❌ Repete dados a cada pergunta (deveria usar contexto)
4. ❌ Respostas muito longas e formais (deveria ser conciso)
5. ❌ Não reconhece perguntas fora do escopo (deveria ser direto)

SOLUÇÃO:
- Ajustar system prompt para ser mais natural e conciso
- Instruir para NÃO despejar todos os dados
- Instruir para usar contexto e não repetir
- Limitar max_tokens para forçar concisão
- Adicionar exemplos de respostas curtas
""")


if __name__ == "__main__":
    simulate_conversation()
