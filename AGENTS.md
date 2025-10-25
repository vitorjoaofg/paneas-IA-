# Repository Guidelines

Keep contributions consistent across all service tiers.

## Project Structure & Module Organization
- `api/` is the FastAPI gateway; routers live under `api/routers/`, shared DTOs in `api/schemas/`, and integrations in `api/services/` and `api/utils/`.
- Model-serving microservices sit in top-level folders (`asr/`, `tts/`, `ocr/`, `align/`, `analytics/`, `llm/`) with Dockerfiles and startup code for each GPU role.
- `infra/` holds provisioning and observability assets, `docs/` centralizes architecture notes, and `scripts/` houses bootstrap, smoke, and load tooling.
- Sample fixtures in `test-data/` back the smoke tests; avoid placing large proprietary media elsewhere in the repo.

## Build, Test, and Development Commands
- `make bootstrap` downloads or validates models in `/srv/models`; run once per host.
- `make up` / `make down` start or stop the full docker compose stack; prefer `make restart` for config changes.
- `make smoke-test` executes `scripts/smoke_tests.sh`, hitting ASR, OCR, TTS, and health endpoints with repo fixtures.
- `make load-test` runs the k6 scenarios under `scripts/k6/`; `make load-test-locust` starts the interactive Locust runner.
- `make health` and `make logs-*` quickly surface readiness and streaming logs.

## Coding Style & Naming Conventions
- Python code follows PEP 8 with 4-space indents, explicit type hints, and `snake_case` modules; mirror router names between `api/routers/` and `api/schemas/`.
- Keep configuration in `config.py` via `pydantic-settings`; document new environment keys in `.env.example`.
- Shell scripts under `scripts/` should be POSIX-friendly, `set -euo pipefail`, and log actionable status lines.

## Testing Guidelines
- Place FastAPI unit or contract tests in `api/tests/`, mirroring router modules (`test_{router}.py`) and favoring local fixtures over network calls.
- Before opening a PR, run `make smoke-test`; performance-sensitive diffs should capture baseline metrics from `make load-test`.
- Document new sample data in `test-data/` with provenance notes.

## Commit & Pull Request Guidelines
- History is sparse; use concise imperative summaries with an optional scope, e.g., `feat(api): add diarization retries`.
- Each PR should include motivation, commands run (`make smoke-test`, etc.), related issue links, and screenshots for UI or Grafana changes.
- Coordinate cross-service changes by noting required image rebuilds or migrations in the PR description.

## Security & Configuration Tips
- Keep populated `.env` files, tokens, and model artifacts out of Git; store them via the deployment process in `docs/DEPLOYMENT.md`.
- Verify new endpoints enforce `AuthMiddleware` and emit structured logs via `telemetry/`.
- When changing model assets or GPU allocation, update the relevant notes in `docs/ARCHITECTURE.md` to keep operators aligned.
