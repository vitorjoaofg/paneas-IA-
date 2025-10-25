# Especificação de API

Todas as rotas exigem autenticacão via `Authorization: Bearer <token>` e respeitam rate limiting conforme configurado.

## Health
- `GET /api/v1/health`
  - Retorna estado agregado dos serviços.

## ASR
- `POST /api/v1/asr`
  - Arquivo multipart (wav/mp3/flac/ogg).
  - Parâmetros opcionais: `language`, `model`, `enable_diarization`, `enable_alignment`, `compute_type`, `vad_filter`, `vad_threshold`.
  - Resposta inclui transcrição, segmentos, metadados de GPU.

## Align & Diarization
- `POST /api/v1/align_diarize`
  - Realiza alinhamento e diarização assíncronos sobre transcrição pré-existente.
  - Resposta 202 com `job_id`.

## OCR
- `POST /api/v1/ocr`
  - Recebe PDF ou imagem (até 100MB).
  - Opções de saída: `text`, `hocr`, `alto`, `json`.
  - `use_gpu` controla uso de TensorRT; fallback automático para CPU.

## TTS
- `POST /api/v1/tts`
  - Sintetiza áudio a partir de texto.
  - Suporta `speaker_reference` apontando para áudio pré-existente no MinIO.

## Chat Completions
- `POST /api/v1/chat/completions`
  - Compatível com API do OpenAI.
  - Roteador decide entre instâncias FP16 e INT4 quando `model` genérico é usado.

## Speech Analytics
- `POST /api/v1/analytics/speech`
  - Dispara pipeline analítico assíncrono.
  - `GET /api/v1/analytics/speech/{job_id}` recupera resultado.

## Metrics
- `GET /metrics`
  - Exposto em formato Prometheus.
