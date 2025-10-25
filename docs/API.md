# Especificação de API

Todas as rotas ficam sob `/api/v1`, exigem `Authorization: Bearer <token>` e são protegidas por middleware de rate limiting.

## Health
`GET /api/v1/health`

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://localhost:8000/api/v1/health
```

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

Entrada: upload `multipart/form-data` com `file=@audio.wav` e parâmetros opcionais (`language`, `model`, `enable_diarization`, `enable_alignment`, `compute_type`, `vad_filter`, `vad_threshold`, `beam_size`).

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
  "metadata": {"model": "large-v3-turbo", "compute_type": "fp16", "gpu_id": 0}
}
```

## ASR Streaming (WebSocket)
`WS /api/v1/asr/stream`

Fluxo:

1. Conecte-se com header `Authorization: Bearer <token>` ou query `?token=`.
2. Envie `{"event":"start","sample_rate":16000,"encoding":"pcm16","language":"pt"}`.
3. Envie múltiplos `{"event":"audio","chunk":"<base64>"}` com áudio PCM16 16 kHz.
4. Finalize com `{"event":"stop"}` para receber a transcrição final.

Exemplo:

```bash
wscat -c "ws://localhost:8000/api/v1/asr/stream?token=$API_TOKEN"
```

Respostas típicas:

```json
{"event":"ready","session_id":"cc31a9fd-2d64-4975-bda9-3344dc64a95e"}
{"event":"session_started","session_id":"cc31a9fd-2d64-4975-bda9-3344dc64a95e"}
{"event":"partial","is_final":false,"text":"Olá, obrigado por ligar","segments":[{"start":0.0,"end":2.1,"text":"Olá, obrigado por ligar"}]}
{"event":"final","is_final":true,"text":"Olá, obrigado por ligar para a central.","segments":[{"start":0.0,"end":2.6,"text":"Olá, obrigado por ligar para a central."}]}
{"event":"session_ended","session_id":"cc31a9fd-2d64-4975-bda9-3344dc64a95e"}
{"event":"insight","type":"live_summary","text":"Cliente solicita renegociação. Reforce condições especiais.","confidence":0.7,"model":"qwen2.5-14b-instruct-awq"}
```

Para um cliente completo em Python, consulte `scripts/streaming/asr_stream_client.py`.

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

Compatível com o formato OpenAI; o roteador interno escolhe FP16 ou INT4 com base no contexto, mas você pode forçar o modelo passando `qwen2.5-14b-instruct` (FP16) ou `qwen2.5-14b-instruct-awq` (INT4).

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
- `POST /api/v1/analytics/speech`: cria job assíncrono.
- `GET /api/v1/analytics/speech/{job_id}`: consulta progresso/resultado.

```bash
curl -X POST http://localhost:8000/api/v1/analytics/speech \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "call_id": "b56d0a24-677d-4d59-84de-1e2fd6c0c978",
        "audio_uri": "s3://recordings/call.wav",
        "transcript_uri": "s3://transcripts/call.json",
        "analysis_types": ["sentiment", "compliance"],
        "keywords": ["cancelamento", "upgrade"]
      }'
```

```json
{"job_id": "ae12b74c-1ef7-4cb6-a9ac-60b1f3b162b8", "status": "queued"}
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
  "results": {"sentiment": {"score": 0.72}, "compliance": {"breaches": 0}}
}
```

## Métricas Prometheus
`GET /metrics` (sem autenticação, exposto pela instância FastAPI através do `prometheus_fastapi_instrumentator`).

```bash
curl http://localhost:8000/metrics | head
```
