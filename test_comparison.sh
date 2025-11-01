#!/bin/bash
# Comparação: Comportamento Atual vs Esperado

API_URL="http://localhost:8000/api/v1/chat/completions"
TOKEN="token_abc123"

PROMPT_MELHORADO='Você é atendente da Central Unimed Natal.

RESPOSTAS CURTAS (máximo 2-3 frases):
- Seja direto
- Use linguagem natural
- NÃO repita dados já ditos

COLETA DE DADOS:
- Só peça se o cliente quiser consultar
- NUNCA invente

APÓS CONSULTA:
- Confirme: "Oi [Nome], achei. O que precisa?"
- NÃO liste tudo
- Responda só o que foi perguntado

FORA DO ESCOPO:
- "Não tenho isso aqui."
- "Quer que transfira?"

EXEMPLOS:
User: bom dia
Bot: Oi! Como posso ajudar?

User: qual vencimento?
Bot: É boleto mensal, vem no boleto. Mais algo?

User: quero empréstimo
Bot: Empréstimo não é aqui. Quer que transfira?'

echo "=========================================="
echo "TESTE COMPARATIVO"
echo "=========================================="
echo ""

# Função para fazer chamada
call_api() {
  local user_msg="$1"
  local history="$2"

  local messages="[{\"role\":\"system\",\"content\":$(echo "$PROMPT_MELHORADO" | jq -Rs '.')}"

  if [ -n "$history" ]; then
    messages="$messages,$history"
  fi

  messages="$messages,{\"role\":\"user\",\"content\":\"$user_msg\"}]"

  local payload="{\"model\":\"paneas-q32b\",\"messages\":$messages,\"max_tokens\":80,\"temperature\":0.7}"

  curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$payload" | jq -r '.choices[0].message.content'
}

echo "TURNO 1: Saudação"
echo "=================="
echo "👤 USER: bom dia"
echo ""
RESP1=$(call_api "bom dia" "")
echo "🤖 BOT ATUAL: $RESP1"
echo "✅ ESPERADO: Oi! Como posso ajudar?"
echo ""
if echo "$RESP1" | grep -qi "cpf\|data\|nascimento"; then
  echo "❌ PROBLEMA: Pede dados logo de cara"
else
  echo "✅ OK: Não pede dados desnecessariamente"
fi
echo ""

# Contar palavras
WORD_COUNT=$(echo "$RESP1" | wc -w)
echo "📏 Tamanho: $WORD_COUNT palavras"
if [ $WORD_COUNT -le 10 ]; then
  echo "✅ OK: Resposta curta"
else
  echo "⚠️  Poderia ser mais curto (ideal: 5-10 palavras)"
fi

echo ""
echo "=========================================="
echo "TURNO 2: Fornece dados (SEM TOOL - SIMULA)"
echo "=========================================="
echo "👤 USER: Meu cpf é 00835690490 nascimento 28031979"
echo ""

# Simular que tool retornou dados
HISTORY="{\"role\":\"assistant\",\"content\":\"$RESP1\"}"
RESP2="Oi Kelly, achei seu cadastro. O que precisa?"
echo "🤖 BOT IDEAL: $RESP2"
echo "✅ ESPERADO: Confirma brevemente, NÃO lista todos os dados"
echo ""

echo "=========================================="
echo "TURNO 3: Pergunta específica"
echo "=========================================="
echo "👤 USER: Qual a data de vencimento?"
echo ""

HISTORY="$HISTORY,{\"role\":\"user\",\"content\":\"Meu cpf é 00835690490 nascimento 28031979\"},{\"role\":\"assistant\",\"content\":\"$RESP2\"}"
RESP3=$(call_api "Qual a data de vencimento?" "$HISTORY")
echo "🤖 BOT ATUAL: $RESP3"
echo "✅ ESPERADO: É boleto mensal, vem no boleto. Mais algo?"
echo ""

if echo "$RESP3" | grep -qi "cpf\|carteira\|pagador\|plano"; then
  echo "❌ PROBLEMA: Repete dados do contrato"
else
  echo "✅ OK: Não repete dados"
fi

WORD_COUNT=$(echo "$RESP3" | wc -w)
echo "📏 Tamanho: $WORD_COUNT palavras"
if [ $WORD_COUNT -le 20 ]; then
  echo "✅ OK: Resposta curta"
else
  echo "⚠️  Muito longo (ideal: 10-20 palavras)"
fi

echo ""
echo "=========================================="
echo "TURNO 4: Pergunta fora do escopo"
echo "=========================================="
echo "👤 USER: Quero saber sobre empréstimos consignados"
echo ""

HISTORY="$HISTORY,{\"role\":\"user\",\"content\":\"Qual a data de vencimento?\"},{\"role\":\"assistant\",\"content\":\"$RESP3\"}"
RESP4=$(call_api "Quero saber sobre empréstimos consignados" "$HISTORY")
echo "🤖 BOT ATUAL: $RESP4"
echo "✅ ESPERADO: Empréstimo não é aqui. Quer que transfira pro financeiro?"
echo ""

if echo "$RESP4" | grep -qi "cpf\|carteira\|kelly\|pagador"; then
  echo "❌ PROBLEMA: Repete dados do contrato novamente"
else
  echo "✅ OK: Não repete dados"
fi

if echo "$RESP4" | grep -qi "não tenho\|não é aqui\|transfir"; then
  echo "✅ OK: Responde que está fora do escopo"
else
  echo "⚠️  Poderia ser mais direto sobre não ter a info"
fi

WORD_COUNT=$(echo "$RESP4" | wc -w)
echo "📏 Tamanho: $WORD_COUNT palavras"
if [ $WORD_COUNT -le 20 ]; then
  echo "✅ OK: Resposta curta"
else
  echo "⚠️  Muito longo"
fi

echo ""
echo "=========================================="
echo "RESUMO FINAL"
echo "=========================================="
echo ""
echo "✅ MELHORIAS IMPLEMENTADAS:"
echo "   - Prompt otimizado para respostas curtas"
echo "   - Instruções claras sobre não repetir dados"
echo "   - Tom natural e conversacional"
echo "   - Limitar max_tokens para forçar concisão"
echo ""
echo "⚠️  PONTOS DE ATENÇÃO:"
echo "   - Tool calling pode não funcionar sempre (limitação do modelo)"
echo "   - Considere ajustar temperature se muito variável"
echo "   - Monitore comprimento das respostas"
echo ""
echo "📖 Ver documentação completa em: PROMPT_FINAL_ATENDENTE.md"
