#!/usr/bin/env python3
"""
Script para atualizar agent_name_detected no full_analysis.json com dados do CSV.

Atualiza TODOS os registros com operador_izzi do CSV (dados oficiais).
Cria backup antes de modificar.

Uso:
    python3 izzi-intelligence-dashboard/engine/backfill_agent_names.py
"""
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict

# Caminhos
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ENGINE_JSON = BASE_DIR / "full_analysis.json"
FRONTEND_JSON = PROJECT_DIR / "public" / "data" / "full_analysis.json"

# CSVs conhecidos (adicionar mais se necessário)
CSV_PATHS = [
    BASE_DIR / "metadata.csv",  # CSV local do engine
    Path("/home/jota/tools/paneas-col/izzi_batch_20251120_01_9530/izzi_batch_20251120_01_9530.csv"),
]


def load_agent_mapping() -> Dict[str, str]:
    """Carrega mapeamento call_id -> operador_izzi de todos os CSVs."""
    agent_map = {}

    for csv_path in CSV_PATHS:
        if not csv_path.exists():
            print(f"⚠️  CSV não encontrado: {csv_path}")
            continue

        print(f"📄 Lendo CSV: {csv_path.name}")

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0

            for row in reader:
                # Extrair identificador único da chamada
                exec_id = row.get('id_exec_paneas', '').strip()
                operator_izzi = row.get('operador_izzi', '').strip()

                if exec_id and operator_izzi:
                    agent_map[exec_id] = operator_izzi
                    count += 1

        print(f"   ✓ {count} registros com operador_izzi")

    print(f"\n📊 Total de mapeamentos: {len(agent_map)}")
    return agent_map


def update_full_analysis(json_path: Path, agent_map: Dict[str, str], dry_run: bool = False):
    """Atualiza full_analysis.json com agent_name do CSV."""

    if not json_path.exists():
        print(f"❌ JSON não encontrado: {json_path}")
        return

    print(f"\n{'🔍 [DRY RUN] ' if dry_run else '🔄 '}Processando: {json_path}")

    # Criar backup
    if not dry_run:
        backup_path = json_path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        shutil.copy2(json_path, backup_path)
        print(f"💾 Backup criado: {backup_path.name}")

    # Carregar JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    calls = data.get('per_call_details', [])
    total = len(calls)

    # Estatísticas
    updated = 0
    matched = 0
    not_found = 0
    already_had = 0

    for call in calls:
        exec_id = call.get('exec_id', '').strip()
        current_agent = call.get('agent_name_detected')

        if not exec_id:
            not_found += 1
            continue

        # Buscar no mapa
        csv_agent = agent_map.get(exec_id)

        if csv_agent:
            matched += 1

            # Atualizar SEMPRE com dado do CSV (mais confiável)
            if current_agent != csv_agent:
                call['agent_name_detected'] = csv_agent
                call['agent_name_confidence'] = 1.0
                call['agent_name_source'] = 'metadata'
                updated += 1
            else:
                # Já tinha o nome correto, apenas garantir source e confidence
                if call.get('agent_name_confidence') != 1.0 or call.get('agent_name_source') != 'metadata':
                    call['agent_name_confidence'] = 1.0
                    call['agent_name_source'] = 'metadata'
                    updated += 1
                else:
                    already_had += 1
        else:
            not_found += 1

    # Salvar
    if not dry_run:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # Relatório
    print(f"\n📈 Estatísticas:")
    print(f"   Total de chamadas: {total}")
    print(f"   Encontrados no CSV: {matched} ({100*matched/total:.1f}%)")
    print(f"   Atualizados: {updated}")
    print(f"   Já estavam corretos: {already_had}")
    print(f"   Não encontrados no CSV: {not_found}")

    if not dry_run:
        print(f"\n✅ JSON atualizado com sucesso!")
    else:
        print(f"\n🔍 DRY RUN - nenhuma alteração foi feita")


def main():
    print("="*60)
    print("🔧 Backfill de agent_name_detected")
    print("="*60)

    # Carregar mapeamento
    agent_map = load_agent_mapping()

    if not agent_map:
        print("\n❌ Nenhum mapeamento encontrado nos CSVs!")
        return

    # Atualizar engine/full_analysis.json
    if ENGINE_JSON.exists():
        update_full_analysis(ENGINE_JSON, agent_map)

    # Atualizar public/data/full_analysis.json
    if FRONTEND_JSON.exists():
        update_full_analysis(FRONTEND_JSON, agent_map)

    print("\n" + "="*60)
    print("✅ Processo concluído!")
    print("="*60)
    print("\n💡 Próximos passos:")
    print("   1. Verificar um registro atualizado")
    print("   2. Copiar para container (se necessário):")
    print("      docker cp izzi-intelligence-dashboard/public/data/full_analysis.json \\")
    print("        stack-izzi-dashboard:/app/dist/data/full_analysis.json")


if __name__ == "__main__":
    main()
