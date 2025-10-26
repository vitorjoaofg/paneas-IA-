# Matriz de Versões e Modelos

Resumo das versões, modelos e requisitos do cluster da AI Stack Platform.

## Hardware e Drivers Validados
- Ubuntu 22.04 com `docker compose` ≥ 2.20 e `nvidia-container-toolkit`.
- 4× NVIDIA RTX 6000/8000 (24 GB).
- Drivers ≥ 525.60.13 (CUDA 12.1) e volumes `/srv/models`, `/srv/data`, `/srv/minio`, `/var/lib/postgresql/data` com permissão de escrita.

## Alocação de GPUs
| GPU | Serviços | Observações |
| --- | --- | --- |
| 0 | `asr-worker-gpu0`, `tts` | 8 réplicas `whisper/medium:int8_float16` dedicadas ao batch ASR; XTTS divide a GPU. |
| 1 | `asr-worker-gpu1`, `align`, `diar`, `analytics` | 8 réplicas `whisper/medium:int8_float16`, com alinhamento/diarização compartilhando a placa (requer `HF_TOKEN`). |
| 2 | `asr-worker-gpu2`, `ocr`, `llm-fp16`, `llm-int4` | Sem réplicas ASR locais; GPU fica dedicada ao OCR e aos modelos vLLM. |
| 3 | `asr-worker-gpu3`, `llm-fp16`, `llm-int4` | Sem réplicas ASR (somente listeners HTTP), liberando totalmente a placa para o vLLM FP16. |
| 0-3 | `dcgm-exporter` | Coleta métricas. |

## Modelos Necessários (`make bootstrap`)
| Componente | Modelo | Origem HF | Destino |
| --- | --- | --- | --- |
| ASR | Whisper medium (lotes principais), Whisper small (fallback HTTP), large-v3-turbo (opcional) | `Systran/faster-whisper-*` | `/srv/models/whisper/*` |
| Alinhamento | Whisper large-v3-turbo | Idem ASR | `/srv/models/whisper/large-v3-turbo` |
| Diarização | Speaker-Diarization 3.1, Segmentation 3.0 | `pyannote/*` (precisa `HF_TOKEN`) | `/srv/models/pyannote/*` |
| LLM | LLaMA-3.1-8B Instruct FP16 + AWQ | `meta-llama/...`, `TheBloke/...AWQ` | `/srv/models/llama/{fp16,int4-awq}` |
| LLM (alta simultaneidade) | Qwen2.5-14B Instruct FP16 (+ alias AWQ) | `Qwen/Qwen2.5-14B-Instruct*` | `/srv/models/qwen2_5/{fp16,int4-awq}` |
| TTS | Coqui XTTS-v2 | `coqui/XTTS-v2` | `/srv/models/xtts` |
| OCR | PP-OCRv4 det/rec/cls + engines | `PaddlePaddle/*` | `/srv/models/paddleocr/{det,rec,cls,engines}` |
| Embeddings | BGE-M3 | `BAAI/bge-m3` | `/srv/models/embeddings/bge-m3` |

## Stack de Containers e Principais Dependências
- **API (`api/`)**: FastAPI 0.110.1 + Celery 5.3.6 + Redis 5.0.4; configuração em `config.py`.
- **ASR LB (`infra/asr/nginx.conf`)**: NGINX 1.25, sticky hash em `session_affinity` direcionando para `asr-worker-gpu0..3` (porta 9000).
- **ASR Workers (`asr/`)**: Faster-Whisper 1.2.0, CTranslate2 4.1.0, Torchaudio 2.2.2, cuDNN 8.9.7. Sessions são consumidas via `/transcribe` em lotes 5–10 s com `whisper/medium`; `whisper/small` permanece para requisições HTTP explícitas.
- **Align (`align/`)**: WhisperX word-level alignment com `whisper/large-v3-turbo`; roda em GPU 1.
- **Diarização (`diar/`)**: Pyannote.audio 3.1.1; cache em `/srv/data/embeddings_cache`; requer `HF_TOKEN`.
- **LLM (`llm/`)**: vLLM 0.4.2 (patch rope), torchvision 0.18.0; `shm_size=4gb`, GPUs 2-3. O servidor FP16 roda com `--gpu-memory-utilization 0.20` e o INT4 com `0.20` para liberar VRAM aos workers de ASR. Instâncias padrão servem Qwen2.5-14B FP16 (alias `*-awq` aponta temporariamente para FP16). Serviço quantizado pode ser iniciado sob demanda com `docker compose --profile int4 up -d llm-int4`. LLaMA-3.1-8B continua disponível para downloads complementares ou treinamento.
- **OCR (`ocr/`)**: PaddleOCR 2.7.3, PaddlePaddle GPU 2.5.1, ONNX Runtime GPU 1.17.1, TensorRT.
- **TTS (`tts/`)**: Coqui TTS 0.22.0, Transformers 4.39.3, MinIO 7.2.4 (`/srv/data/voices`).
- **Analytics (`analytics/`)**: Librosa 0.10.1, Celery 5.3.6; modelos em modo leitura.
- **Observabilidade (`infra/`)**: Otel Collector 0.95.0, Grafana, Prometheus, Loki 2.8.4, Tempo, dcgm-exporter 3.3.5-3.4.0.

## Checklist de Setup
1. Validar drivers com `nvidia-smi` e aplicar `sudo nvidia-ctk runtime configure`.
2. Criar `.env` (base `.env.example`) com `HF_TOKEN`, Postgres, Redis, MinIO e tokens.
3. Instalar `huggingface_hub[cli]` e rodar `make bootstrap`.
4. Subir com `make up`, checar `make health` e Grafana.
5. Se saturar, revisar `make logs-asr`, `make logs-llm` e métricas do `dcgm-exporter`.
