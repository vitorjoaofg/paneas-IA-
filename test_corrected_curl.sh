#!/bin/bash

# Script para testar o CURL corrigido com system prompt e tools organizados

API_URL="https://jota.ngrok.app/api/v1/chat/completions"
AUTH="Bearer token_abc123"

echo "=========================================="
echo "🔧 TESTE: CURL CORRIGIDO - SAUDAÇÃO"
echo "=========================================="
echo ""
echo "Enviando: 'bom dia'"
echo "Expectativa: Resposta de saudação profissional SEM chamar tool"
echo ""
echo "Payload sendo enviado:"
echo "------------------------------------------"

# Criar o JSON payload em um arquivo temporário para melhor formatação
cat > /tmp/test_payload.json << 'EOF'
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Assistente especializado em consultas de beneficiários e contratos Unimed Natal.\n\n## ESCOPO DE ATUAÇÃO\n- APENAS consultas sobre beneficiários Unimed Natal\n- Informações de contratos e planos de saúde\n- Dados de carteirinha e dependentes\n- Status de benefício e vigência\n- Orientações sobre cobertura e procedimentos\n- Dúvidas sobre rede credenciada\n\n## COMPORTAMENTO OBRIGATÓRIO\n1. SEMPRE mantenha o foco em planos de saúde Unimed Natal\n2. Se perguntarem sobre outras operadoras, redirecione educadamente\n3. Use linguagem elegante, profissional e empática\n4. Seja objetivo e direto nas respostas\n5. Sempre ofereça próximos passos concretos\n\n## ESTRATÉGIA DE RESPOSTA\n- CPF e data de nascimento fornecidos: consulte dados completos\n- Informações de contrato: apresente de forma clara e organizada\n- Dúvidas gerais: use base de conhecimento sobre planos Unimed\n- Sempre cite fontes: \"Conforme sistema Unimed Natal\"\n- Mantenha contexto da conversa\n\n## FORMATAÇÃO ELEGANTE\n- Respostas estruturadas e organizadas\n- Destaque informações importantes com *negrito*\n- Use listas numeradas para próximas ações\n- Seja específico sobre prazos e vigências\n- Inclua seção \"Próximas ações\" quando relevante\n\n## REDIRECIONAMENTO\n- Se perguntarem sobre outras operadoras: \"Sou especialista apenas em planos Unimed Natal\"\n- Se perguntarem sobre outros produtos: \"Foco exclusivamente em planos de saúde Unimed\"\n- Se perguntarem sobre outros assuntos: \"Posso ajudá-lo apenas com questões de planos de saúde Unimed Natal\"\n\n## PRIVACIDADE\n- Nunca exponha CPF completo, use mascaramento (ex: 123.***.***-90)\n- Nunca exponha dados completos de cartão ou bancários\n- Respeite LGPD rigorosamente\n- Proteja informações sensíveis dos beneficiários"
    },
    {
      "role": "user",
      "content": "bom dia"
    }
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
          "required": ["cpf", "data_nascimento"]
        }
      }
    }
  ],
  "tool_choice": "auto"
}
EOF

# Mostrar resumo do payload
echo "✅ System prompt: Instruções completas da Unimed Natal"
echo "✅ User message: 'bom dia'"
echo "✅ Tools: unimed_consult (com CPF e data_nascimento como required)"
echo "✅ tool_choice: auto (deixa o modelo decidir)"
echo ""
echo "------------------------------------------"
echo "📤 Enviando requisição..."
echo "------------------------------------------"
echo ""

# Fazer a requisição
response=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: $AUTH" \
  -d @/tmp/test_payload.json)

# Analisar resposta
echo "📥 RESPOSTA DO MODELO:"
echo "------------------------------------------"

# Verificar se há tool_calls
if echo "$response" | grep -q '"tool_calls":\['; then
    echo "❌ ERRO: Modelo chamou tool desnecessariamente!"
    echo ""
    func_name=$(echo "$response" | grep -oP '"name":"\K[^"]+' | head -1)
    echo "Função chamada: $func_name"
    echo ""
    echo "🔴 PROBLEMA: O modelo está tentando usar ferramenta para uma saudação simples"
elif echo "$response" | grep -q '"tool_calls":null'; then
    echo "✅ SUCESSO: Modelo NÃO chamou ferramentas!"
    echo ""
    # Extrair e formatar o conteúdo
    content=$(echo "$response" | python3 -c "
import json
import sys
data = json.load(sys.stdin)
if 'choices' in data and len(data['choices']) > 0:
    content = data['choices'][0]['message'].get('content', '')
    print(content)
" 2>/dev/null)

    echo "Resposta do assistente:"
    echo ""
    echo "$content"
    echo ""
    echo "✅ COMPORTAMENTO CORRETO: Respondeu à saudação sem forçar uso de ferramentas"
else
    echo "⚠️  Formato de resposta inesperado"
    echo "$response" | python3 -m json.tool 2>/dev/null | head -20
fi

echo ""
echo "=========================================="
echo "🔍 ANÁLISE DO RESULTADO"
echo "=========================================="
echo ""
echo "Comportamento esperado:"
echo "✓ Responder com saudação profissional"
echo "✓ Mencionar ser assistente Unimed Natal"
echo "✓ Oferecer ajuda com serviços disponíveis"
echo "✓ NÃO tentar chamar a ferramenta unimed_consult"
echo ""

# Limpar arquivo temporário
rm -f /tmp/test_payload.json

echo "=========================================="
echo "FIM DO TESTE"
echo "=========================================="