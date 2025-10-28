# Especificação de API

Todas as rotas ficam sob `/api/v1`, exigem `Authorization: Bearer <token>` e são protegidas por middleware de rate limiting.

## Health
`GET /api/v1/health`

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://localhost:8000/api/v1/health
```

> ℹ️ Para ambientes com GPU limitada, você pode subir apenas os serviços essenciais (postgres, redis, minio, ASR e LLM FP16) executando `./scripts/start_core_stack.sh core`. Após subir o core stack, valide o gateway com `./scripts/test_core_stack.sh`, que cobre chat completions (incluindo `stream=true`) e o endpoint de transcrição batch.

```json
{
  "status": "healthy",
  "timestamp": "2024-07-28T12:35:40.812345",
  "version": "1.3.0",
  "services": {
    "redis": {"status": "up", "latency_ms": 4},
    "asr": {"status": "up", "latency_ms": 220}
  }
}
```

## ASR
`POST /api/v1/asr`

Entrada: upload `multipart/form-data` com `file=@audio.wav` e parâmetros opcionais (`language`, `model`, `enable_diarization`, `enable_alignment`, `compute_type`, `vad_filter`, `vad_threshold`, `beam_size`, `provider`). Use `provider=openai` para encaminhar a transcrição via OpenAI em vez do pool interno (padrão `paneas`).

Modelos suportados:
- `whisper/medium` (padrão; INT8/FP16 híbrido, indicado para produção)
- `whisper/small` (uso opcional em cenários de baixa latência)
- `whisper/large-v3-turbo` (alta fidelidade; exige FP16)

```bash
curl -X POST http://localhost:8000/api/v1/asr \
  -H "Authorization: Bearer $API_TOKEN" \
  -F "file=@test-data/audio/sample_10s.wav" \
  -F "language=pt" \
  -F "enable_diarization=true"
