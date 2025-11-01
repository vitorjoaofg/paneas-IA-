#!/bin/bash
# Teste turno a turno da conversa

API_URL="http://localhost:8000/api/v1/chat/completions"

# System prompt melhorado
SYSTEM_PROMPT='Você é atendente da Central Unimed Natal.

COMO FALAR:
- Seja breve e natural como um atendente real
- Use poucas palavras, seja direto
- Não seja formal demais

COLETA DE DADOS:
- Só peça CPF e data se o cliente quiser consultar algo
- NUNCA invente dados

APÓS CONSULTAR:
- Confirme que encontrou: "Oi [Nome], encontrei seu cadastro. O que precisa?"
- NÃO liste tudo (cpf, carteira, pagador, plano, etc)
- Só responda o que for perguntado

SE NÃO SOUBER:
- Seja direto: "Não tenho essa info aqui."
- Ofereça ajuda: "Quer que transfira pro setor certo?"

EXEMPLOS:
User: bom dia
Bot: Oi! Em que posso ajudar?

User: meu cpf é 123 e nasci 01/01/1990
Bot: Achei seu cadastro, Maria. O que precisa saber?

User: qual o vencimento?
Bot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?

User: quero fazer empréstimo
Bot: Empréstimo não é aqui. Quer que transfira pro financeiro?'

echo "======================================"
echo "TURNO 1: Saudação"
echo "======================================"
cat > /tmp/payload1.json << 'EOF'
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Você é atendente da Central Unimed Natal.\n\nCOMO FALAR:\n- Seja breve e natural como um atendente real\n- Use poucas palavras, seja direto\n- Não seja formal demais\n\nCOLETA DE DADOS:\n- Só peça CPF e data se o cliente quiser consultar algo\n- NUNCA invente dados\n\nAPÓS CONSULTAR:\n- Confirme que encontrou: \"Oi [Nome], encontrei seu cadastro. O que precisa?\"\n- NÃO liste tudo (cpf, carteira, pagador, plano, etc)\n- Só responda o que for perguntado\n\nSE NÃO SOUBER:\n- Seja direto: \"Não tenho essa info aqui.\"\n- Ofereça ajuda: \"Quer que transfira pro setor certo?\"\n\nEXEMPLOS:\nUser: bom dia\nBot: Oi! Em que posso ajudar?\n\nUser: meu cpf é 123 e nasci 01/01/1990\nBot: Achei seu cadastro, Maria. O que precisa saber?\n\nUser: qual o vencimento?\nBot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?\n\nUser: quero fazer empréstimo\nBot: Empréstimo não é aqui. Quer que transfira pro financeiro?"
    },
    {
      "role": "user",
      "content": "bom dia"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
EOF

echo "USER: bom dia"
echo ""
echo "Chamando API..."
RESPONSE1=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -H "Authorization: Bearer token_abc123" \
  -d @/tmp/payload1.json)

echo "$RESPONSE1" | jq -r '.choices[0].message.content' > /tmp/resp1.txt
echo "BOT: $(cat /tmp/resp1.txt)"
echo ""

# Salvar resposta para próximo turno
RESP1_CONTENT=$(cat /tmp/resp1.txt)

echo ""
echo "======================================"
echo "TURNO 2: Cliente fornece dados"
echo "======================================"
cat > /tmp/payload2.json << EOF
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Você é atendente da Central Unimed Natal.\n\nCOMO FALAR:\n- Seja breve e natural como um atendente real\n- Use poucas palavras, seja direto\n- Não seja formal demais\n\nCOLETA DE DADOS:\n- Só peça CPF e data se o cliente quiser consultar algo\n- NUNCA invente dados\n\nAPÓS CONSULTAR:\n- Confirme que encontrou: \"Oi [Nome], encontrei seu cadastro. O que precisa?\"\n- NÃO liste tudo (cpf, carteira, pagador, plano, etc)\n- Só responda o que for perguntado\n\nSE NÃO SOUBER:\n- Seja direto: \"Não tenho essa info aqui.\"\n- Ofereça ajuda: \"Quer que transfira pro setor certo?\"\n\nEXEMPLOS:\nUser: bom dia\nBot: Oi! Em que posso ajudar?\n\nUser: meu cpf é 123 e nasci 01/01/1990\nBot: Achei seu cadastro, Maria. O que precisa saber?\n\nUser: qual o vencimento?\nBot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?\n\nUser: quero fazer empréstimo\nBot: Empréstimo não é aqui. Quer que transfira pro financeiro?"
    },
    {
      "role": "user",
      "content": "bom dia"
    },
    {
      "role": "assistant",
      "content": "$RESP1_CONTENT"
    },
    {
      "role": "user",
      "content": "Meu cpf é 00835690490 e nascimento 28031979"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "unimed_consult",
        "description": "Consulta dados do beneficiário.",
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
    }
  ],
  "tool_choice": "auto"
}
EOF

