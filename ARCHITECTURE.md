# Paneas AI Stack - Arquitetura Completa

## Visão Geral do Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INTERNET / USUÁRIOS                                │
│                     https://jota.ngrok.app (ngrok tunnel)                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                          REVERSE PROXY & LOAD BALANCER                        │
│                                                                               │
│  ┌─────────────────┐                                                         │
│  │  Caddy Proxy    │  :80, :443                                             │
│  │  (stack-caddy)  │  SSL/TLS, HTTP/2, Routing                              │
│  └────────┬────────┘                                                         │
│           │                                                                   │
└───────────┼───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                             API GATEWAY (FastAPI)                             │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  stack-api (:8000)                                                   │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  Middlewares:                                                 │   │   │
│  │  │  • CORS (allow all origins)                                  │   │   │
│  │  │  • Request ID                                                │   │   │
│  │  │  • Logging (structured logs)                                 │   │   │
│  │  │  • Authentication (Bearer token)                             │   │   │
│  │  │  • Rate Limiting                                             │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                      │   │
│  │  Routers:                                                            │   │
│  │  • /api/v1/asr         - Transcrição batch                          │   │
│  │  • /api/v1/asr/stream  - Transcrição em tempo real (WebSocket)      │   │
│  │  • /api/v1/ocr         - OCR de imagens/PDFs                        │   │
│  │  • /api/v1/tts         - Text-to-Speech                             │   │
│  │  • /api/v1/chat/completions - Chat com LLM (OpenAI-compatible)      │   │
│  │  • /api/v1/align       - Alinhamento de áudio                       │   │
│  │  • /api/v1/analytics   - Analytics e métricas                       │   │
│  │  • /                   - Frontend estático (React/Vue)              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└─────┬─────────┬──────────┬──────────┬───────────┬──────────┬─────────────────┘
      │         │          │          │           │          │
      │         │          │          │           │          │
      ▼         ▼          ▼          ▼           ▼          ▼
┌─────────┐ ┌──────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐
│   ASR   │ │ LLM  │ │   OCR   │ │   TTS   │ │ Redis  │ │PostgreSQL│
│ Service │ │ APIs │ │ Service │ │ Service │ │        │ │          │
└─────────┘ └──────┘ └─────────┘ └─────────┘ └────────┘ └──────────┘
```

---

## GPU Allocation - 4x Quadro RTX 6000 (23GB VRAM cada)

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         GPU 0 (Quadro RTX 6000)                           │
│                         VRAM: 7.5 GB / 23 GB                              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  stack-asr-gpu0 - Whisper Medium (INT8/FP16)                        │ │
│  │  • Transcrição de áudio em tempo real                               │ │
│  │  • Weight: 3 (load balancing)                                       │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                         GPU 1 (Quadro RTX 6000)                           │
│                         VRAM: 7.6 GB / 23 GB                              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  stack-asr-gpu1 - Whisper Medium (INT8/FP16)                        │ │
│  │  • Transcrição de áudio em tempo real                               │ │
│  │  • Weight: 3 (load balancing)                                       │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                         GPU 2 (Quadro RTX 6000)                           │
│                         VRAM: 19.5 GB / 23 GB                             │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  stack-asr-gpu2 - Whisper Medium (INT8/FP16)                        │ │
│  │  • Transcrição de áudio em tempo real                               │ │
│  │  • Weight: 3 (load balancing)                                       │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  stack-llm-int4 - Qwen2.5-32B INT4-AWQ (:8002)                      │ │
│  │  • LLM para chat e insights                                         │ │
│  │  • Modelo: paneas-q32b                                              │ │
│  │  • Quantização: INT4 AWQ (~12GB VRAM)                               │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                         GPU 3 (Quadro RTX 6000)                           │
│                         VRAM: 21.1 GB / 23 GB                             │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  stack-asr-gpu3 - Whisper Medium (INT8/FP16)                        │ │
│  │  • Transcrição de áudio em tempo real                               │ │
│  │  • Weight: 3 (load balancing)                                       │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  stack-llm-fp16 - Qwen2.5-14B FP16 (:8001)                          │ │
│  │  • LLM de backup/insights                                           │ │
│  │  • Modelo: paneas-v1-q14b                                           │ │
│  │  • Precisão: FP16 (~21GB VRAM)                                      │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## ASR Service - Load Balancing com Nginx

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    stack-asr (Nginx Load Balancer)                      │
│                              Port: 9000                                 │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Configuração:                                                    │ │
│  │  • client_max_body_size: 50m (permite upload de arquivos grandes)│ │
│  │  • proxy_read_timeout: 3600s                                      │ │
│  │  • proxy_send_timeout: 3600s                                      │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Upstream HTTP (least_conn):                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ asr-gpu0:9000│  │ asr-gpu1:9000│  │ asr-gpu2:9000│  │asr-gpu3:9k│ │
│  │  weight: 3   │  │  weight: 3   │  │  weight: 3   │  │ weight: 3 │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                                         │
│  Upstream WebSocket (hash $arg_session_affinity):                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ asr-gpu0:9000│  │ asr-gpu1:9000│  │ asr-gpu2:9000│  │asr-gpu3:9k│ │
│  │  weight: 3   │  │  weight: 3   │  │  weight: 3   │  │ weight: 3 │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                                         │
│  Endpoints:                                                            │
│  • POST /transcribe     → HTTP load balancing (batch ASR)             │
│  • WS   /stream         → WebSocket with session affinity             │
│  • GET  /health         → Health check                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## LLM Router - Modelo Híbrido

```
┌──────────────────────────────────────────────────────────────────────┐
│                          LLM Router Logic                            │
│                     (api/services/llm_router.py)                     │
│                                                                      │
│  Estratégia: Qualidade/Custo/Latência                               │
│                                                                      │
│  Modelos Disponíveis:                                               │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  paneas-q32b                                                   │ │
│  │  • Target: INT4 (GPU 2)                                        │ │
│  │  • Endpoint: http://llm-int4:8002                              │ │
│  │  • Modelo: Qwen2.5-32B INT4-AWQ                                │ │
│  │  • Uso: Chat, insights, tool calling                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  paneas-v1-q14b                                                │ │
│  │  • Target: FP16 (GPU 3)                                        │ │
│  │  • Endpoint: http://llm-fp16:8001                              │ │
│  │  • Modelo: Qwen2.5-14B FP16                                    │ │
│  │  • Uso: Fallback, insights rápidos                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  gpt-4o-mini (OpenAI)                                          │ │
│  │  • Target: OPENAI                                              │ │
│  │  • Endpoint: https://api.openai.com/v1                         │ │
│  │  • Uso: Fallback externo, alta qualidade                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Roteamento Automático:                                             │
│  • prompt_tokens < 2000 → INT4 (rápido)                            │
│  • prompt_tokens < 8000 → FP16 (balanceado)                        │
│  • prompt_tokens > 8000 → OpenAI (externo)                         │
│  • context_length > 32k → Rejeitar (limite do sistema)             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Serviços de Suporte