```

```json
{
  "request_id": "5e5c4c18-4d5b-4ce3-9e75-2f40cc1423f4",
  "duration_seconds": 9.8,
  "processing_time_ms": 1520,
  "language": "pt",
  "text": "olá mundo mascarado",
  "segments": [
    {"start": 0.0, "end": 4.8, "text": "olá mundo", "speaker": "SPEAKER_00"}
  ],
  "metadata": {"model": "whisper/medium", "compute_type": "int8_float16", "gpu_id": 0}
}
```

> Nota: as requisições HTTP síncronas reutilizam o modelo do evento final (`whisper/medium` por padrão).

## ASR Streaming (WebSocket)
`WS /api/v1/asr/stream`

O endpoint opera em **modo batch**: cada sessão acumula áudio por um período configurável, processa o lote com `whisper/medium` e envia o resultado para o pipeline de insights. O operador recebe metadados e os insights resumidos, em vez da transcrição palavra a palavra.

### Configuração de Performance

**Valores Otimizados (Produção):**
- `batch_window_sec: 2.0` - Latência média de ~2.3s com 90-95% de qualidade
- `beam_size: 5` - Qualidade máxima de beam search
- `best_of: 1` - Otimizado para latência

**Alternativas:**
- **Máxima Qualidade**: `batch_window_sec: 5.0, beam_size: 5, best_of: 3` (~5.1s latência, 100% qualidade)
- **Ultra Responsivo**: `batch_window_sec: 1.5, beam_size: 5, best_of: 1` (~1.8s latência, 85-90% qualidade)

Ver [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) para detalhes de tuning.

### Fluxo de Conexão

1. Conecte-se com header `Authorization: Bearer <token>` (ou query `?token=`).
2. Envie `{"event":"start","sample_rate":16000,"encoding":"pcm16","language":"pt"}`. Campos opcionais:
   - `model` / `compute_type`: modelo Whisper usado por lote (default `whisper/medium` + `int8_float16`);
   - `batch_window_sec`: janela alvo em segundos (default `2.0`, otimizado para real-time);
   - `max_batch_window_sec`: tempo máximo antes de forçar processamento (default `10.0`);
   - `beam_size`: tamanho do beam search (default `5`, range 1-10);
   - `enable_diarization`: ativa diarização por lote (default `false`).
   - `provider`: backend de ASR (`paneas` padrão, `openai` para usar a API da OpenAI para transcrição);
   - `insight_provider`: backend para geração de insights (`paneas` padrão, `openai` para roteamento via OpenAI);
   - `insight_model` / `insight_openai_model`: sobrescrevem o modelo lógico e o modelo físico usado quando necessário.
   - `enable_insights`: quando `false`, o gateway não registra a sessão no `insight_manager` (default `true`).
3. Envie `{"event":"audio","chunk":"<base64>"}` com áudio PCM16 16 kHz.
4. Finalize com `{"event":"stop"}` para processar o último lote e encerrar.

Respostas típicas:

```json
{"event":"ready","session_id":"2a01fcb6-3ce6-4f4f-9ceb-93f7b6b44a6c","mode":"batch"}
{"event":"session_started","session_id":"2a01fcb6-3ce6-4f4f-9ceb-93f7b6b44a6c","mode":"batch","batch_window_sec":2.0,"insights_enabled":true}
{"event":"batch_processed","session_id":"2a01fcb6-3ce6-4f4f-9ceb-93f7b6b44a6c","batch_index":1,"duration_sec":2.0,"transcript_chars":428,"tokens":112,"total_tokens":112,"text":"Trecho reconhecido do lote atual.","transcript":"Transcrição acumulada até o momento.","model":"whisper/medium","diarization":false}
{"event":"insight","type":"live_summary","text":"Cliente reclama de cobrança duplicada; ofereça revisão da fatura e abertura de contestação.","confidence":0.7,"model":"qwen2.5-14b-instruct-awq"}
{"event":"final_summary","session_id":"2a01fcb6-3ce6-4f4f-9ceb-93f7b6b44a6c","stats":{"total_batches":5.0,"total_audio_seconds":14.9,"total_tokens":92.0,"transcript":"Transcrição completa da sessão."}}
{"event":"session_ended","session_id":"2a01fcb6-3ce6-4f4f-9ceb-93f7b6b44a6c"}
```

Eventos relevantes:

- `batch_processed`: confirma que um lote foi transcrito, incluindo o texto do lote (`text`), a transcrição acumulada (`transcript`) e contadores de tokens (`tokens` por lote, `total_tokens` acumulado).
- `insight`: insight em tempo (quase) real emitido pelo `insight_manager`.
- `final_summary`: resumo agregado da chamada (lotes, duração, contagem de tokens e transcrição final).
- `session_ended`: fechamento definitivo da sessão.

> Para evitar perda de insights quando a chamada é encerrada, o gateway aguarda até `INSIGHT_FLUSH_TIMEOUT` (60 s por padrão) para escoar jobs pendentes antes de fechar o WebSocket. Clientes que desejam encerrar imediatamente podem aguardar explicitamente o último `event=insight` ou aumentar esse timeout na aplicação.

Referências:
- Cliente de exemplo: `scripts/streaming/asr_stream_client.py`
- Stress test: `scripts/loadtest/asr_insight_stress.py --batch-window-sec 5 --max-batch-window-sec 10`

## Align & Diarize
`POST /api/v1/align_diarize`

Recebe uma transcrição pré-existente e referência do áudio; retorna 202 com o job criado.

```bash
curl -X POST http://localhost:8000/api/v1/align_diarize \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "transcript_id": "5e5c4c18-4d5b-4ce3-9e75-2f40cc1423f4",
        "transcript": {"segments": []},
        "audio_uri": "s3://recordings/call.wav",
        "enable_alignment": true,
        "enable_diarization": true
      }'
```

```json
{"job_id": "6a9fb654-b9ce-4ae7-8ae8-9f0a67b6dcfb", "status": "queued"}
```

## OCR
`POST /api/v1/ocr`

Suporta PDFs e imagens. Parâmetros: `languages` (JSON ou CSV), `output_format`, `use_gpu`, `deskew`, `denoise`.

```bash
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Authorization: Bearer $API_TOKEN" \
  -F "file=@test-data/documents/sample_5pages.pdf" \
  -F "languages=pt,en" \
  -F "output_format=json"
