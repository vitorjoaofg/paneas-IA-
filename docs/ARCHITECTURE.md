# Arquitetura da Plataforma

## Visão Geral

A plataforma é composta por serviços especializados que compartilham infraestrutura comum, orquestrados via Docker Compose e alavancando quatro GPUs NVIDIA Turing.

## Distribuição de GPUs

- **GPU0**: Serviços de tempo real (ASR Faster-Whisper, TTS Coqui XTTS-v2) com pinagem exclusiva.
- **GPU1**: WhisperX Align, Pyannote Diarization e pipeline de Speech Analytics D+1.
- **GPU2-3**: Instâncias vLLM servindo Qwen2.5-14B (FP16 e INT4/AWQ) com tensor parallelism + OCR (PaddleOCR com TensorRT).

## Estado & Mensageria

- **PostgreSQL 16** para metadados, auditoria e estado relacional.
- **Redis 7** para cache expresso, locks distribuídos e backend do Celery.
- **MinIO** como armazenamento S3-compatível para áudios, documentos e artefatos.
- **Celery** operando em pools dedicados (asr, ocr, analytics, llm) com Celery Beat para agendamentos.

## Camada de API

- **FastAPI** rodando sobre Uvicorn, expondo endpoints REST e compatíveis com OpenAI.
- Middlewares para request-id, autenticação por bearer token e rate limiting baseado em Redis.

## Observabilidade

- **OpenTelemetry Collector** consolidando métricas, logs e traces de todos os serviços.
- **Prometheus** e **Alertmanager** para métricas e alertas, agora consumindo exporters dedicados (Redis/Postgres) e os `/metrics` nativos de cada microserviço.
- **Grafana** com dashboards provisionados (GPU, LLM, ASR/TTS, OCR, API, Celery).
- **Loki** + **Promtail** para logs estruturados.
- **Tempo** para tracing distribuído.

## Segurança & Proxy

- **Caddy** atua como reverse proxy com restrições de acesso, CORS, autenticação básica para `/metrics` e regras de IP para Flower.
- Todos os serviços sensíveis montam `/srv/models` como read-only.
- O gateway FastAPI bloqueia inicialização em ambientes `production/staging` caso `API_TOKENS` não estejam configurados.

## Fluxo de Dados

1. Cliente envia áudio/arquivo → FastAPI valida autenticação e delega tarefa.
2. Serviço especializado (ASR, OCR, etc.) processa dados usando modelos em `/srv/models`.
3. Resultados persistidos no PostgreSQL/MinIO com auditoria em Redis/Postgres.
4. Métricas, logs e traces emitidos via OTEL para stack de observabilidade.

## Políticas de Degradação

- Roteamento dinâmico entre instâncias FP16/INT4 para balancear latência e throughput.
- ASR reduz compute_type para int8 sob alta utilização de VRAM e troca para modelo turbo se necessário.
- OCR realiza fallback automático para execução em CPU quando TensorRT indisponível ou `use_gpu=false`.
- LLM tenta o backend INT4 por padrão e alterna para FP16 diante de falhas transitórias.
- Celery aplica retires exponenciais para falhas transitórias.
