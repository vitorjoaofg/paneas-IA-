#!/usr/bin/env python3
"""
Reprocessa apenas o enriquecimento LLM para arquivos que já têm transcrição.
"""
import sys
from pathlib import Path

# Adiciona o diretório engine ao path para importar os módulos
ENGINE_DIR = Path(__file__).parent / "izzi-intelligence-dashboard" / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import generate_full_analysis_v3 as g

def main():
    # Lê a lista de IDs que precisam de LLM
    need_llm_file = Path("/tmp/need_llm.txt")
    if not need_llm_file.exists():
        print("❌ Arquivo /tmp/need_llm.txt não encontrado!")
        print("Execute o comando de identificação primeiro.")
        return 1

    call_ids = need_llm_file.read_text().strip().split('\n')
    call_ids = [cid.strip() for cid in call_ids if cid.strip()]

    print(f"📊 Processando LLM para {len(call_ids)} arquivos...")

    # Carrega metadata
    metadata = g.load_metadata(g.METADATA_FILE)

    # Prepara chamadas
    print("==> Preparando chamadas...")
    prepared = g.prepare_calls(call_ids, metadata)

    # Executa pipeline LLM
    print(f"==> Executando LLM com modelo gpt-4o-mini e 8 workers...")
    per_call_details, successes, failures = g.run_llm_pipeline(
        prepared,
        model="gpt-4o-mini",
        workers=8
    )

    # Mescla com análise existente
    print("==> Mesclando com full_analysis.json existente...")
    engine_file = ENGINE_DIR / "full_analysis.json"
    frontend_file = ENGINE_DIR.parent / "public" / "data" / "full_analysis.json"

    try:
        import json
        existing = json.loads(engine_file.read_text())
    except FileNotFoundError:
        existing = {
            "dataset_summary": {},
            "status_analysis": {},
            "divergence_summary": {},
            "per_call_details": []
        }

    # Cria índice por call_id
    index = {item.get("call_id"): item for item in existing.get("per_call_details") or []}

    # Adiciona os novos
    for detail in per_call_details:
        call_id = detail.get("call_id")
        if call_id:
            index[call_id] = detail

    merged_calls = list(index.values())

    # Recomputa sumários
    print("==> Recomputando sumários...")
    dataset_summary = g.compute_dataset_summary(merged_calls)
    dataset_summary["recurrence_summary"] = g.compute_recurrence_summary(merged_calls)
    status_analysis = g.compute_status_analysis(merged_calls)
    divergence_summary = g.compute_divergence_summary(merged_calls, dataset_summary)

    out = {
        "dataset_summary": dataset_summary,
        "status_analysis": status_analysis,
        "divergence_summary": divergence_summary,
        "per_call_details": merged_calls,
    }

    # Salva
    print("==> Salvando resultados...")
    engine_file.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    frontend_file.parent.mkdir(parents=True, exist_ok=True)
    frontend_file.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"\n✅ Concluído!")
    print(f"   Sucessos: {successes}")
    print(f"   Falhas: {len(failures)}")
    print(f"   Total no full_analysis.json: {len(merged_calls)}")

    if failures:
        print(f"\n⚠️  Falhas:")
        for call_id, error in failures[:10]:
            print(f"   - {call_id}: {error[:100]}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