echo "USER: Meu cpf é 00835690490 e nascimento 28031979"
echo ""
echo "Chamando API com tools..."
RESPONSE2=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -H "Authorization: Bearer token_abc123" \
  -d @/tmp/payload2.json)

echo "$RESPONSE2" | jq '.' > /tmp/resp2_full.json
RESP2_CONTENT=$(echo "$RESPONSE2" | jq -r '.choices[0].message.content // empty')

if [ -z "$RESP2_CONTENT" ]; then
  echo "⚙️  Tool foi executada, aguardando resultado..."
  # Verificar se há tool_calls
  TOOL_CALLS=$(echo "$RESPONSE2" | jq '.choices[0].message.tool_calls // []')
  echo "Tool calls: $TOOL_CALLS"
  RESP2_CONTENT="[consulta realizada]"
else
  echo "BOT: $RESP2_CONTENT"
fi

echo ""
echo "======================================"
echo "TURNO 3: Pergunta específica"
echo "======================================"
# Simular que tool retornou dados
cat > /tmp/payload3.json << EOF
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Você é atendente da Central Unimed Natal.\n\nCOMO FALAR:\n- Seja breve e natural como um atendente real\n- Use poucas palavras, seja direto\n- Não seja formal demais\n\nCOLETA DE DADOS:\n- Só peça CPF e data se o cliente quiser consultar algo\n- NUNCA invente dados\n\nAPÓS CONSULTAR:\n- Confirme que encontrou: \"Oi [Nome], encontrei seu cadastro. O que precisa?\"\n- NÃO liste tudo (cpf, carteira, pagador, plano, etc)\n- Só responda o que for perguntado\n\nSE NÃO SOUBER:\n- Seja direto: \"Não tenho essa info aqui.\"\n- Ofereça ajuda: \"Quer que transfira pro setor certo?\"\n\nEXEMPLOS:\nUser: bom dia\nBot: Oi! Em que posso ajudar?\n\nUser: meu cpf é 123 e nasci 01/01/1990\nBot: Achei seu cadastro, Maria. O que precisa saber?\n\nUser: qual o vencimento?\nBot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?\n\nUser: quero fazer empréstimo\nBot: Empréstimo não é aqui. Quer que transfira pro financeiro?"
    },
    {
      "role": "user",
      "content": "bom dia"
    },
    {
      "role": "assistant",
      "content": "$RESP1_CONTENT"
    },
    {
      "role": "user",
      "content": "Meu cpf é 00835690490 e nascimento 28031979"
    },
    {
      "role": "assistant",
      "content": "Oi Kelly, achei seu cadastro. O que precisa?"
    },
    {
      "role": "user",
      "content": "Poderia me informar a data de vencimento do meu contrato?"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
EOF

echo "USER: Poderia me informar a data de vencimento do meu contrato?"
echo ""
echo "Chamando API..."
RESPONSE3=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -d @/tmp/payload3.json)

echo "$RESPONSE3" | jq -r '.choices[0].message.content' > /tmp/resp3.txt
echo "BOT: $(cat /tmp/resp3.txt)"
RESP3_CONTENT=$(cat /tmp/resp3.txt)

