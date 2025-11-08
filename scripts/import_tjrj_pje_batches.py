#!/usr/bin/env python3
"""
Script otimizado para importar processos TJRJ PJE Autenticado EM LOTES (evita timeout).

A estratégia em lotes resolve o problema de timeout ao navegar 2500+ páginas:
- Busca 100 páginas (~2k processos) por vez
- Import

a esse lote
- Repete até acabar

Uso:
    python import_tjrj_pje_batches.py --parallel 30 --batch-pages 100
"""
import asyncio
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
import asyncpg

# Configurar path
if os.path.exists('/app'):
    sys.path.insert(0, '/app')
else:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

try:
    from config import get_settings
    settings = get_settings()
except:
    class Settings:
        postgres_user = os.getenv("POSTGRES_USER", "paneas")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "paneas")
        postgres_host = os.getenv("POSTGRES_HOST", "postgres")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        postgres_db = os.getenv("POSTGRES_DB", "aistack")
    settings = Settings()

# Configurações
CPF = "48561184809"
SENHA = "Julho3007!@"
NOME_PARTE = "Claro S.A"
SCRAPPER_URL = "http://scrapper:8080" if os.path.exists('/app') else "http://localhost:8089"
DB_URL = None


async def get_db_pool():
    """Cria pool de conexões com o banco."""
    global DB_URL
    if not DB_URL:
        if os.path.exists('/app'):
            db_host = settings.postgres_host
            db_port = settings.postgres_port
        else:
            db_host = "localhost"
            db_port = 5432

        DB_URL = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{db_host}:{db_port}/{settings.postgres_db}"
        print(f"[DB] Connecting to: postgresql://***:***@{db_host}:{db_port}/{settings.postgres_db}")

    return await asyncpg.create_pool(
        DB_URL,
        min_size=10,
        max_size=50,
        command_timeout=60
    )


