# Plano De Pipeline De Insights Em Tempo Real

## Objetivo
Gerar insights acionáveis para operadores durante chamadas ao vivo reutilizando a transcrição de streaming. A resposta deve chegar em até ~2 s após o gatilho, privilegiando precisão em português/espanhol.

## Fluxo De Alto Nível
- Operador conecta no `WS /api/v1/asr/stream` com `tenant_id` e `conversation_id`.
- Gateway agrega segmentos (texto, speaker, confiança, timestamps) e envia lotes para uma fila baixa-latência (Redis Stream ou Kafka) por sessão.
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
- Collector incorporado em `InsightSession` com buffer deslizante e mascaramento de PII.
- Fila assíncrona interna (`asyncio.Queue`) no API Gateway limita jobs simultâneos (tamanho configurável, padrão 200) e aciona até 2 workers concorrentes.
- Cada worker reusa `services.llm_client.chat_completion` com timeout implícito do HTTPX, reaproveitando o roteamento Qwen FP16/AWQ.
- Após publicar `event: insight`, a sessão reavalia automaticamente se há contexto extra acumulado para novo disparo sem depender de novo áudio.
- Integração opcional com Celery (`INSIGHT_USE_CELERY=true`) envia o job para workers dedicados (`stack-celery-worker`) mantendo backpressure e respeitando `insights.generate` queue.
- Pipeline de ASR streaming agora mantém janelas incrementais (contexto deslizante de ~2,5 s), processa apenas o delta de áudio e aceita parametrização de modelo/compute por sessão (`whisper/medium` como padrão `int8_float16`; `whisper/large-v3-turbo` para alta fidelidade em FP16).
- Sessões longas (~38 min) estabelecidas: 10 canais simultâneos completam sem falhas; 20 canais alcançam 95% de sucesso com latência ~15 min por chamada (restante expira por timeout do cliente — ajustar thresholds antes de subir a carga).

## Observabilidade E Controle
- Métricas: tempo transcrição→insight, taxa de acerto (feedback do operador), volume por tenant, erros do LLM, além dos novos gauges/histogramas (`insight_queue_size`, `insight_job_wait_seconds`, `insight_job_duration_seconds`, `insight_job_failures_total`).
- Circuit breaker: limitar insights a 1/20s por sessão + max 5 simultâneos por tenant.
- Log estruturado com `conversation_id` e `insight_type`.
- Dashboards recomendados: painel LLM (latência, tokens/s), painel ASR streaming (`asr_stream_*`), health `api/v1/health` com destaque para alias `llm_int4` opcional.

## Teste De Carga
- Script `scripts/loadtest/asr_insight_stress.py` gera N sessões WebSocket com áudio real, valida `event=final` e `event=insight` e mede latências.
- Targets: `make loadtest-insights` (50 sessões por padrão, configurável com `SESSIONS`, `RAMP`, `AUDIO`) e `make loadtest-insights-max` (500 sessões, utiliza o target anterior com predefinições pesadas).
- Variáveis relevantes: `API_TOKEN`, `CHUNK_MS`, `INSIGHT_WORKER_CONCURRENCY`, `INSIGHT_QUEUE_MAXSIZE`, `INSIGHT_USE_CELERY`.
- Monitorar durante o teste: `insight_queue_size`, `insight_job_wait_seconds`, `insight_job_duration_seconds`, `insight_job_failures_total`, latência média do ASR (`processing_time_ms`) e utilização de GPU/CPU.
- Referência atual: `python3 scripts/loadtest/asr_insight_stress.py --sessions 10 --model whisper/medium --compute-type int8_float16` → sucesso 10/10 (latência p95 ~8 min); `--sessions 20` requer timeout ≥ 900 s e ainda gera 1/20 expirado — priorizar otimizações antes de aumentar o fanout.

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
