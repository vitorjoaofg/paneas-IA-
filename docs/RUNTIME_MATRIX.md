# Matriz de Versões e Modelos

Resumo das versões, modelos e requisitos do cluster da AI Stack Platform.

## Hardware e Drivers Validados
- Ubuntu 22.04 com `docker compose` ≥ 2.20 e `nvidia-container-toolkit`.
- 4× NVIDIA RTX 6000/8000 (24 GB).
- Drivers ≥ 525.60.13 (CUDA 12.1) e volumes `/srv/models`, `/srv/data`, `/srv/minio`, `/var/lib/postgresql/data` com permissão de escrita.

## Alocação de GPUs
| GPU | Serviços | Observações |
| --- | --- | --- |
| 0 | `asr`, `tts` | Whisper large-v3(-turbo) + XTTS-v2; observar fila. |
| 1 | `align`, `diar`, `analytics` | Pyannote exige `HF_TOKEN`; analytics sob demanda. |
| 2 | `ocr`, `llm-fp16`, `llm-int4` | OCR gera TensorRT; divide VRAM. |
| 3 | `llm-fp16`, `llm-int4` | Necessária para `tensor-parallel-size 2`. |
| 0-3 | `dcgm-exporter` | Coleta métricas. |

## Modelos Necessários (`make bootstrap`)
| Componente | Modelo | Origem HF | Destino |
| --- | --- | --- | --- |
| ASR | Whisper large-v3 / large-v3-turbo | `Systran/faster-whisper-*` | `/srv/models/whisper/*` |
| Alinhamento | Whisper large-v3-turbo | Idem ASR | `/srv/models/whisper/large-v3-turbo` |
| Diarização | Speaker-Diarization 3.1, Segmentation 3.0 | `pyannote/*` (precisa `HF_TOKEN`) | `/srv/models/pyannote/*` |
| LLM | LLaMA-3.1-8B Instruct FP16 + AWQ | `meta-llama/...`, `TheBloke/...AWQ` | `/srv/models/llama/{fp16,int4-awq}` |
| TTS | Coqui XTTS-v2 | `coqui/XTTS-v2` | `/srv/models/xtts` |
| OCR | PP-OCRv4 det/rec/cls + engines | `PaddlePaddle/*` | `/srv/models/paddleocr/{det,rec,cls,engines}` |
| Embeddings | BGE-M3 | `BAAI/bge-m3` | `/srv/models/embeddings/bge-m3` |

## Stack de Containers e Principais Dependências
- **API (`api/`)**: FastAPI 0.110.1 + Celery 5.3.6 + Redis 5.0.4; configuração em `config.py`.
- **ASR & Align (`asr/`, `align/`)**: Faster-Whisper 1.2.0, CTranslate2 4.1.0, Torchaudio 2.2.2, cuDNN 8.9.7.
- **Diarização (`diar/`)**: Pyannote.audio 3.1.1; cache em `/srv/data/embeddings_cache`; requer `HF_TOKEN`.
- **LLM (`llm/`)**: vLLM 0.4.2 (patch rope), torchvision 0.18.0; `shm_size=4gb`, GPUs 2-3.
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
