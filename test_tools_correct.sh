#!/bin/bash

# Script de teste para uso CORRETO de tools em LLM
# Demonstra a diferença entre forçar tool_choice vs deixar o modelo decidir

API_URL="https://jota.ngrok.app/api/v1/chat/completions"
AUTH_TOKEN="token_abc123"

echo "=========================================="
echo "TESTES DE USO CORRETO DE TOOLS"
echo "=========================================="

echo -e "\n📝 TESTE 1: Saudação simples (NÃO deve chamar tool)"
echo "Enviando: 'oi'"
echo -e "\n✅ FORMA CORRETA (sem forçar tool_choice):"

curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "model": "paneas-q32b",
    "messages": [
      {
        "role": "user",
        "content": "oi"
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
  }'

echo -e "\n\nRESPOSTA ESPERADA: Mensagem de saudação normal, SEM tool_calls"

echo -e "\n\n=========================================="
echo -e "\n📝 TESTE 2: Consulta que PRECISA de tool"
echo "Enviando: 'Preciso consultar o contrato do CPF 00835690490, nascido em 28/03/1979 em Natal'"

curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "model": "paneas-q32b",
    "messages": [
      {
        "role": "user",
        "content": "Preciso consultar o contrato do CPF 00835690490, nascido em 28/03/1979 em Natal"
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
  }'

echo -e "\n\nRESPOSTA ESPERADA: tool_calls com argumentos extraídos do contexto"

echo -e "\n\n=========================================="
echo -e "\n📝 TESTE 3: Pergunta genérica (NÃO deve chamar tool)"
echo "Enviando: 'Qual a capital do Brasil?'"

curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "model": "paneas-q32b",
    "messages": [
      {
        "role": "user",
        "content": "Qual a capital do Brasil?"
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
  }'

echo -e "\n\nRESPOSTA ESPERADA: Resposta direta sobre Brasília, SEM tool_calls"

echo -e "\n\n=========================================="
echo "ANÁLISE DO PROBLEMA ORIGINAL:"
echo "=========================================="
echo "❌ ERRO: Usar tool_choice com arguments pré-definidos"
echo "   Isso força o modelo a sempre usar a tool com aqueles argumentos"
echo ""
echo "✅ CORRETO: Omitir tool_choice ou usar \"auto\""
echo "   Deixa o modelo decidir QUANDO e COMO usar as ferramentas"
echo ""
echo "FLUXO CORRETO:"
echo "1. Usuário envia pergunta"
echo "2. Modelo analisa semanticamente se precisa de tools"
echo "3. Se sim: gera tool_call com argumentos do contexto"
echo "4. Se não: responde diretamente"
echo "=========================================="