```

```json
{
  "request_id": "8a460ad1-0f7a-4ba3-97c2-9c0ed2f8e6ab",
  "pages": [
    {
      "page_num": 1,
      "text": "Primeiro parágrafo...",
      "blocks": [
        {"bbox": [32, 70, 540, 120], "text": "Primeiro parágrafo...", "confidence": 0.98}
      ],
      "metadata": {"processing_time_ms": 430, "engine": "paddle-ocr-trt"}
    }
  ]
}
```

## TTS
`POST /api/v1/tts`

Entrada JSON (`text`, `language`, opcional `speaker_reference`, `format`). A resposta é áudio binário; use `--output` para salvar e leia cabeçalhos `X-Request-ID`, `X-Audio-Sample-Rate`.

```bash
curl -X POST http://localhost:8000/api/v1/tts \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Olá, este é um teste.", "language": "pt"}' \
  --output saida.wav -D -
```

Cabeçalhos de exemplo:

```
HTTP/1.1 200 OK
X-Request-ID: 9f1c9d5a-3a72-4090-9d1a-e4c2f8f1b6af
X-Audio-Sample-Rate: 22050
X-Audio-Duration: 2.7
Content-Type: audio/wav
```

## Chat Completions
`POST /api/v1/chat/completions`

Compatível com o formato OpenAI; o roteador interno usa por padrão o modelo corporativo `paneas-v1` (alias para Qwen2.5-14B INT4). Se necessário, especifique explicitamente `paneas-v1`, `qwen2.5-14b-instruct-awq` (INT4) ou `qwen2.5-14b-instruct` (FP16).

Modelos disponíveis:
- `qwen2.5-14b-instruct` (alta qualidade, FP16, GPUs 2-3)
- `qwen2.5-14b-instruct-awq` (alias temporário que usa o servidor FP16; para ativar o serviço quantizado, subir o profile `int4`)
- `llama-3.1-8b-instruct*` (apelidos legados que redirecionam para o Qwen2.5 correspondente)

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "qwen2.5-14b-instruct",
        "messages": [{"role": "user", "content": "Resuma em uma frase o objetivo da plataforma."}],
        "max_tokens": 128,
        "quality_priority": "balanced"
      }'
```

```json
{
  "id": "chatcmpl-1f84f7c0f0a14e18",
  "model": "qwen2.5-14b-instruct",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "A plataforma entrega serviços de IA on-premises unificando ASR, OCR, LLM e TTS."},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 23, "completion_tokens": 24, "total_tokens": 47}
}
```

## Speech Analytics
`POST /api/v1/analytics/speech` cria um job assíncrono; `GET /api/v1/analytics/speech/{job_id}` retorna o resultado quando finalizado.

```bash
curl -X POST http://localhost:8000/api/v1/analytics/speech \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "call_id": "b56d0a24-677d-4d59-84de-1e2fd6c0c978",
        "audio_uri": "s3://audio/call.wav",
        "transcript_uri": "s3://artifacts/call.json",
        "analysis_types": [
          "vad_advanced",
          "sentiment",
          "emotion",
          "intent",
          "outcome",
          "compliance",
          "summary",
          "keywords"
        ],
        "keywords": ["internet", "cancelamento", "upgrade"]
      }'
```

```json
{"job_id": "ae12b74c-1ef7-4cb6-a9ac-60b1f3b162b8", "status": "processing"}
```

