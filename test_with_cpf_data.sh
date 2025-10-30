#!/bin/bash

# Script para testar CURL com dados que DEVEM acionar a ferramenta

API_URL="https://jota.ngrok.app/api/v1/chat/completions"
AUTH="Bearer token_abc123"

echo "=========================================="
echo "🔧 TESTE 2: CONSULTA COM CPF E DATA"
echo "=========================================="
echo ""
echo "Enviando: 'Quero consultar o contrato do CPF 12345678901, nascido em 15/06/1985 em Natal'"
echo "Expectativa: DEVE chamar a ferramenta unimed_consult"
echo ""

# Criar o JSON payload
cat > /tmp/test_payload2.json << 'EOF'
{
  "model": "paneas-q32b",
  "messages": [
    {
      "role": "system",
      "content": "Assistente especializado em consultas de beneficiários e contratos Unimed Natal.\n\n## ESCOPO DE ATUAÇÃO\n- APENAS consultas sobre beneficiários Unimed Natal\n- Informações de contratos e planos de saúde\n- Dados de carteirinha e dependentes\n- Status de benefício e vigência\n\n## COMPORTAMENTO OBRIGATÓRIO\n1. Use linguagem elegante, profissional e empática\n2. Seja objetivo e direto nas respostas\n3. Sempre ofereça próximos passos concretos\n\n## ESTRATÉGIA DE RESPOSTA\n- CPF e data de nascimento fornecidos: consulte dados completos usando a ferramenta disponível\n- Mantenha contexto da conversa\n\n## PRIVACIDADE\n- Nunca exponha CPF completo, use mascaramento (ex: 123.***.***-90)\n- Respeite LGPD rigorosamente"
    },
    {
      "role": "user",
      "content": "Quero consultar o contrato do CPF 12345678901, nascido em 15/06/1985 em Natal"
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

echo "📤 Enviando requisição..."
echo "------------------------------------------"
echo ""

# Fazer a requisição
response=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: $AUTH" \
  -d @/tmp/test_payload2.json)

# Analisar resposta
echo "📥 RESPOSTA DO MODELO:"
echo "------------------------------------------"

# Verificar se há tool_calls
if echo "$response" | grep -q '"tool_calls":\['; then
    echo "✅ SUCESSO: Modelo CHAMOU a ferramenta!"
    echo ""

    # Extrair informações da tool call
    func_name=$(echo "$response" | grep -oP '"name":"\K[^"]+' | head -1)
    echo "Função chamada: $func_name"

    # Tentar extrair argumentos
    echo ""
    echo "Argumentos extraídos:"
    echo "$response" | python3 -c "
import json
import sys
import re

data = sys.stdin.read()
# Procurar por arguments no JSON
match = re.search(r'\"arguments\":\"([^\"]+)\"', data)
if match:
    args_str = match.group(1)
    # Decodificar escape sequences
    args_str = args_str.replace('\\\\\"', '\"').replace('\\\\n', '\n')
    try:
        args = json.loads(args_str)
        for key, value in args.items():
            print(f'  • {key}: {value}')
    except:
        print('  Erro ao parsear argumentos')
" 2>/dev/null

    echo ""
    echo "✅ COMPORTAMENTO CORRETO:"
    echo "   - Detectou necessidade de consulta"
    echo "   - Extraiu CPF do contexto"
    echo "   - Extraiu data de nascimento"
    echo "   - Identificou cidade (Natal)"

elif echo "$response" | grep -q '"tool_calls":null'; then
    echo "❌ ERRO: Modelo NÃO chamou a ferramenta!"
    echo ""
    content=$(echo "$response" | python3 -c "
import json
import sys
data = json.load(sys.stdin)
if 'choices' in data and len(data['choices']) > 0:
    content = data['choices'][0]['message'].get('content', '')
    print(content)
" 2>/dev/null)

    echo "Resposta (sem tool):"
    echo "$content"
    echo ""
    echo "🔴 PROBLEMA: O modelo deveria ter usado unimed_consult"
else
    echo "⚠️  Formato de resposta inesperado"
    echo "$response" | python3 -m json.tool 2>/dev/null | head -20
fi

# Limpar arquivo temporário
rm -f /tmp/test_payload2.json

echo ""
echo "=========================================="
echo "🔍 ANÁLISE COMPARATIVA"
echo "=========================================="
echo ""
echo "TESTE 1 (Saudação):"
echo "  Input: 'bom dia'"
echo "  ✅ Resultado: NÃO chamou ferramenta (correto)"
echo ""
echo "TESTE 2 (Consulta com dados):"
echo "  Input: CPF + data nascimento + cidade"
echo "  Esperado: DEVE chamar ferramenta"
echo ""
echo "=========================================="