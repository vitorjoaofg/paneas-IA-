#!/usr/bin/env python3
"""
Mock da API Unimed para testes de function calling
"""

import json
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Mock Unimed API")

# Base de dados simulada
MOCK_DATABASE = {
    "12345678900": {
        "cpf": "123.456.789-00",
        "nome": "João da Silva Santos",
        "data_nascimento": "1990-01-01",
        "status": "ativo",
        "plano": "Unimed Premium",
        "numero_carteirinha": "1234567890123456",
        "validade": "2025-12-31",
        "dependentes": 2,
        "carencias": {
            "consultas": "cumprido",
            "exames": "cumprido",
            "internacao": "30 dias restantes"
        },
        "historico": [
            {"data": "2024-10-15", "tipo": "consulta", "especialidade": "Cardiologia"},
            {"data": "2024-09-20", "tipo": "exame", "descricao": "Hemograma completo"}
        ]
    },
    "98765432100": {
        "cpf": "987.654.321-00",
        "nome": "Maria Oliveira Costa",
        "data_nascimento": "1985-05-15",
        "status": "ativo",
        "plano": "Unimed Básico",
        "numero_carteirinha": "9876543210987654",
        "validade": "2026-06-30",
        "dependentes": 0,
        "carencias": {
            "consultas": "cumprido",
            "exames": "cumprido",
            "internacao": "cumprido"
        },
        "historico": [
            {"data": "2024-11-01", "tipo": "consulta", "especialidade": "Clínico Geral"}
        ]
    },
    "11122233344": {
        "cpf": "111.222.333-44",
        "nome": "Carlos Alberto Souza",
        "data_nascimento": "1978-12-25",
        "status": "suspenso",
        "plano": "Unimed Premium",
        "numero_carteirinha": "1112223334445556",
        "validade": "2024-12-31",
        "motivo_suspensao": "Inadimplência",
        "dependentes": 3,
        "carencias": {},
        "historico": []
    }
}


@app.get("/")
def root():
    return {
        "service": "Mock Unimed API",
        "version": "1.0.0",
        "endpoints": [
            "GET /{cidade}/{tipo}",
            "GET /health"
        ]
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/{cidade}/{tipo}")
def consultar_beneficiario(
    cidade: str,
    tipo: str,
    cpf: str = Query(..., description="CPF do beneficiário"),
    data_nascimento: str = Query(..., description="Data de nascimento"),
    protocolo: Optional[str] = Query(None, description="Número do protocolo")
):
    """
    Simula consulta de beneficiário na API Unimed

    Exemplos:
    - /Natal_Tasy/Contratos?cpf=12345678900&data_nascimento=19900101
    - /Fortaleza/Beneficiarios?cpf=98765432100&data_nascimento=19850515&protocolo=123456
    """

    # Normalizar CPF
    cpf_limpo = cpf.replace(".", "").replace("-", "")

    # Normalizar data de nascimento
    data_limpa = data_nascimento.replace("-", "")

    # Log da requisição
    print(f"[MOCK API] Request: cidade={cidade}, tipo={tipo}, cpf={cpf_limpo[:3]}***, data={data_limpa}")

    # Verificar se CPF existe no banco
    if cpf_limpo not in MOCK_DATABASE:
        return JSONResponse(
            status_code=404,
            content={
                "error": "Beneficiário não encontrado",
                "code": "NOT_FOUND",
                "details": f"Não foram encontrados registros para o CPF informado"
            }
        )

    beneficiario = MOCK_DATABASE[cpf_limpo]

    # Validar data de nascimento
    data_beneficiario = beneficiario["data_nascimento"].replace("-", "")
    if data_limpa != data_beneficiario:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Data de nascimento não confere",
                "code": "INVALID_BIRTHDATE",
                "details": "A data de nascimento informada não corresponde aos registros"
            }
        )

    # Montar resposta
    response_data = {
        "protocolo": protocolo or f"AUTO-{cpf_limpo[:6]}",
        "cidade": cidade,
        "tipo_consulta": tipo,
        "data_consulta": "2024-11-29T10:30:00Z",
        "beneficiario": beneficiario,
        "observacoes": f"Consulta realizada com sucesso para {cidade}/{tipo}"
    }

    print(f"[MOCK API] Success: Retornando dados do beneficiário {beneficiario['nome']}")

    return response_data


if __name__ == "__main__":
    print("=" * 60)
    print("Mock Unimed API Server")
    print("=" * 60)
    print("Starting server on http://localhost:9999")
    print("\nAvailable test CPFs:")
    print("  - 12345678900 (João da Silva Santos) - Ativo")
    print("  - 98765432100 (Maria Oliveira Costa) - Ativo")
    print("  - 11122233344 (Carlos Alberto Souza) - Suspenso")
    print("\nExample request:")
    print("  curl 'http://localhost:9999/Natal_Tasy/Contratos?cpf=12345678900&data_nascimento=19900101'")
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=9999, log_level="info")