async def buscar_processos_lote(
    client: httpx.AsyncClient,
    batch_pages: int,
    extract_details: bool = False,
    max_details: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Busca UM LOTE de processos (batch_pages páginas).
    Retorna lista de resumos: [{"numeroProcesso": "...", "link": "..."}, ...]
    Se extract_details=True, retorna processos com movimentos e documentos completos.
    """
    print(f"[LOTE] Buscando primeiras {batch_pages} páginas...")
    if extract_details:
        print(f"[LOTE] Modo: Extração de DETALHES habilitada (max_details={max_details or 'todos'})")

    url = f"{SCRAPPER_URL}/v1/processos/tjrj-pje-auth/listar"
    payload = {
        "cpf": CPF,
        "senha": SENHA,
        "nome_parte": NOME_PARTE,
        "max_pages": batch_pages,
        "extract_details": extract_details,
        "max_details": max_details
    }

    # Timeout de 15 minutos para o lote (ou mais se estiver extraindo detalhes)
    timeout = 1800.0 if extract_details else 900.0
    response = await client.post(url, json=payload, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    processos = data.get("processos", [])

    print(f"[LOTE] ✓ Encontrados {len(processos)} processos")
    return processos


# REMOVIDO: buscar_detalhes_processo
# O endpoint /consulta não funciona pra processos que não estão na primeira página.
# Vamos usar os dados do ProcessoResumoTJRJ que já tem as informações necessárias.


async def salvar_processo_db(pool: asyncpg.Pool, processo: Dict[str, Any]) -> bool:
    """Salva processo no banco de dados."""
    if not processo:
        return False

    try:
        async with pool.acquire() as conn:
            from uuid import uuid4
            import json

            numero = processo.get("numeroProcesso")

            # Verificar se já existe
            existing = await conn.fetchrow(
                "SELECT id FROM processos.processos_judiciais WHERE numero_processo = $1 AND tribunal = 'TJRJ'",
                numero
            )

            if existing:
                return False

            # Inserir novo
            processo_id = uuid4()
            dados_completos = json.dumps(processo, default=str, ensure_ascii=False)

            await conn.execute(
                """
                INSERT INTO processos.processos_judiciais (
                    id, numero_processo, tribunal, uf, classe, assunto, comarca, vara, juiz,
                    data_distribuicao, valor_causa, situacao, link_publico, dados_completos
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                processo_id,
                numero,
                "TJRJ",
                processo.get("uf"),
                processo.get("classe"),
                processo.get("assunto"),
                processo.get("comarca"),
                processo.get("vara"),
                processo.get("juiz"),
                None,
                processo.get("valorCausa"),
                processo.get("situacao"),
                processo.get("linkPublico"),
                dados_completos
            )

            # Salvar partes (ProcessoResumoTJRJ tem partesRelacionadas)
            # Agora partesRelacionadas contém objetos {tipo: 'autor'/'reu', nome: 'NOME'}
            for parte in processo.get("partesRelacionadas", []):
                # parte é um objeto {tipo: 'autor'/'reu', nome: 'NOME DA PARTE'}
                tipo = parte.get("tipo", "outro") if isinstance(parte, dict) else "outro"
                nome = parte.get("nome") if isinstance(parte, dict) else parte

                if nome:  # só salva se tem nome
                    await conn.execute(
                        "INSERT INTO processos.processos_partes (id, processo_id, tipo, nome) VALUES ($1, $2, $3, $4)",
                        uuid4(), processo_id, tipo, nome
                    )

            return True

    except Exception as e:
        print(f"[DB] ✗ {processo.get('numeroProcesso')} - Erro: {e}")
        return False


async def processar_processo(
    pool: asyncpg.Pool,
    processo_resumo: Dict[str, Any],
    stats: Dict[str, Any]
) -> bool:
    """Salva processo (usa dados do ProcessoResumoTJRJ diretamente)."""
    sucesso = await salvar_processo_db(pool, processo_resumo)
    if sucesso:
        stats['salvos'] += 1
    else:
        stats['ja_existiam'] += 1
    stats['processados'] += 1
    return sucesso


async def import_in_batches(
    max_concurrent: int = 30,
    batch_pages: int = 100,
    extract_details: bool = False,
    max_details: Optional[int] = None
):
    """Importa processos em LOTES para evitar timeout."""
    log_file = "/tmp/import_tjrj_progress.log"

    print("=" * 80)
    print(f"IMPORTAÇÃO POR LOTES")
    print(f"Concorrência: {max_concurrent} | Lote: {batch_pages} páginas (~{batch_pages * 20} processos)")
    if extract_details:
        print(f"Extração de detalhes: HABILITADA (max_details={max_details or 'todos'})")
    print("=" * 80)

    # Limpar log anterior
    with open(log_file, 'w') as f:
        f.write(f"=== IMPORTAÇÃO INICIADA EM {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"Concorrência: {max_concurrent}\n")
        f.write(f"Tamanho do lote: {batch_pages} páginas\n\n")

    pool = await get_db_pool()
    semaphore = asyncio.Semaphore(max_concurrent)

    # Estatísticas globais
    stats_global = {
        'processados': 0,
        'salvos': 0,
        'ja_existiam': 0,
        'erros': 0
    }

    inicio_global = datetime.now()
    current_batch = 1

    async with httpx.AsyncClient(timeout=httpx.Timeout(1000.0)) as client:
        while True:
            inicio_lote = datetime.now()

            print(f"\n{'='*80}")
            print(f"LOTE {current_batch} - Páginas {(current_batch-1)*batch_pages + 1} até {current_batch*batch_pages}")
            print(f"{'='*80}")

            # 1. Buscar lote de processos
            # Cada lote aumenta o max_pages (busca cumulativo)
            # current_batch=1: busca páginas 1-100
            # current_batch=2: busca páginas 1-200 (mas só processa os novos)
            # current_batch=3: busca páginas 1-300 (mas só processa os novos)
            try:
                max_pages_cumulative = current_batch * batch_pages
                processos_resumo = await buscar_processos_lote(
                    client,
                    max_pages_cumulative,
                    extract_details=extract_details,
                    max_details=max_details
                )
            except Exception as e:
                print(f"[LOTE] ✗ Erro ao buscar lote: {e}")
                break

            if not processos_resumo:
                print("[LOTE] ✓ Nenhum processo novo encontrado. Finalizando...")
                break

            total_lote = len(processos_resumo)
            print(f"[LOTE] Total no lote: {total_lote}")

            # 2. Estatísticas do lote
            stats_lote = {
                'processados': 0,
                'salvos': 0,
                'ja_existiam': 0,
                'erros': 0
            }

            # 3. Processar lote em paralelo (salvar diretamente no DB)
            tasks = [
                processar_processo(pool, p, stats_lote)
                for p in processos_resumo
            ]

            print(f"[LOTE] Salvando {total_lote} processos no banco...")
            await asyncio.gather(*tasks, return_exceptions=True)

            # 4. Atualizar estatísticas globais
            stats_global['processados'] += stats_lote['processados']
            stats_global['salvos'] += stats_lote['salvos']
            stats_global['ja_existiam'] += stats_lote['ja_existiam']
            stats_global['erros'] += stats_lote['erros']

            # 5. Exibir estatísticas do lote
            duracao_lote = (datetime.now() - inicio_lote).total_seconds()
            print(f"\n[LOTE {current_batch}] RESULTADO:")
            print(f"  ✓ Salvos: {stats_lote['salvos']}")
            print(f"  ⊙ Já existiam: {stats_lote['ja_existiam']}")
            print(f"  ✗ Erros: {stats_lote['erros']}")
            print(f"  ⏱  Duração: {duracao_lote:.1f}s ({duracao_lote/60:.1f} min)")
            print(f"  📊 Taxa: {total_lote/duracao_lote:.2f} processos/s")

            # 6. Log
            with open(log_file, 'a') as f:
                f.write(f"\n[LOTE {current_batch}] ✓{stats_lote['salvos']} ⊙{stats_lote['ja_existiam']} ✗{stats_lote['erros']} | {duracao_lote:.1f}s\n")

            # 7. Se todos já existiam, provavelmente acabou
            if stats_lote['salvos'] == 0 and stats_lote['ja_existiam'] == total_lote:
                print(f"\n[LOTE] ✓ Todos os processos deste lote já existiam. Provavelmente terminamos!")
                break

            current_batch += 1

    # Estatísticas finais
    fim_global = datetime.now()
    duracao_total = (fim_global - inicio_global).total_seconds()

    print(f"\n{'='*80}")
    print("RESULTADO FINAL DA IMPORTAÇÃO")
    print(f"{'='*80}")
    print(f"Total de processos: {stats_global['processados']}")
    print(f"✓ Salvos com sucesso: {stats_global['salvos']}")
    print(f"⊙ Já existiam: {stats_global['ja_existiam']}")
    print(f"✗ Erros: {stats_global['erros']}")
    print(f"Duração total: {duracao_total:.2f}s ({duracao_total/60:.1f} minutos)")
    if stats_global['processados'] > 0:
        print(f"Taxa média: {stats_global['processados']/duracao_total:.2f} processos/segundo")
    print(f"{'='*80}")

    with open(log_file, 'a') as f:
        f.write(f"\n=== FINALIZADO EM {fim_global.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"✓ Salvos: {stats_global['salvos']}\n")
        f.write(f"⊙ Já existiam: {stats_global['ja_existiam']}\n")
        f.write(f"✗ Erros: {stats_global['erros']}\n")
        f.write(f"Duração: {duracao_total/60:.1f} min\n")

    await pool.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Importar processos TJRJ PJE em lotes (evita timeout)")
    parser.add_argument("--parallel", type=int, default=30, help="Número de requisições paralelas")
    parser.add_argument("--batch-pages", type=int, default=100, help="Páginas por lote")
    parser.add_argument("--extract-details", action="store_true", help="Extrair detalhes completos (movimentos, documentos)")
    parser.add_argument("--max-details", type=int, default=None, help="Máximo de processos para extrair detalhes (útil para testes)")

    args = parser.parse_args()

    asyncio.run(import_in_batches(
        max_concurrent=args.parallel,
        batch_pages=args.batch_pages,
        extract_details=args.extract_details,
        max_details=args.max_details
    ))


if __name__ == "__main__":
    main()
