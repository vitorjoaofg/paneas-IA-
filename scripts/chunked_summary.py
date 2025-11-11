#!/usr/bin/env python3
"""Helper CLI to summarize long documents without hitting the context limit."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, List

import requests


def chunk_text(text: str, max_chunk_chars: int) -> List[str]:
    """Split text into blocks with soft paragraph boundaries."""

    paragraphs = [p.strip() for p in text.split("\n\n")]
    paragraphs = [p for p in paragraphs if p]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for paragraph in paragraphs:
        para_len = len(paragraph)
        if para_len >= max_chunk_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for start in range(0, para_len, max_chunk_chars):
                chunks.append(paragraph[start : start + max_chunk_chars])
            continue

        if current_len + para_len + (2 if current else 0) > max_chunk_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = para_len
        else:
            current.append(paragraph)
            current_len += para_len if not current_len else para_len + 2

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def call_llm(endpoint: str, token: str, payload: dict) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.post(endpoint, headers=headers, json=payload, timeout=120)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - manual CLI only
        detail = response.text
        raise SystemExit(f"LLM request failed: {exc}\n{detail}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def summarize_chunks(
    chunks: Iterable[str],
    endpoint: str,
    token: str,
    model: str,
    system_prompt: str,
    chunk_system_prompt: str,
    chunk_max_tokens: int,
    final_max_tokens: int,
) -> str:
    partial_summaries: List[str] = []
    chunks_list = list(chunks)
    total = len(chunks_list)

    for idx, chunk in enumerate(chunks_list, start=1):
        print(f"→ Resumindo trecho {idx}/{total} ({len(chunk)} chars)...", file=sys.stderr)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": chunk_system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Trecho {idx} de {total}. Construa até quatro frases claras, "
                        f"preservando quantias, nomes e pedidos relevantes.\n\n{chunk}"
                    ),
                },
            ],
            "max_tokens": chunk_max_tokens,
        }
        summary = call_llm(endpoint, token, payload)
        partial_summaries.append(f"Trecho {idx}: {summary}")

    summaries_text = "\n\n".join(partial_summaries)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Use os resumos numerados abaixo para escrever um único parágrafo "
                    "coeso destacando contexto, pedidos e fundamentos jurídicos principais.\n\n"
                    f"{summaries_text}"
                ),
            },
        ],
        "max_tokens": final_max_tokens,
    }
    print("→ Gerando resumo final consolidado...", file=sys.stderr)
    return call_llm(endpoint, token, payload)


def read_input(path: Path | None) -> str:
    if path:
        return path.read_text(encoding="utf-8")
    return sys.stdin.read()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk + summarize long texts via Paneas LLM")
    parser.add_argument("--input", "-i", type=Path, help="Arquivo de texto (padrão: stdin)")
    parser.add_argument("--api-url", default="https://jota.ngrok.app/api/v1", help="Base do endpoint /api/v1")
    parser.add_argument("--token", default=os.environ.get("PANEAS_API_TOKEN"), help="Bearer token (ou defina PANEAS_API_TOKEN)")
    parser.add_argument("--model", default="paneas-q32b", help="Modelo a ser usado")
    parser.add_argument("--chunk-chars", type=int, default=6000, help="Qtd máx. de caracteres por trecho")
    parser.add_argument("--chunk-max-tokens", type=int, default=320, help="max_tokens para cada chamada parcial")
    parser.add_argument("--final-max-tokens", type=int, default=256, help="max_tokens para o resumo final")
    parser.add_argument(
        "--system",
        default="Você é um assistente útil que resume texto longo em 1 parágrafo",
        help="Prompt de sistema para o resumo final",
    )
    parser.add_argument(
        "--chunk-system",
        default=(
            "Você converte trechos extensos em notas objetivas, destacando fatos, datas, valores e pedidos "
            "sem inventar informações."
        ),
        help="Prompt de sistema usado em cada trecho",
    )

    args = parser.parse_args()
    if not args.token:
        parser.error("Token não informado (use --token ou PANEAS_API_TOKEN)")
    return args


def main() -> None:
    args = parse_args()
    text = read_input(args.input).strip()
    if not text:
        raise SystemExit("Nenhum conteúdo fornecido")

    chunks = chunk_text(text, args.chunk_chars)
    if not chunks:
        raise SystemExit("Texto vazio após segmentação")

    endpoint = args.api_url.rstrip("/") + "/chat/completions"
    final_summary = summarize_chunks(
        chunks,
        endpoint,
        args.token,
        args.model,
        args.system,
        args.chunk_system,
        args.chunk_max_tokens,
        args.final_max_tokens,
    )

    print("\n===== RESUMO FINAL =====\n")
    print(final_summary)


if __name__ == "__main__":
    main()