### Armazenamento e Cache

```
┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐
│   Redis (:6379)      │  │  PostgreSQL (:5432)  │  │ MinIO (:9000)   │
│  (stack-redis)       │  │  (stack-postgres)    │  │ (stack-minio)   │
├──────────────────────┤  ├──────────────────────┤  ├─────────────────┤
│ • Session cache      │  │ • Metadata DB        │  │ • Object store  │
│ • Rate limiting      │  │ • User data          │  │ • Audio files   │
│ • Celery broker      │  │ • Analytics          │  │ • Uploads       │
│ • Pub/Sub messaging  │  │ • Audit logs         │  │ • Backups       │
└──────────────────────┘  └──────────────────────┘  └─────────────────┘
```

### Background Jobs (Celery)

```
┌───────────────────────────────────────────────────────────────────────┐
│                    Celery Distributed Task Queue                      │
│  ┌─────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ stack-celery-worker │  │  stack-celery-beat (Scheduler)       │  │
│  │                     │  │                                       │  │
│  │ • Insight jobs      │  │  • Periodic tasks                    │  │
│  │ • Batch processing  │  │  • Cleanup jobs                      │  │
│  │ • Email/webhooks    │  │  • Health checks                     │  │
│  └─────────────────────┘  └──────────────────────────────────────┘  │
│                                                                       │
│  Monitoring:                                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  stack-flower (:5555) - Web UI para Celery                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Observability Stack

### Métricas (Prometheus + Grafana)

```
┌───────────────────────────────────────────────────────────────────────┐
│                    Prometheus Time Series Database                    │
│                         (stack-prometheus)                            │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Exporters coletando métricas:                                  │ │
│  │  • dcgm-exporter (:9400)     - NVIDIA GPU metrics               │ │
│  │  • redis-exporter            - Redis performance                │ │
│  │  • postgres-exporter         - PostgreSQL stats                 │ │
│  │  • /metrics (API)            - FastAPI application metrics      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Alerting:                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  stack-alertmanager (:9093) - Alertas e notificações           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    Grafana Dashboards (:3000)                         │
│                         (stack-grafana)                               │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Dashboards:                                                     │ │
│  │  • GPU Utilization (DCGM)                                       │ │
│  │  • API Performance                                              │ │
│  │  • LLM Metrics (tokens/s, latency)                              │ │
│  │  • ASR throughput                                               │ │
│  │  • System health                                                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### Logs (Loki + Promtail)

