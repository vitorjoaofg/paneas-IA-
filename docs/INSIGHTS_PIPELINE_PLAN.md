# Plano De Pipeline De Insights Em Tempo Real

## Objetivo
Gerar insights acionáveis para operadores durante chamadas ao vivo processando áudio em janelas de 5–10 segundos. A resposta deve chegar em até ~2 s após o fechamento de cada lote, privilegiando precisão em português/espanhol.

- Operador conecta no `WS /api/v1/asr/stream` com `tenant_id` e `conversation_id`.
- Gateway bufferiza o áudio cru por sessão (PCM16), consolida lotes de 5–10 s e envia o bloco para o serviço ASR síncrono (`/transcribe`).
- Um worker de insights consome a fila, decide se há contexto suficiente e chama o modelo LLM adequado.
- O resultado retorna ao operador via evento WebSocket `{"event":"insight", ...}` e é persistido para auditoria.

## Gatilhos E Buffer
- Janela deslizante por sessão com últimos N segundos de fala “limpa” (remoção de fillers e PII).
- Disparo mínimo: 120 tokens ou 20 s desde o último insight **e** mudança de tópico ou palavra-chave (ex.: cancelamento, reclamação, promessa de pagamento).
- Tipos de insight previstos: resumo parcial, próximos passos sugeridos, alerta de risco/compliance, oportunidades de upsell.

## LLM E Prompting
- Servir Qwen2-14B Instruct (FP16 e AWQ) via vLLM. Selecionar:
  - INT4 para respostas rápidas (<1s) em prompts curtos.
  - FP16 para pedidos críticos com maior confiança.
- Prompts específicos por insight, com instruções: “Se faltar informação, responda `Sem dados suficientes`”. Respostas sempre estruturadas (`type`, `message`, `confidence`).
- Adotar dicionário de termos do call center para normalizar a transcrição antes do prompt.

## Componentes Técnicos
1. **Collector** (FastAPI): mantém buffers, aplica throttling e publica payloads compactos na fila.
2. **Insight Worker** (Celery/async worker dedicado): lê lote, calcula heurísticas, chama LLM, valida saída (regex/score), grava no storage (Postgres/Redis).
3. **Emitter**: publica no WS existente um novo evento.

### Estado Atual (Out/2025)
- Coletor de áudio implementado em `services.asr_batch.SessionState`: mantém buffer PCM16, aplica `max_buffer_sec` e agenda flush a cada `batch_window_sec`.
- Cada flush converte o PCM para WAV em memória e chama o ASR síncrono (`/transcribe`) com `whisper/medium` (INT8/FP16). O texto concatenado alimenta o `InsightSession`.
- Fila assíncrona por sessão (`asyncio.Queue`) garante processamento sequencial e controla backpressure; métricas `batch_processed` e `final_summary` são emitidas pelo gateway.
- `insight_manager` permanece responsável por throttling (tokens mínimos + intervalo), agendamento (fila interna) e emissão de `event: insight`; a configuração atual usa `min_tokens=10`, `min_interval_sec=10`, `retain_tokens=60` e 32 workers HTTP apontando para o modelo corporativo `paneas-v1` (Qwen2.5-14B INT4).
- Ao receber `stop`, o gateway aguarda até `INSIGHT_FLUSH_TIMEOUT` (60 s) para escoar jobs pendentes antes de fechar o WebSocket, evitando perdas quando o LLM responde com atraso.
- Integração opcional com Celery (`INSIGHT_USE_CELERY=true`) continua disponível para offload de jobs de LLM.
- Os workers de ASR (`asr-worker-gpu0..3`) rodam variantes `whisper/medium` em cada GPU; `whisper/small` fica disponível apenas para requisições HTTP explícitas. O NGINX `stack-asr` distribui as sessões conforme `session_affinity`.

## Observabilidade E Controle
- Métricas: tempo transcrição→insight, taxa de acerto (feedback do operador), volume por tenant, erros do LLM, além dos novos gauges/histogramas (`insight_queue_size`, `insight_job_wait_seconds`, `insight_job_duration_seconds`, `insight_job_failures_total`).
- Circuit breaker: limitar insights a 1/20s por sessão + max 5 simultâneos por tenant.
- Log estruturado com `conversation_id` e `insight_type`.
- Dashboards recomendados: painel LLM (latência, tokens/s), painel ASR streaming (`asr_stream_*`), health `api/v1/health` com destaque para alias `llm_int4` opcional.

## Teste De Carga
- Script `scripts/loadtest/asr_insight_stress.py` gera N sessões WebSocket com áudio real, valida `event=session_ended` e, opcionalmente, a presença de `event=insight`, medindo latências de conclusão.
- Targets: `make loadtest-insights` (50 sessões por padrão, configurável com `SESSIONS`, `RAMP`, `AUDIO`) e `make loadtest-insights-max` (500 sessões com presets agressivos).
- Variáveis relevantes: `API_TOKEN`, `CHUNK_MS`, `BATCH_WINDOW_SEC`, `MAX_BATCH_WINDOW_SEC`, `INSIGHT_WORKER_CONCURRENCY`, `INSIGHT_QUEUE_MAXSIZE`, `INSIGHT_USE_CELERY`.
- Monitorar durante o teste: `insight_queue_size`, `insight_job_wait_seconds`, `insight_job_duration_seconds`, `insight_job_failures_total`, métricas `batch_processed`/`final_summary` e utilização de GPU/CPU.
- Referência atual: `python3 scripts/loadtest/asr_insight_stress.py --sessions 100 --audio test-data/audio/sample4_8s.wav --batch-window-sec 5 --max-batch-window-sec 10 --post-audio-wait 10 --expect-insight --require-final` → sucesso 100/100 (latência p95 de conclusão ~48 s, insights p95 ~48 s, aguardando flush antes do encerramento).

## Próximos Passos
1. Definir esquema de fila e storage temporário.
2. Implementar Collector + Worker com testes de carga.
3. Criar prompts e validações de saída.
4. Ajustar dashboard Grafana (latência e confiabilidade).
5. Planejar fine-tuning/LoRA para Qwen com dados internos.

## Fine-tuning LoRA (Plano)
- Objetivo: adaptar Qwen2.5-14B aos diálogos de call center PT/ES para gerar insights precisos.
- Dados necessários:
  - Áudio transcrito via ASR + diarização (30–60 s por trecho).
  - Anotações manualmente validadas de insights (resumo, alerta, sugestão) por tipo de situação.
  - Glossário, políticas de linguagem e scripts do call center para ground truth.
- Volume mínimo recomendado:
  - PoC: 3–5k trechos (~80–120h de diálogo útil).
  - Produção inicial: 20–30k trechos (~500h).
  - Alta precisão: 100k+ trechos com 2–3 insights por chamada.
- Pipeline de preparação:
  1. Transcrever, higienizar (remover PII) e segmentar diálogos.
  2. Selecionar subtrechos relevantes e construir prompts no formato final.
  3. Rotular insights (humano + revisão). Formato JSONL com `prompt`, `response`, `metadata`.
  4. Separar treino/validação/teste estratificados por tenant, idioma e tipo de insight.
- Treinamento:
  - Usar PEFT/LoRA sobre Qwen2.5-14B (FP16 ou INT4), com mesmo template de prompt que será usado na produção.
  - Métricas: ROUGE/L, recall de alertas, avaliação manual.
- Iteração contínua:
  - Recolher feedback dos operadores, reanotar casos problemáticos e atualizar o LoRA periodicamente.
