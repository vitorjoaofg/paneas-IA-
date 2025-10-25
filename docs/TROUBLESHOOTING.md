# Troubleshooting

## Serviços não sobem
- Verificar `docker compose ps` e logs específicos (`make logs-api`, `make logs-llm`).
- Conferir se `/srv/models` está montado com permissões de leitura para UID/GID do container.

## Latência ASR acima da meta
- Checar métricas `asr_real_time_factor` no dashboard ASR/TTS.
- Confirmar que GPU0 não está compartilhada com processos externos.
- Ajustar `ASR_BATCH_SIZE` no `.env` e reiniciar serviço.

## LLaMA retornando erro de memória
- Garante que apenas instâncias llm-fp16/int4 utilizam GPUs 2 e 3.
- Reduzir `--max-num-seqs` ou `GPU_MEMORY_FRACTION` no `.env`.

## OCR usando fallback CPU
- Validar que script de bootstrap gerou engines TensorRT em `/srv/models/paddleocr/engines`.
- Conferir logs do container `stack-ocr` para erros do TensorRT.

## Diarização indisponível
- Certificar que `HF_TOKEN` foi configurado antes de rodar bootstrap.
- Validar presença de modelos em `/srv/models/pyannote`.

## Falhas na observabilidade
- Prometheus indisponível: conferir se `infra/prometheus/prometheus.yml` inclui endpoints corretos.
- Grafana sem dashboards: verificar provisioning em `/etc/grafana/provisioning` dentro do container.
- Loki sem logs: conferir permissões de leitura em `/var/lib/docker/containers`.

## Problemas de autenticação
- Garantir que header `Authorization` está presente (Bearer token).
- Tokens são lidos de `API_TOKENS` no `.env`; reiniciar API após mudanças.

## Limite de requisições
- HTTP 429 indica rate limit; inspecionar headers `X-RateLimit-*`.
- Ajustar valores no `.env` ou aplicar roteamento alternativo via Celery quando possível.