echo ""
echo "======================================"
echo "TURNO 4: Pergunta fora do escopo"
echo "======================================"
cat > /tmp/payload4.json << EOF
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Você é atendente da Central Unimed Natal.\n\nCOMO FALAR:\n- Seja breve e natural como um atendente real\n- Use poucas palavras, seja direto\n- Não seja formal demais\n\nCOLETA DE DADOS:\n- Só peça CPF e data se o cliente quiser consultar algo\n- NUNCA invente dados\n\nAPÓS CONSULTAR:\n- Confirme que encontrou: \"Oi [Nome], encontrei seu cadastro. O que precisa?\"\n- NÃO liste tudo (cpf, carteira, pagador, plano, etc)\n- Só responda o que for perguntado\n\nSE NÃO SOUBER:\n- Seja direto: \"Não tenho essa info aqui.\"\n- Ofereça ajuda: \"Quer que transfira pro setor certo?\"\n\nEXEMPLOS:\nUser: bom dia\nBot: Oi! Em que posso ajudar?\n\nUser: meu cpf é 123 e nasci 01/01/1990\nBot: Achei seu cadastro, Maria. O que precisa saber?\n\nUser: qual o vencimento?\nBot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?\n\nUser: quero fazer empréstimo\nBot: Empréstimo não é aqui. Quer que transfira pro financeiro?"
    },
    {
      "role": "user",
      "content": "bom dia"
    },
    {
      "role": "assistant",
      "content": "$RESP1_CONTENT"
    },
    {
      "role": "user",
      "content": "Meu cpf é 00835690490 e nascimento 28031979"
    },
    {
      "role": "assistant",
      "content": "Oi Kelly, achei seu cadastro. O que precisa?"
    },
    {
      "role": "user",
      "content": "Poderia me informar a data de vencimento do meu contrato?"
    },
    {
      "role": "assistant",
      "content": "$RESP3_CONTENT"
    },
    {
      "role": "user",
      "content": "Quero saber sobre empréstimos consignados"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
EOF

echo "USER: Quero saber sobre empréstimos consignados"
echo ""
echo "Chamando API..."
RESPONSE4=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -d @/tmp/payload4.json)

echo "$RESPONSE4" | jq -r '.choices[0].message.content' > /tmp/resp4.txt
echo "BOT: $(cat /tmp/resp4.txt)"
RESP4_CONTENT=$(cat /tmp/resp4.txt)

echo ""
echo "======================================"
echo "TURNO 5: Segunda via"
echo "======================================"
cat > /tmp/payload5.json << EOF
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Você é atendente da Central Unimed Natal.\n\nCOMO FALAR:\n- Seja breve e natural como um atendente real\n- Use poucas palavras, seja direto\n- Não seja formal demais\n\nCOLETA DE DADOS:\n- Só peça CPF e data se o cliente quiser consultar algo\n- NUNCA invente dados\n\nAPÓS CONSULTAR:\n- Confirme que encontrou: \"Oi [Nome], encontrei seu cadastro. O que precisa?\"\n- NÃO liste tudo (cpf, carteira, pagador, plano, etc)\n- Só responda o que for perguntado\n\nSE NÃO SOUBER:\n- Seja direto: \"Não tenho essa info aqui.\"\n- Ofereça ajuda: \"Quer que transfira pro setor certo?\"\n\nEXEMPLOS:\nUser: bom dia\nBot: Oi! Em que posso ajudar?\n\nUser: meu cpf é 123 e nasci 01/01/1990\nBot: Achei seu cadastro, Maria. O que precisa saber?\n\nUser: qual o vencimento?\nBot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?\n\nUser: quero fazer empréstimo\nBot: Empréstimo não é aqui. Quer que transfira pro financeiro?"
    },
    {
      "role": "user",
      "content": "bom dia"
    },
    {
      "role": "assistant",
      "content": "$RESP1_CONTENT"
    },
    {
      "role": "user",
      "content": "Meu cpf é 00835690490 e nascimento 28031979"
    },
    {
      "role": "assistant",
      "content": "Oi Kelly, achei seu cadastro. O que precisa?"
    },
    {
      "role": "user",
      "content": "Poderia me informar a data de vencimento do meu contrato?"
    },
    {
      "role": "assistant",
      "content": "$RESP3_CONTENT"
    },
    {
      "role": "user",
      "content": "Quero saber sobre empréstimos consignados"
    },
    {
      "role": "assistant",
      "content": "$RESP4_CONTENT"
    },
    {
      "role": "user",
      "content": "Como posso emitir a segunda via da carteirinha?"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
EOF

echo "USER: Como posso emitir a segunda via da carteirinha?"
echo ""
echo "Chamando API..."
RESPONSE5=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -d @/tmp/payload5.json)

