#!/bin/bash

# Script para executar 10 testes variados de decisão de tools

API_URL="https://jota.ngrok.app/api/v1/chat/completions"
AUTH="Bearer token_abc123"

# Função para fazer request
make_request() {
    local content="$1"
    local test_num="$2"
    local expected="$3"

    echo "=========================================="
    echo "TESTE $test_num: $expected"
    echo "Input: \"$content\""
    echo "------------------------------------------"

    response=$(curl -s -X POST "$API_URL" \
      -H "Content-Type: application/json" \
      -H "Authorization: $AUTH" \
      -d '{
        "model": "paneas-q32b",
        "messages": [
          {
            "role": "user",
            "content": "'"$content"'"
          }
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
                  "base_url": {
                    "type": "string",
                    "description": "URL base da API Unimed",
                    "default": "https://unimed-central-cobranca.paneas.net/api/v1"
                  },
                  "cidade": {
                    "type": "string",
                    "description": "Cidade do protocolo (ex: Natal_Tasy)"
                  },
                  "tipo": {
                    "type": "string",
                    "description": "Tipo de consulta (ex: Contratos)",
                    "default": "Contratos"
                  },
                  "protocolo": {
                    "type": "string",
                    "description": "Número do protocolo (opcional, use 0 ou null para ignorar)"
                  },
                  "cpf": {
                    "type": "string",
                    "description": "CPF do beneficiário"
                  },
                  "data_nascimento": {
                    "type": "string",
                    "description": "Data de nascimento (formato: AAAA-MM-DD ou AAAAMMDD)"
                  }
                },
                "required": ["cidade", "cpf", "data_nascimento"]
              }
            }
          }
        ]
      }')

    # Verificar se há tool_calls na resposta
    if echo "$response" | grep -q '"tool_calls":\['; then
        echo "✅ CHAMOU TOOL"
        # Extrair nome da função
        func_name=$(echo "$response" | grep -oP '"name":"\K[^"]+' | head -1)
        echo "   Função: $func_name"
        # Tentar extrair alguns argumentos
        echo "$response" | grep -oP '"arguments":"\K[^"]+' | head -1 | sed 's/\\"/"/g' | python3 -m json.tool 2>/dev/null | head -5
    elif echo "$response" | grep -q '"tool_calls":null'; then
        echo "❌ NÃO CHAMOU TOOL"
        # Extrair conteúdo da resposta
        content=$(echo "$response" | grep -oP '"content":"\K[^"]*' | head -1)
        echo "   Resposta: $content"
    else
        echo "⚠️  ERRO OU FORMATO INESPERADO"
        echo "$response" | head -2
    fi

    echo ""
}

# EXECUTAR OS 10 TESTES
echo "================================================"
echo "EXECUTANDO 10 TESTES DE DECISÃO DE TOOLS"
echo "================================================"
echo ""

# TESTE 1: Saudação simples
make_request "Oi, tudo bem?" 1 "NÃO deve chamar tool"

# TESTE 2: Consulta clara com todos os dados
make_request "Quero consultar o contrato do CPF 12345678901, nascido em 15/06/1985 em Fortaleza" 2 "DEVE chamar tool"

# TESTE 3: Pergunta geral
make_request "Quanto é 2 + 2?" 3 "NÃO deve chamar tool"

# TESTE 4: Consulta sem dados completos
make_request "Preciso ver meus contratos da Unimed" 4 "PODE chamar tool (faltam dados)"

# TESTE 5: Despedida
make_request "Tchau, obrigado!" 5 "NÃO deve chamar tool"

# TESTE 6: Consulta com CPF formatado
make_request "Verificar contrato do beneficiário CPF 987.654.321-00, data de nascimento 01/01/1990, cidade Natal" 6 "DEVE chamar tool"

# TESTE 7: Pergunta sobre clima (sem tool de clima disponível)
make_request "Qual a previsão do tempo para hoje?" 7 "NÃO deve chamar tool Unimed"

# TESTE 8: Menção a Unimed sem ser consulta
make_request "A Unimed é uma boa operadora de saúde?" 8 "NÃO deve chamar tool"

# TESTE 9: Consulta com variação de linguagem
make_request "Olha, eu gostaria de checar o status do meu plano, meu CPF é 55566677788 e nasci em 20 de dezembro de 2000, sou de Natal" 9 "DEVE chamar tool"

# TESTE 10: Pergunta complexa mas não relacionada
make_request "Explique como funciona o sistema de saúde no Brasil" 10 "NÃO deve chamar tool"

echo "================================================"
echo "FIM DOS TESTES"
echo "================================================"