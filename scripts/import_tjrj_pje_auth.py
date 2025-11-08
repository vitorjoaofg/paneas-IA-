#!/usr/bin/env python3
"""
Script otimizado para importar processos TJRJ PJE Autenticado em paralelo.
Uso:
    # Testar com 1 processo:
    python import_tjrj_pje_auth.py --test

    # Importar todos com paralelização:
    python import_tjrj_pje_auth.py --parallel 30
"""
import asyncio
import sys
import os
from typing import List, Dict, Any
from datetime import datetime
import httpx
import asyncpg

# Configurar path se rodar de fora do container
if os.path.exists('/app'):
    # Rodando dentro do container
    sys.path.insert(0, '/app')
else:
    # Rodando fora do container
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

try:
    from config import get_settings
    settings = get_settings()
except:
    # Fallback se não conseguir importar
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
DB_URL = None  # Will be set from settings


async def get_db_pool():
    """Cria pool de conexões com o banco."""
    global DB_URL
    if not DB_URL:
        # If inside container, use service name; if outside, use localhost
        if os.path.exists('/app'):
            # Inside container - use settings as is
            db_host = settings.postgres_host
            db_port = settings.postgres_port
        else:
            # Outside container - use localhost
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


async def buscar_processos_listagem(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """
    Busca TODOS os processos da listagem.
    Retorna lista de resumos: [{"numeroProcesso": "...", "link": "..."}, ...]
    """
    print(f"[LISTAR] Buscando processos de '{NOME_PARTE}'...")

    url = f"{SCRAPPER_URL}/v1/processos/tjrj-pje-auth/listar"
    payload = {
        "cpf": CPF,
        "senha": SENHA,
        "nome_parte": NOME_PARTE
    }

    # Timeout de 2 HORAS para listagem completa
    # São ~2500 páginas × 2s/página = ~5000s = 1h23min
    print(f"[LISTAR] Aguarde... isso pode demorar até 1h30min (navegando ~2500 páginas)")
    response = await client.post(url, json=payload, timeout=7200.0)
    response.raise_for_status()

    data = response.json()
    processos = data.get("processos", [])

    print(f"[LISTAR] ✓ Encontrados {len(processos)} processos")
    return processos


async def buscar_detalhes_processo(
    client: httpx.AsyncClient,
    numero_processo: str,
    semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """
    Busca detalhes completos de UM processo específico.
    Usa semaphore para controlar concorrência.
    """
    async with semaphore:
        url = f"{SCRAPPER_URL}/v1/processos/tjrj-pje-auth/consulta"
        payload = {
            "cpf": CPF,
            "senha": SENHA,
            "numero_processo": numero_processo
        }

        try:
            response = await client.post(url, json=payload, timeout=300.0)
            response.raise_for_status()
            processo = response.json()
            return processo
        except Exception as e:
            print(f"[DETALHE] ✗ {numero_processo} - Erro: {e}")
            return None


async def salvar_processo_db(pool: asyncpg.Pool, processo: Dict[str, Any]) -> bool:
    """Salva processo no banco de dados."""
    if not processo:
        return False

    try:
        async with pool.acquire() as conn:
            # Usar a função de salvar do processos_db (adaptada para receber conn)
            numero = processo.get("numeroProcesso")

            # Verificar se já existe
            existing = await conn.fetchrow(
                "SELECT id FROM processos.processos_judiciais WHERE numero_processo = $1 AND tribunal = 'TJRJ'",
                numero
            )

            if existing:
                return False

            # Inserir novo
            from uuid import uuid4
            import json

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
                None,  # data_distribuicao
                processo.get("valorCausa"),
                processo.get("situacao"),
                processo.get("linkPublico"),
                dados_completos
            )

            # Salvar partes
            if processo.get("autor"):
                await conn.execute(
                    "INSERT INTO processos.processos_partes (id, processo_id, tipo, nome) VALUES ($1, $2, $3, $4)",
                    uuid4(), processo_id, "autor", processo["autor"]
                )

            if processo.get("reu"):
                await conn.execute(
                    "INSERT INTO processos.processos_partes (id, processo_id, tipo, nome) VALUES ($1, $2, $3, $4)",
                    uuid4(), processo_id, "reu", processo["reu"]
                )

            for adv in processo.get("advogados", []):
                await conn.execute(
                    "INSERT INTO processos.processos_partes (id, processo_id, tipo, nome) VALUES ($1, $2, $3, $4)",
                    uuid4(), processo_id, "advogado", adv
                )

            return True

    except Exception as e:
        print(f"[DB] ✗ {processo.get('numeroProcesso')} - Erro: {e}")
        return False


async def processar_processo(
    client: httpx.AsyncClient,
    pool: asyncpg.Pool,
    numero_processo: str,
    semaphore: asyncio.Semaphore,
    stats: Dict[str, Any]
) -> bool:
    """Busca detalhes E salva no banco."""
    processo = await buscar_detalhes_processo(client, numero_processo, semaphore)

    if processo:
        sucesso = await salvar_processo_db(pool, processo)
        if sucesso:
            stats['salvos'] += 1
        else:
            stats['ja_existiam'] += 1
        stats['processados'] += 1
        return sucesso
    else:
        stats['erros'] += 1
        stats['processados'] += 1
        return False


async def test_one_processo():
    """Testa com apenas 1 processo."""
    print("=" * 80)
    print("TESTE: Importando 1 processo da página 3")
    print("=" * 80)

    pool = await get_db_pool()

    async with httpx.AsyncClient() as client:
        # Buscar processo de teste da página 3
        url = f"{SCRAPPER_URL}/v1/processos/tjrj-pje-auth/test-page3"
        payload = {"cpf": CPF, "senha": SENHA, "nome_parte": NOME_PARTE}

        print("[TEST] Buscando processo da página 3...")
        response = await client.post(url, json=payload, timeout=300.0)
        response.raise_for_status()
        processo = response.json()

        numero = processo.get("numeroProcesso")
        print(f"[TEST] ✓ Processo obtido: {numero}")
        print(f"[TEST]   - Autor: {processo.get('autor')}")
        print(f"[TEST]   - Réu: {processo.get('reu')}")
        print(f"[TEST]   - Advogados: {len(processo.get('advogados', []))}")
        print(f"[TEST]   - Movimentos: {len(processo.get('movimentos', []))}")
        print(f"[TEST]   - Documentos: {len(processo.get('documentos', []))}")

        # Salvar no banco
        print(f"\n[TEST] Salvando no banco...")
        sucesso = await salvar_processo_db(pool, processo)

        if sucesso:
            print(f"[TEST] ✓✓✓ SUCESSO! Processo {numero} salvo no banco")
        else:
            print(f"[TEST] ⊙ Processo já existia no banco")

    await pool.close()


async def monitor_progress(stats: Dict[str, Any], total: int, log_file: str):
    """Monitora e exibe progresso em tempo real."""
    import time

    inicio = time.time()
    ultimo_report = 0

    while stats['processados'] < total:
        await asyncio.sleep(2)  # Atualizar a cada 2 segundos

        processados = stats['processados']
        salvos = stats['salvos']
        ja_existiam = stats['ja_existiam']
        erros = stats['erros']

        # Calcular estatísticas
        elapsed = time.time() - inicio
        if processados > 0:
            taxa = processados / elapsed
            restantes = total - processados
            tempo_restante = restantes / taxa if taxa > 0 else 0

            # Formatar tempo restante
            horas = int(tempo_restante // 3600)
            minutos = int((tempo_restante % 3600) // 60)
            segundos = int(tempo_restante % 60)

            # Progress bar
            percent = (processados / total) * 100
            bar_len = 50
            filled = int(bar_len * processados / total)
            bar = '█' * filled + '░' * (bar_len - filled)

            # Log a cada 10 processos ou a cada 30s
            if processados - ultimo_report >= 10 or (elapsed - stats.get('last_log_time', 0)) > 30:
                msg = f"[{datetime.now().strftime('%H:%M:%S')}] {bar} {percent:.1f}% | {processados}/{total} | ✓{salvos} ⊙{ja_existiam} ✗{erros} | Taxa: {taxa:.2f}/s | Resta: {horas:02d}:{minutos:02d}:{segundos:02d}"
                print(msg)

                # Salvar em arquivo
                with open(log_file, 'a') as f:
                    f.write(msg + '\n')

                ultimo_report = processados
                stats['last_log_time'] = elapsed


async def import_all_parallel(max_concurrent: int = 10):
    """Importa TODOS os processos em paralelo com progresso em tempo real."""
    log_file = "/tmp/import_tjrj_progress.log"

    print("=" * 80)
    print(f"IMPORTAÇÃO EM PARALELO (concorrência: {max_concurrent})")
    print("=" * 80)

    # Limpar log anterior
    with open(log_file, 'w') as f:
        f.write(f"=== IMPORTAÇÃO INICIADA EM {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(f"Concorrência: {max_concurrent}\n\n")

    print(f"[PROGRESS] Log em tempo real: tail -f {log_file}\n")

    pool = await get_db_pool()
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=httpx.Timeout(7200.0)) as client:
        # 1. Buscar listagem completa
        processos_resumo = await buscar_processos_listagem(client)
        total = len(processos_resumo)

        print(f"[IMPORT] Total de processos: {total}")
        print(f"[IMPORT] Concorrência máxima: {max_concurrent}")
        print(f"[IMPORT] Iniciando importação...\n")

        with open(log_file, 'a') as f:
            f.write(f"Total de processos: {total}\n\n")

        # 2. Estatísticas compartilhadas
        stats = {
            'processados': 0,
            'salvos': 0,
            'ja_existiam': 0,
            'erros': 0,
            'last_log_time': 0
        }

        # 3. Iniciar monitor de progresso
        inicio = datetime.now()
        monitor_task = asyncio.create_task(monitor_progress(stats, total, log_file))

        # 4. Processar todos em paralelo
        tasks = [
            processar_processo(client, pool, p["numeroProcesso"], semaphore, stats)
            for p in processos_resumo
        ]

        resultados = await asyncio.gather(*tasks, return_exceptions=True)

        # 5. Cancelar monitor
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        fim = datetime.now()
        duracao = (fim - inicio).total_seconds()

        # 6. Estatísticas finais
        print("\n" + "=" * 80)
        print("RESULTADO DA IMPORTAÇÃO")
        print("=" * 80)
        print(f"Total de processos: {total}")
        print(f"✓ Salvos com sucesso: {stats['salvos']}")
        print(f"⊙ Já existiam: {stats['ja_existiam']}")
        print(f"✗ Erros: {stats['erros']}")
        print(f"Duração: {duracao:.2f}s ({duracao/60:.1f} minutos)")
        print(f"Taxa média: {total/duracao:.2f} processos/segundo")
        print("=" * 80)

        with open(log_file, 'a') as f:
            f.write(f"\n=== FINALIZADO EM {fim.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"✓ Salvos: {stats['salvos']}\n")
            f.write(f"⊙ Já existiam: {stats['ja_existiam']}\n")
            f.write(f"✗ Erros: {stats['erros']}\n")
            f.write(f"Duração: {duracao:.2f}s\n")
            f.write(f"Taxa: {total/duracao:.2f}/s\n")

    await pool.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Importar processos TJRJ PJE Autenticado")
    parser.add_argument("--test", action="store_true", help="Testar com 1 processo apenas")
    parser.add_argument("--parallel", type=int, metavar="N", help="Importar todos com N requisições paralelas")

    args = parser.parse_args()

    if args.test:
        asyncio.run(test_one_processo())
    elif args.parallel:
        asyncio.run(import_all_parallel(max_concurrent=args.parallel))
    else:
        parser.print_help()
        print("\nExemplos:")
        print("  python import_tjrj_pje_auth.py --test")
        print("  python import_tjrj_pje_auth.py --parallel 30")


if __name__ == "__main__":
    main()
