#!/usr/bin/env bash
# Helper script to start either the entire stack or a reduced core subset
# focused on LLM completions and transcription (batch + streaming).

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: start_core_stack.sh <mode>

Modes:
  core    Start only the services required for API, LLM completions,
          batch ASR, and streaming insights.
  full    Start the full platform (equivalent to `docker compose up -d`).

Environment:
  COMPOSE_CMD  Optional override for the docker compose command (default: "docker compose").

Examples:
  ./scripts/start_core_stack.sh core
  ./scripts/start_core_stack.sh full
EOF
}

if [[ $# -ne 1 ]]; then
    usage
    exit 1
fi

MODE="$1"
COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

if ! command -v ${COMPOSE_CMD%% *} >/dev/null 2>&1; then
    echo "Error: docker compose is required." >&2
    exit 1
fi

case "$MODE" in
    core)
        # Start only the essentials:
        # - postgres, redis, minio: API dependencies
        # - asr (includes workers via depends_on) for batch + streaming ASR
        # - llm-fp16: LLM completions backend
        # - api: FastAPI gateway exposing the endpoints
        echo "Starting core services (postgres, redis, minio, asr stack, llm-fp16, api)..."
        $COMPOSE_CMD up -d postgres redis minio asr llm-fp16 api
        ;;
    full)
        echo "Starting full stack..."
        $COMPOSE_CMD up -d
        ;;
    *)
        echo "Unknown mode: $MODE" >&2
        usage
        exit 1
        ;;
esac
