# Guia de Implantação

## Pré-requisitos

- Ubuntu 22.04 com drivers NVIDIA atualizados e `nvidia-docker2`.
- Docker 24+ e Docker Compose v2.
- Acesso a `/srv/models` com modelos previamente baixados (quando disponíveis).

## Passo a Passo

1. **Configuração**
   - Clonar repositório.
   - Copiar `.env.example` para `.env` e ajustar segredos e parâmetros.
2. **Bootstrap de Modelos**
   - Executar `make bootstrap`.
   - Script verifica `/srv/models`, reutiliza modelos existentes, baixa faltantes, valida checksums e gera manifest.
3. **Inicialização da Stack**
   - Executar `make up`.
   - Aguardar healthchecks completarem (aprox. 2 minutos).
4. **Verificações Iniciais**
   - `make health` para snapshot do estado.
   - `make smoke-test` para validar endpoints críticos e SLAs de referência.
5. **Provisionamento de Dados**
   - Criar buckets MinIO via `mc` ou console web.
   - Popular `test-data/` com amostras de áudio/PDF para testes.
6. **Acesso a Observabilidade**
   - Grafana disponível em `http://<host>:3000` (usuário admin conforme `.env`).
   - Configurar alertas adicionais no Alertmanager conforme políticas internas.

## Atualizações

- Para aplicar atualizações, puxar novos commits, executar `docker compose pull` (se usar imagens públicas) e reiniciar com `make restart`.
- Sempre revisar `manifest.json` após qualquer alteração nos modelos.

## Backup & Recuperação

- PostgreSQL: volumes persistidos em `/var/lib/postgresql/data` (garantir snapshots regulares).
- MinIO: dados em `/srv/minio`.
- Grafana, Loki, Tempo, Alertmanager: diretórios persistentes em `/srv/data/*` (incluídos no backup).
