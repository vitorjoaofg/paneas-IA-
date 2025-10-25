.PHONY: help bootstrap up down restart logs clean test smoke-test smoke-test-stream load-test load-test-locust logs-api logs-asr logs-llm shell stats health gpu-stats

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
