.PHONY: help bootstrap up down restart logs clean test smoke-test smoke-test-stream load-test load-test-locust loadtest-insights loadtest-insights-max logs-api logs-asr logs-llm shell stats health gpu-stats

help:
	@echo "AI Stack Platform - Available Commands:"
	@echo ""
	@echo "  make bootstrap    - Download models and prepare environment"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - Follow logs from all services"
	@echo "  make smoke-test   - Run smoke tests"
	@echo "  make smoke-test-stream - Run streaming ASR smoke test"
	@echo "  make load-test    - Run k6 load tests"
	@echo "  make loadtest-insights     - Run async load test (default 50 sessions)"
	@echo "  make loadtest-insights-max - Run async load test (500 sessions, heavy)"
	@echo "  make clean        - Clean volumes and data"
	@echo "  make shell        - Open shell in API container"
	@echo ""

bootstrap:
	@echo "Bootstrapping models..."
	chmod +x scripts/bootstrap_models.sh
	./scripts/bootstrap_models.sh

up:
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	sleep 30
	@echo "Stack is up! Access:"
	@echo "  API:     http://localhost:8000"
	@echo "  Grafana: http://localhost:3000"
	@echo "  Flower:  http://localhost:5555"

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-asr:
	docker compose logs -f asr

logs-llm:
	docker compose logs -f llm-fp16 llm-int4

smoke-test:
	chmod +x scripts/smoke_tests.sh
	./scripts/smoke_tests.sh

smoke-test-stream:
	chmod +x scripts/smoke_tests_streaming.sh
	./scripts/smoke_tests_streaming.sh

load-test:
	@echo "Running k6 load tests..."
	k6 run scripts/k6/asr_load_test.js
	k6 run scripts/k6/llm_comparison_test.js

load-test-locust:
	@echo "Starting Locust..."
	locust -f scripts/locust/mixed_pipeline.py --host=http://localhost:8000

loadtest-insights:
	@API_TOKEN=$${API_TOKEN:-token_abc123}; \
	SESS=$${SESSIONS:-50}; \
	RAMP_SECS=$${RAMP:-30}; \
	AUDIO_FILE=$${AUDIO:-test-data/audio/sample_stream.wav}; \
	CHUNK=$${CHUNK_MS:-600}; \
	POST_WAIT=$${POST_AUDIO_WAIT:-0}; \
	BATCH=$${BATCH_WINDOW_SEC:-5}; \
	MAX_BATCH=$${MAX_BATCH_WINDOW_SEC:-10}; \
	echo "Sessions=$$SESS Ramp=$$RAMP_SECS Audio=$$AUDIO_FILE ChunkMS=$$CHUNK"; \
	python3 scripts/loadtest/asr_insight_stress.py \
		--sessions $$SESS \
		--ramp $$RAMP_SECS \
		--audio $$AUDIO_FILE \
		--chunk-ms $$CHUNK \
		--token $$API_TOKEN \
		--batch-window-sec $$BATCH \
		--max-batch-window-sec $$MAX_BATCH \
		--post-audio-wait $$POST_WAIT \
		--expect-insight

loadtest-insights-max:
	@SESS_MAX=$${SESSIONS:-500}; \
	RAMP_MAX=$${RAMP:-120}; \
	AUDIO_MAX=$${AUDIO:-test-data/audio/sample_stream.wav}; \
	CHUNK_MAX=$${CHUNK_MS:-600}; \
	POST_WAIT_MAX=$${POST_AUDIO_WAIT:-0}; \
	BATCH_MAX=$${BATCH_WINDOW_SEC:-5}; \
	MAX_BATCH_MAX=$${MAX_BATCH_WINDOW_SEC:-10}; \
	make loadtest-insights SESSIONS=$$SESS_MAX RAMP=$$RAMP_MAX AUDIO=$$AUDIO_MAX CHUNK_MS=$$CHUNK_MAX BATCH_WINDOW_SEC=$$BATCH_MAX MAX_BATCH_WINDOW_SEC=$$MAX_BATCH_MAX POST_AUDIO_WAIT=$$POST_WAIT_MAX

clean:
	@echo "Cleaning up..."
	docker compose down -v
	rm -rf /srv/data/redis/*
	rm -rf /srv/data/temp/*

shell:
	docker compose exec api bash

stats:
	@echo "=== Container Stats ==="
	docker stats --no-stream

health:
	@curl -s -H "Authorization: Bearer token_abc123" http://localhost:8000/api/v1/health | jq

gpu-stats:
	@curl -s http://localhost:9400/metrics | grep DCGM_FI_DEV_GPU_UTIL
