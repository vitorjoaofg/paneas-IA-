"""Gera enriquecimentos de conversas usando OpenAI Responses API.

Executa uma chamada para cada transcrição localizada em `engine/` e grava
as saídas em `engine/conversation_enrichment.json` (dicionário com call_id -> dados).

Dependências: `requests`. Configure `OPENAI_API_KEY` no ambiente.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

ROOT = Path(__file__).resolve().parent
TRANSCRIPTS_DIR = ROOT
OUTPUT_PATH = ROOT / "conversation_enrichment.json"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
API_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def load_transcript(call_id: str) -> Dict[str, Any]:
    path = TRANSCRIPTS_DIR / f"{call_id}.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_prompt(transcript: Dict[str, Any]) -> str:
    segments = transcript.get("segments") or []
    turns: List[str] = []
    for segment in segments[:80]:
        speaker = (segment.get("speaker") or segment.get("role") or "speaker").upper()
        text = segment.get("text", "")
        turns.append(f"[{speaker}] {text}")
    conversation = "\n".join(turns)
    return (
        "Analise a conversa a seguir e produza um JSON com os campos:"
        " resumo_curto (5 frases),"
        " pontos_positivos (lista),"
        " pontos_negativos (lista),"
        " eventos_timeline (lista de objetos com minuto, tipo, descricao),"
        " alertas (lista de objetos com severidade e mensagem)."
        " Seja objetivo e mantenha termos em português."\
        "\n\nCONVERSA:\n" + conversation
    )


def openai_response(prompt: str) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    payload = {
        "model": MODEL,
        "input": prompt,
        "max_output_tokens": 900,
        "temperature": 0.2,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "conversa_enriquecida",
            "schema": {
                "type": "object",
                "properties": {
                    "resumo_curto": {"type": "string"},
                    "pontos_positivos": {"type": "array", "items": {"type": "string"}},
                    "pontos_negativos": {"type": "array", "items": {"type": "string"}},
                    "eventos_timeline": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "minuto": {"type": "number"},
                                "tipo": {"type": "string"},
                                "descricao": {"type": "string"},
                            },
                            "required": ["minuto", "tipo", "descricao"],
                        },
                    },
                    "alertas": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severidade": {"type": "string"},
                                "mensagem": {"type": "string"},
                            },
                            "required": ["severidade", "mensagem"],
                        },
                    },
                },
                "required": ["resumo_curto", "pontos_positivos", "pontos_negativos"],
            },
        }},
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    response = requests.post(f"{API_BASE}/responses", headers=headers, json=payload, timeout=120)
    if response.status_code >= 400:
        raise RuntimeError(f"Erro OpenAI {response.status_code}: {response.text}")
    content = response.json()
    output = content.get("output") or content.get("responses")
    if not output:
        raise RuntimeError(f"Resposta inválida: {content}")
    text = output[0].get("content", [{}])[0].get("text")
    if not text:
        raise RuntimeError(f"Conteúdo vazio na resposta: {content}")
    return json.loads(text)


def main() -> int:
    metadata_path = ROOT / "metadata.csv"
    if not metadata_path.exists():
        print("metadata.csv não encontrado", file=sys.stderr)
    enrichment: Dict[str, Any] = {}

    per_call = json.load((ROOT / "full_analysis.json").open("r", encoding="utf-8"))
    details = per_call.get("per_call_details", [])
    for index, item in enumerate(details, 1):
        call_id = item["call_id"]
        try:
            transcript = load_transcript(call_id)
            prompt = build_prompt(transcript)
            summary = openai_response(prompt)
            enrichment[call_id] = summary
            print(f"[{index}/{len(details)}] Enriquecido {call_id}")
            time.sleep(float(os.environ.get("OPENAI_SLEEP", "0.5")))
        except Exception as error:  # noqa: BLE001
            print(f"Falha ao enriquecer {call_id}: {error}", file=sys.stderr)

    OUTPUT_PATH.write_text(json.dumps(enrichment, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Enriquecimento salvo em {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