Consulta:

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://localhost:8000/api/v1/analytics/speech/ae12b74c-1ef7-4cb6-a9ac-60b1f3b162b8
```

```json
{
  "job_id": "ae12b74c-1ef7-4cb6-a9ac-60b1f3b162b8",
  "status": "completed",
  "results": {
    "keywords": {
      "searched": ["internet", "cancelamento", "upgrade"],
      "occurrences": {"internet": 2},
      "positions": {"internet": 18.6}
    },
    "acoustic": {
      "duration_seconds": 312.7,
      "speech_ratio": 0.64,
      "speech_rate_wpm": 118.5,
      "average_pitch_hz": 198.4,
      "speaker_activity": {
        "SPEAKER_00": {"total_seconds": 176.3, "turns": 41},
        "SPEAKER_01": {"total_seconds": 136.4, "turns": 37}
      }
    },
    "sentiment": {
      "overall": {
        "label": "positive",
        "score": 0.48,
        "total_tokens": 812,
        "probabilities": {"positive": 0.59, "neutral": 0.36, "negative": 0.05}
      },
      "per_speaker": {
        "SPEAKER_00": {
          "label": "positive",
          "scores": {"positive": 0.63, "neutral": 0.32, "negative": 0.05},
          "score": 0.58,
          "tokens": 436,
          "positive_terms": 28,
          "negative_terms": 8
        },
        "SPEAKER_01": {
          "label": "neutral",
          "scores": {"positive": 0.52, "neutral": 0.42, "negative": 0.06},
          "score": 0.46,
          "tokens": 376,
          "positive_terms": 14,
          "negative_terms": 11
        }
      }
    },
    "emotion": {
      "overall": {"label": "calm", "confidence": 0.61},
      "per_speaker": {
        "SPEAKER_00": {"label": "motivated", "score": 0.74, "scores": {"motivated": 0.74, "calm": 0.19, "frustrated": 0.07}},
        "SPEAKER_01": {"label": "calm", "score": 0.68, "scores": {"calm": 0.68, "motivated": 0.21, "frustrated": 0.11}}
      }
    },
    "intent": {
      "intents": {
        "venda": {"score": 0.97, "evidence": ["oferta", "contratar"]},
        "upgrade": {"score": 0.82, "evidence": ["plano melhor", "aumentar velocidade"]},
        "cancelamento": {"score": 0.18, "evidence": []},
        "suporte": {"score": 0.33, "evidence": ["problema"]}
      },
      "outcome": {"label": "accepted", "score": 0.89, "evidence": ["aceito", "vamos fechar"]}
    },
    "compliance": {
      "passed": ["greeting", "operator_identification", "offer_presented"],
      "failed": ["call_closure"],
      "score": 0.75,
      "details": [
        {"name": "greeting", "score": 0.91, "passed": true, "evidence": ["ola"]},
        {"name": "operator_identification", "score": 0.88, "passed": true, "evidence": ["sou da claro"]},
        {"name": "offer_presented", "score": 0.94, "passed": true, "evidence": ["fibra", "globoplay"]},
        {"name": "call_closure", "score": 0.31, "passed": false, "evidence": []}
      ]
    },
    "summary": {
      "summary": [
        "Cliente avaliou migrar para o combo fibra + Globoplay destacando custo-benefício.",
        "Operador reforçou vantagens de manter o número atual e ampliou franquia de dados móveis.",
        "Conversa encerrou com aceite condicionado ao envio do contrato para assinatura."
      ],
      "next_actions": ["Enviar contrato digital", "Registrar aceite no CRM", "Agendar instalação"],
      "confidence": 0.78
    },
    "timeline": [
      {"timestamp": 18.6, "type": "keyword", "label": "internet", "confidence": 0.6, "metadata": {"keyword": "internet"}},
      {"timestamp": 182.4, "type": "intent", "label": "venda", "confidence": 0.97, "metadata": {"score": 0.97, "evidence": ["contratar"]}},
      {"timestamp": 289.1, "type": "outcome", "label": "accepted", "confidence": 0.89, "metadata": {"score": 0.89, "evidence": ["aceito"]}}
    ]
  }
}
```

`analysis_types` controla quais módulos executam. Disponíveis:

| Flag             | Descrição                                                                 |
|------------------|---------------------------------------------------------------------------|
| `vad_advanced`   | Métricas acústicas (duração, relação fala/silêncio, taxa de fala, pitch e distribuição por speaker). |
| `sentiment`      | Polaridade geral e por participante (léxicos PT/ES).                      |
| `emotion`        | Categoria emocional inferida a partir do sentimento e da dinâmica de fala.|
| `intent`         | Intenções detectadas (venda, suporte, cancelamento, upgrade, downgrade).  |
| `outcome`        | Resultado da negociação (`accepted`, `rejected`, `pending`).              |
| `keywords`       | Busca de termos fornecidos pelo cliente com timestamps quando possível.   |
| `compliance`     | Checklist de script (saudação, identificação, oferta, encerramento).      |
| `summary`        | Resumo estruturado + próximos passos gerado pelo modelo `paneas-v1`.      |

> Pré-requisito: o áudio e a transcrição precisam estar acessíveis (MinIO ou caminho local).

## Métricas Prometheus
`GET /metrics` (sem autenticação, exposto pela instância FastAPI através do `prometheus_fastapi_instrumentator`).

```bash
curl http://localhost:8000/metrics | head
```
