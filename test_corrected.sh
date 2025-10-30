#!/bin/bash

echo "=========================================="
echo "TESTE 1: Saudação simples - NÃO deve chamar tool"
echo "=========================================="
echo "Enviando: 'oi'"
echo ""

# CURL CORRIGIDO - SEM tool_choice com arguments forçados
curl -X POST https://jota.ngrok.app/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
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

echo ""
echo ""
echo "=========================================="
echo "TESTE 2: Consulta que DEVE chamar a tool"
echo "=========================================="
echo "Enviando: 'Preciso consultar o contrato do CPF 00835690490, nascido em 28/03/1979 em Natal'"
echo ""

curl -X POST https://jota.ngrok.app/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token_abc123" \
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

echo ""