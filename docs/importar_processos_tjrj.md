# Importar `processos_completos.json` para o banco de dados

Este procedimento carrega os processos do TJRJ exportados pelo scraper (arquivo `processos_completos.json` na raiz do repositório) para a tabela `processos.processos_judiciais` do Postgres. Use-o sempre que receber um novo dump.

## Pré-requisitos

- Containers do stack rodando (`docker compose up -d`), em especial `stack-postgres` e `stack-api`.
- Variáveis do banco já configuradas em `.env` (POSTGRES\_*).
- Arquivo `processos_completos.json` atualizado no diretório raiz do repositório.

## Passo a passo

1. **Executar o importador**

   ```bash
   POSTGRES_HOST=localhost PYTHONPATH=api python3 - <<'PY'
   import asyncio, json
   from copy import deepcopy
   from pathlib import Path

   from services import processos_db
   from services.db_client import close_db_pool

   BASE_URL = "https://www3.tjrj.jus.br/consultaprocessual/"
   DATA_PATH = Path("processos_completos.json")

   def normalize_record(raw: dict) -> dict:
       data = deepcopy(raw)
       detalhes = data.get("detalhesPublicos") or {}
       info = detalhes.get("informacoes") or {}

       numero = data.get("numero") or info.get("Número Processo")
       if not numero:
           raise ValueError("Registro sem número de processo")

       data["numeroProcesso"] = numero
       data["uf"] = data.get("uf") or "RJ"
       data["classe"] = data.get("classe") or data.get("classeJudicial") or info.get("Classe Judicial")
       data["assunto"] = data.get("assunto") or info.get("Assunto")
       data["comarca"] = data.get("comarca") or info.get("Jurisdição")
       data["vara"] = data.get("vara") or data.get("orgaoJulgador") or info.get("Órgão Julgador")
       data["dataDistribuicao"] = data.get("dataDistribuicao") or info.get("Data da Distribuição") or data.get("dataAutuacao")
       data["situacao"] = data.get("situacao") or data.get("localizacao") or data.get("ultimaMovimentacao")
       data["linkPublico"] = data.get("linkPublico") or f"{BASE_URL}#/processo/{numero}"

       advs = data.get("advogados")
       if advs is None:
           data["advogados"] = []
       elif isinstance(advs, str):
           data["advogados"] = [advs]
       elif isinstance(advs, list):
           data["advogados"] = advs
       else:
           data["advogados"] = [str(advs)]

       movimentos = detalhes.get("movimentacoes") or data.get("movimentos") or []
       data["movimentos"] = [
           {"data": str(m.get("data", "")), "descricao": str(m.get("descricao", ""))}
           if isinstance(m, dict) else {"data": "", "descricao": str(m)}
           for m in movimentos
       ]

       data.setdefault("audiencias", [])
       data.setdefault("publicacoes", [])
       data.setdefault("documentos", [])
       data.setdefault("partes", [])

       return data

   async def main():
       processos = json.loads(DATA_PATH.read_text(encoding="utf-8"))
       inseridos = 0
       for idx, raw in enumerate(processos, start=1):
           try:
               payload = normalize_record(raw)
           except Exception as exc:
               print(f"[WARN] Ignorando registro {idx}: {exc}")
               continue

           await processos_db.salvar_processo(payload, tribunal="TJRJ", permitir_atualizacao=False)
           inseridos += 1
           if inseridos % 250 == 0:
               print(f"[INFO] {inseridos} processos inseridos...")

       await close_db_pool()
       print(f"[DONE] Inseridos {inseridos} processos do TJRJ")

   asyncio.run(main())
   PY
   ```

2. **Validar contagem**

   ```bash
   docker exec stack-postgres \
     psql -U aistack -d aistack \
     -c "SELECT tribunal, COUNT(*) FROM processos.processos_judiciais GROUP BY tribunal ORDER BY tribunal;"
   ```

   Esperado: `TJSP` mantém a contagem original e `TJRJ` passa a refletir o número de registros do JSON (ex.: 6300).

3. **(Opcional) conferir via API**

   ```bash
   curl -s 'http://localhost:8000/api/v1/processos?tribunal=TJRJ&page=1&per_page=5&include_dados_completos=true' \
     -H 'Authorization: Bearer token_abc123' | jq '.total'
   ```

## Observações

- O script chama `salvar_processo(..., permitir_atualizacao=False)`, então registros que já existem no banco são simplesmente ignorados (sem atualizar os dados antigos).
- Se o arquivo estiver em outro caminho, ajuste `DATA_PATH` antes de rodar.
- Para reimportar após limpar o banco (`DELETE FROM processos.processos_judiciais WHERE tribunal='TJRJ';`), basta repetir os passos acima com o novo JSON.
