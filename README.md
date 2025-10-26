# AI Stack Platform

Plataforma completa de IA on-premises com ASR, Diarização, OCR, LLM e TTS otimizada para 4 GPUs NVIDIA Turing.

## Características

- **ASR**: Pipeline em lotes (5–10 s) operando `whisper/medium` em todas as GPUs; `whisper/small` permanece disponível como fallback HTTP
- **Diarização**: Pyannote 3.x com cache de embeddings (GPU1)
- **Alinhamento**: WhisperX word-level alignment (GPU1)
- **LLM**: LLaMA-3.1-8B (FP16 e INT4/AWQ) com vLLM (GPU2-3)
- **OCR**: PaddleOCR com TensorRT (GPU2)
- **TTS**: Coqui XTTS-v2 com voice cloning (GPU0)
- **Analytics**: Speech analytics D+1 (GPU1)
- **Observabilidade**: Prometheus, Grafana, Loki, Tempo

## Requisitos

- Ubuntu 22.04
- 4x NVIDIA RTX 6000/8000 (Turing)
- Docker 24+ com NVIDIA Container Runtime
- 128GB+ RAM
- 500GB+ SSD para modelos

## Quick Start

### 1. Clonar e Configurar

```bash
git clone <repo>
cd ai-stack-platform
cp .env.example .env
# Editar .env com suas credenciais
```

### 2. Bootstrap de Modelos

**IMPORTANTE**: O servidor já tem modelos em `/srv/models`. O script verifica o que existe e baixa apenas o que falta.

```bash
make bootstrap
# Verifica modelos existentes em /srv/models
# Baixa apenas modelos ausentes (~0-30GB dependendo do que já existe)
# Tempo estimado: 5-30 minutos (depende de quantos modelos precisam ser baixados)
```

O script de bootstrap:
- Verifica cada modelo em `/srv/models`
- Reusa modelos já baixados
- Baixa apenas o que está faltando
- Valida integridade dos modelos existentes
- Gera TensorRT engines para OCR
- Cria `manifest.json` com status de cada modelo

Saída esperada:

```
=== Checking existing models in /srv/models ===

[1/8] Checking Whisper large-v3...
✓ Whisper large-v3 already exists at /srv/models/whisper/large-v3

[2/11] Checking Whisper large-v3-turbo...
✓ Whisper large-v3-turbo already exists at /srv/models/whisper/large-v3-turbo

[3/11] Checking Whisper medium (INT8-capable)...
✗ Whisper medium not found, will download...
Downloading Whisper medium...

[4/11] Checking Pyannote models...
✓ Pyannote Diarization 3.1 already exists at /srv/models/pyannote/speaker-diarization-3.1

...

=== Verifying model integrity ===
✓ OK: whisper-large-v3
✓ OK: whisper-large-v3-turbo
✓ OK: whisper-medium
✓ OK: pyannote-diarization
✓ OK: llama-fp16
✓ OK: llama-int4
✓ OK: xtts
✓ OK: paddleocr-det
✓ OK: bge-m3

=== Bootstrap Complete ===
Summary:
whisper-large-v3: present
whisper-large-v3-turbo: present
whisper-medium: present
pyannote-diarization: present
llama-fp16: present
llama-int4: present
xtts: present
paddleocr: present
bge-m3: present
```

### 3. Iniciar Stack

```bash
make up
# Aguarde ~2 minutos para todos os serviços ficarem prontos
```

### 4. Verificar Saúde

```bash
make health
make smoke-test
```

## Acessos

- **API**: http://localhost:8000
- **Grafana**: http://localhost:3000 (admin/senha_do_.env)
- **Flower**: http://localhost:5555 (apenas rede interna)
- **Prometheus**: http://localhost:9090

## Uso da API

### ASR Simples

```bash
curl -X POST http://localhost:8000/api/v1/asr \
  -H "Authorization: Bearer token_abc123" \
  -F "file=@audio.wav" \
  -F "language=pt" \
  -F "model=whisper/medium"
```

### ASR com Diarização

```bash
curl -X POST http://localhost:8000/api/v1/asr \
  -H "Authorization: Bearer token_abc123" \
  -F "file=@conversation.wav" \
  -F "enable_diarization=true" \
  -F "enable_alignment=true"
```

### OCR

```bash
curl -X POST http://localhost:8000/api/v1/ocr \
  -H "Authorization: Bearer token_abc123" \
  -F "file=@document.pdf" \
  -F "languages=pt,en"
```

### LLM Chat

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer token_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-14b-instruct",
    "messages": [
      {"role": "user", "content": "Olá!"}
    ]
  }'
```

## Arquitetura ASR em Lotes

- O serviço `stack-asr` segue atuando como load balancer (NGINX) escutando na porta 9000 e distribuindo sessões por hash de `session_affinity`.
- GPUs 0 e 1 concentram a transcrição em lotes com `whisper/medium:int8_float16` (8 réplicas cada); GPUs 2 e 3 permanecem livres para o LLM (`llm-fp16`/`llm-int4`), mantendo apenas listeners HTTP para fallback.
- O gateway WebSocket armazena o áudio bruto por sessão, converte o lote para WAV e chama o `/transcribe` síncrono; os eventos expostos ao operador são `batch_processed`, `final_summary`, `session_ended` e `insight`.
- Configure o tamanho da janela com `batch_window_sec`/`max_batch_window_sec` no evento `start`. Valores padrão (5s / 10s) sustentam 500+ sessões simultâneas mantendo latência de ~3 s por lote.
- `make logs-asr` exibe os logs do balanceador; use `docker compose logs asr-worker-gpuX` para investigar um worker específico.
- O gateway de API acrescenta automaticamente `session_affinity=<uuid>` ao conectar com o balanceador; clientes que se conectarem diretamente ao `stack-asr` devem enviar esse parâmetro para manter a sessão no mesmo worker.

> ℹ️  O alias `paneas-v1` aponta para o serviço INT4 (`llm-int4`); use-o como modelo padrão ao chamar o LLM. O FP16 continua disponível apenas sob demanda. Use `--post-audio-wait` nos testes de carga para manter o WebSocket aberto até que os insights cheguem antes do encerramento da chamada.

### TTS

```bash
curl -X POST http://localhost:8000/api/v1/tts \
  -H "Authorization: Bearer token_abc123" \
  -H "Content-Type: application/json" \
  -d '{"text": "Olá mundo", "language": "pt"}' \
  -o output.wav
```

## Testes de Carga

```bash
# K6
make load-test

# Locust
make load-test-locust
```

## Monitoramento

Acesse Grafana (http://localhost:3000) e visualize:

1. **GPU Overview**: Utilização, temperatura, memória
2. **LLM Performance**: Throughput, latência, filas
3. **ASR Pipeline**: RTF, latência por modelo
4. **OCR Processing**: Pages/min, engine usage
5. **API Gateway**: Status codes, rate limits

## Troubleshooting

Ver [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Licença

Ver [LICENSE](LICENSE)
