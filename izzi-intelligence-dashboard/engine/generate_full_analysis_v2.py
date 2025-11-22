#!/usr/bin/env python3
"""
Pipeline geração de análises (heurística + LLM).

Etapas:
 1. Executa o motor heurístico padrão (`generate_full_analysis.py`).
 2. Copia `engine/full_analysis.json` para `public/data/full_analysis.json`.
 3. (Opcional) Enriquecer com OpenAI (`llm_enrichment.enrich_calls`).

Uso:
    python engine/generate_full_analysis_v2.py
    python engine/generate_full_analysis_v2.py --no-llm
    python engine/generate_full_analysis_v2.py --model gpt-5-mini --workers 6
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import generate_full_analysis
from llm_enrichment import enrich_calls

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ENGINE_OUTPUT = BASE_DIR / "full_analysis.json"
FRONTEND_OUTPUT = PROJECT_DIR / "public" / "data" / "full_analysis.json"


def load_call_ids(path: Path) -> list[str]:
    with path.open() as handle:
        data = json.load(handle)
    details = data.get("per_call_details") or []
    return [item.get("call_id") for item in details if item.get("call_id")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline heurística + LLM para o dashboard.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Pula a etapa de enriquecimento com OpenAI (gera apenas heurística).",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Modelo OpenAI para enriquecimento (padrão: gpt-4o-mini).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Número de threads para o enriquecimento (padrão: núcleos disponíveis).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suprime logs detalhados do enriquecimento.",
    )
    args = parser.parse_args()

    print("==> Executando heurística (generate_full_analysis.py)...")
    generate_full_analysis.main()
    if not ENGINE_OUTPUT.exists():
        raise FileNotFoundError(f"Arquivo heurístico não encontrado: {ENGINE_OUTPUT}")

    FRONTEND_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ENGINE_OUTPUT, FRONTEND_OUTPUT)
    print(f"==> Copiado para {FRONTEND_OUTPUT.relative_to(PROJECT_DIR)}")

    if args.no_llm:
        print("==> Etapa de LLM ignorada (--no-llm).")
        return

    call_ids = load_call_ids(ENGINE_OUTPUT)
    print(f"==> Enriquecendo {len(call_ids)} chamadas com {args.model}...")
    successes, failures = enrich_calls(
        call_ids,
        model=args.model,
        workers=args.workers,
        verbose=not args.quiet,
    )
    print(f"==> Enriquecimento concluído. Sucesso: {successes}, Falhas: {len(failures)}")
    if failures and not args.quiet:
        for cid, message in failures:
            print(f"   - {cid}: {message}")


if __name__ == "__main__":
    main()