echo "$RESPONSE5" | jq -r '.choices[0].message.content' > /tmp/resp5.txt
echo "BOT: $(cat /tmp/resp5.txt)"
RESP5_CONTENT=$(cat /tmp/resp5.txt)

echo ""
echo "======================================"
echo "TURNO 6: Incluir dependente"
echo "======================================"
cat > /tmp/payload6.json << EOF
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Você é atendente da Central Unimed Natal.\n\nCOMO FALAR:\n- Seja breve e natural como um atendente real\n- Use poucas palavras, seja direto\n- Não seja formal demais\n\nCOLETA DE DADOS:\n- Só peça CPF e data se o cliente quiser consultar algo\n- NUNCA invente dados\n\nAPÓS CONSULTAR:\n- Confirme que encontrou: \"Oi [Nome], encontrei seu cadastro. O que precisa?\"\n- NÃO liste tudo (cpf, carteira, pagador, plano, etc)\n- Só responda o que for perguntado\n\nSE NÃO SOUBER:\n- Seja direto: \"Não tenho essa info aqui.\"\n- Ofereça ajuda: \"Quer que transfira pro setor certo?\"\n\nEXEMPLOS:\nUser: bom dia\nBot: Oi! Em que posso ajudar?\n\nUser: meu cpf é 123 e nasci 01/01/1990\nBot: Achei seu cadastro, Maria. O que precisa saber?\n\nUser: qual o vencimento?\nBot: Seu plano é boleto mensal, a data vem no boleto mesmo. Mais alguma coisa?\n\nUser: quero fazer empréstimo\nBot: Empréstimo não é aqui. Quer que transfira pro financeiro?"
    },
    {
      "role": "user",
      "content": "bom dia"
    },
    {
      "role": "assistant",
      "content": "$RESP1_CONTENT"
    },
    {
      "role": "user",
      "content": "Meu cpf é 00835690490 e nascimento 28031979"
    },
    {
      "role": "assistant",
      "content": "Oi Kelly, achei seu cadastro. O que precisa?"
    },
    {
      "role": "user",
      "content": "Poderia me informar a data de vencimento do meu contrato?"
    },
    {
      "role": "assistant",
      "content": "$RESP3_CONTENT"
    },
    {
      "role": "user",
      "content": "Quero saber sobre empréstimos consignados"
    },
    {
      "role": "assistant",
      "content": "$RESP4_CONTENT"
    },
    {
      "role": "user",
      "content": "Como posso emitir a segunda via da carteirinha?"
    },
    {
      "role": "assistant",
      "content": "$RESP5_CONTENT"
    },
    {
      "role": "user",
      "content": "Como faço para incluir um dependente?"
    }
  ],
  "max_tokens": 100,
  "temperature": 0.7
}
EOF

echo "USER: Como faço para incluir um dependente?"
echo ""
echo "Chamando API..."
RESPONSE6=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
  -d @/tmp/payload6.json)

echo "$RESPONSE6" | jq -r '.choices[0].message.content' > /tmp/resp6.txt
echo "BOT: $(cat /tmp/resp6.txt)"

echo ""
echo "======================================"
echo "ANÁLISE FINAL"
echo "======================================"
echo ""
echo "✅ ESPERADO (respostas curtas e naturais):"
echo "1. Oi! Em que posso ajudar?"
echo "2. Oi Kelly, achei seu cadastro. O que precisa?"
echo "3. Seu plano é boleto mensal, a data vem no boleto. Mais alguma coisa?"
echo "4. Empréstimo não é aqui. Quer que transfira pro financeiro?"
echo "5. Você tira pelo app ou site na área do cliente. Precisa de ajuda?"
echo "6. Seu plano é empresarial, tem que pedir pro RH da empresa. Mais algo?"
echo ""
echo "Compare com as respostas reais acima ☝️"