```
┌───────────────────────────────────────────────────────────────────────┐
│                    Promtail (Log Collector)                           │
│                      (stack-promtail)                                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Coleta logs de:                                                 │ │
│  │  • Docker containers (via /var/lib/docker)                      │ │
│  │  • Structured logs (JSON)                                       │ │
│  │  • Application logs                                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    Loki Log Aggregation (:3100)                       │
│                         (stack-loki)                                  │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  • Armazena logs estruturados                                   │ │
│  │  • Indexação por labels                                         │ │
│  │  • LogQL queries                                                │ │
│  │  • Integração com Grafana                                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### Tracing (Tempo + OpenTelemetry)

```
┌───────────────────────────────────────────────────────────────────────┐
│                OpenTelemetry Collector (:4318)                        │
│                    (stack-otel-collector)                             │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Receivers:                                                      │ │
│  │  • OTLP gRPC (:4317)                                            │ │
│  │  • OTLP HTTP (:4318)                                            │ │
│  │                                                                  │ │
│  │  Exporters:                                                      │ │
│  │  • Tempo (traces)                                               │ │
│  │  • Prometheus (metrics)                                         │ │
│  │  • Loki (logs)                                                  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    Tempo Tracing Backend                              │
│                        (stack-tempo)                                  │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  • Distributed tracing                                          │ │
│  │  • Request flow tracking                                        │ │
│  │  • Performance analysis                                         │ │
│  │  • Integração com Grafana                                       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Fluxo de Dados - Transcrição em Tempo Real

```
1. Usuário → Frontend (Browser)
      │
      ▼
2. WebSocket Connection
      │
      ws://jota.ngrok.app/api/v1/asr/stream
      │
      ▼
3. API Gateway (stack-api)
      │
      │ Envia evento "start" com config
      │ { language: "pt", enable_insights: true, ... }
      │
      ▼
4. ASR Load Balancer (stack-asr nginx)
      │
      │ Hash-based routing (session affinity)
      │
      ▼
5. ASR Worker (stack-asr-gpu[0-3])
      │
      │ Recebe chunks de áudio PCM16 16kHz
      │ Buffer de 2-10 segundos
      │
      ▼
6. Whisper Model (GPU)
      │
      │ Transcrição com timestamps
      │ Segmentação automática
      │
      ▼
7. Eventos retornam via WebSocket
      │
      ├─→ batch_processed: { text, tokens, duration }
      │
      ├─→ insight: { type, text, generated_at }
      │        │
      │        └─→ Celery Worker → LLM (stack-llm-int4)
      │
      └─→ final_summary: { transcript, stats }
```

---

## Fluxo de Dados - Chat com LLM

```
1. Frontend → POST /api/v1/chat/completions
      │
      │ { model: "paneas-q32b", messages: [...], stream: true }
      │
      ▼
2. API Gateway (stack-api)
      │
      ├─→ Middleware: Auth, Rate Limit
      ├─→ Router: llm.py
      │
      ▼
3. LLM Router decide o target
      │
      ├─→ Análise de contexto
      ├─→ Contagem de tokens
      └─→ Escolhe modelo adequado
      │
      ▼
4. Forward para modelo selecionado
      │
      ├─→ stack-llm-int4 (GPU 2) - Qwen2.5-32B INT4
      │   • Tools/function calling
      │   • Context: 32k tokens
      │   • Speed: ~30 tokens/s
      │
      ├─→ stack-llm-fp16 (GPU 3) - Qwen2.5-14B FP16
      │   • Insights rápidos
      │   • Context: 32k tokens
      │   • Speed: ~50 tokens/s
      │
      └─→ OpenAI API (externo)
          • Fallback de alta qualidade
          • Context: 128k tokens
      │
      ▼
5. Streaming Response (SSE)
      │
      │ data: {"choices":[{"delta":{"content":"texto"}}]}
      │
      ▼
6. Frontend renderiza incrementalmente
```

---

## Recursos Computacionais Totais

```
CPU:
  • Não especificado (provavelmente multi-core Xeon)

RAM:
  • Não especificado (estimado: 128-256 GB)

GPU:
  ┌────────────────────────────────────────────────────┐
  │ 4x NVIDIA Quadro RTX 6000                          │
  │ • VRAM total: 92 GB                                │
  │ • VRAM em uso: ~56 GB (61%)                        │
  │ • CUDA Cores: 4,608 por GPU = 18,432 total         │
  │ • Tensor Cores: 576 por GPU = 2,304 total          │
  │ • RT Cores: 72 por GPU = 288 total                 │
  └────────────────────────────────────────────────────┘

Storage:
  • Docker volumes (local SSD/HDD)
  • MinIO object storage
  • PostgreSQL database

Network:
  • Docker network: stack-network
  • Exposed ports: 80, 443, 3000, 5555, 8000, 9093
  • Ngrok tunnel: jota.ngrok.app
```

---

## Segurança e Autenticação

```
┌───────────────────────────────────────────────────────────────────┐
│                        Security Layers                            │
│                                                                   │
│  1. Reverse Proxy (Caddy)                                        │
│     • SSL/TLS termination                                        │
│     • HTTP → HTTPS redirect                                      │
│                                                                   │
│  2. API Gateway Auth Middleware                                  │
│     • Bearer token authentication                                │
│     • Token validation: API_TOKENS env var                       │
│     • Excluded paths: /health, /metrics, /api/v1/asr/stream     │
│                                                                   │
│  3. Rate Limiting                                                │
│     • Global: 1000 req/min                                       │
│     • ASR: rate_limit_asr                                        │
│     • OCR: rate_limit_ocr                                        │
│     • Per-IP tracking via Redis                                  │
│                                                                   │
│  4. CORS                                                         │
│     • Allow origins: * (development)                             │
│     • Allow credentials: true                                    │
│     • Allow methods: *                                           │
│     • Allow headers: *                                           │
│                                                                   │
│  5. Frontend Password Protection                                 │
│     • Password: Paneas@321                                       │
│     • Stored in localStorage after unlock                        │
└───────────────────────────────────────────────────────────────────┘
```

---

## Capacidade e Performance

### ASR (Whisper Medium)

```
Capacidade por worker:
  • ~4x tempo real (1 min áudio → 15s processamento)
  • Concurrent sessions: ~10-15 por worker
  • Total capacity: 40-60 sessions simultâneas

Latência:
  • Batch mode: 2-5 segundos para áudio de 1 min
  • Streaming mode: 500ms - 2s (buffer de 2-10s)

Throughput:
  • ~240-360 minutos de áudio/minuto (total)
```

### LLM (Qwen2.5)

```
INT4 (32B):
  • Speed: ~30 tokens/s
  • Context: 32k tokens
  • VRAM: ~12 GB
  • Concurrent requests: 2-3

FP16 (14B):
  • Speed: ~50 tokens/s
  • Context: 32k tokens
  • VRAM: ~21 GB
  • Concurrent requests: 1-2

Total LLM capacity:
  • ~4-5 requests simultâneas
  • ~100-150 tokens/s agregado
```

---

## Endpoints Principais

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/asr` | POST | Transcrição batch (arquivo) |
| `/api/v1/asr/stream` | WS | Transcrição em tempo real |
| `/api/v1/ocr` | POST | OCR de imagens/PDFs |
| `/api/v1/tts` | POST | Text-to-Speech |
| `/api/v1/chat/completions` | POST | Chat LLM (OpenAI-compatible) |
| `/api/v1/align` | POST | Alinhamento áudio-texto |
| `/api/v1/analytics` | GET | Métricas e analytics |
| `/metrics` | GET | Prometheus metrics |
| `/` | GET | Frontend estático |

---

## Variáveis de Ambiente Principais

```bash
# API
API_TOKENS=token_abc123,token_xyz789
ENV=production
LOG_LEVEL=info
STACK_VERSION=1.0.0

# LLM
LLM_INT4_HOST=llm-int4
LLM_INT4_PORT=8002
LLM_FP16_HOST=llm-fp16
LLM_FP16_PORT=8001
LLM_TIMEOUT=300.0
LLM_ROUTING_STRATEGY=quality

# OpenAI (fallback)
OPENAI_API_KEY=sk-...
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_INSIGHTS_MODEL=gpt-4o-mini

# Database
POSTGRES_HOST=postgres
POSTGRES_DB=paneas_db
POSTGRES_USER=paneas
POSTGRES_PASSWORD=***

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=***
MINIO_ROOT_PASSWORD=***

# Rate Limiting
RATE_LIMIT_GLOBAL=1000
RATE_LIMIT_ASR=100
RATE_LIMIT_OCR=50

# Telemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

---

## Manutenção e Operação

### Comandos Úteis

```bash
# Ver status de todos os containers
docker-compose ps

# Ver logs em tempo real
docker-compose logs -f api

# Reiniciar serviço específico
docker-compose restart asr

# Ver uso de GPU
nvidia-smi

# Rebuild e restart
docker-compose build api && docker-compose up -d api

# Ver métricas do Prometheus
curl http://localhost:9090/api/v1/query?query=up

# Acessar Grafana
open http://localhost:3000

# Ver fila do Celery
open http://localhost:5555
```

### Health Checks

Todos os serviços principais têm health checks configurados:

- ASR workers: `GET http://asr-worker-gpu0:9000/health`
- LLM INT4: `GET http://llm-int4:8002/health`
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`
- MinIO: `curl http://minio:9000/minio/health/live`

---

**Última atualização:** 2025-10-31
**Versão da Stack:** 1.0.0
