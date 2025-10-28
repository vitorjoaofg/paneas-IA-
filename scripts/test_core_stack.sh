#!/usr/bin/env bash
# Smoke test for the core stack (LLM completions + ASR endpoints).

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-token_abc123}"
ASR_FILE="${ASR_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/test-data/audio/sample4_8s.wav}"
STREAM_TIMEOUT="${STREAM_TIMEOUT:-30}"
HEALTH_RETRIES="${HEALTH_RETRIES:-36}"
HEALTH_DELAY="${HEALTH_DELAY:-5}"

AUTH_HEADER="Authorization: Bearer ${API_TOKEN}"
CONTENT_JSON_HEADER="Content-Type: application/json"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

info() { printf '▸ %s\n' "$*"; }
ok() { printf '  ✔ %s\n' "$*"; }
fail() { printf '  ✖ %s\n' "$1" >&2; exit 1; }

wait_for_health() {
    local url="${API_BASE%/}/api/v1/health"
    info "Esperando API ficar saudável em $url"
    for ((i=1; i<=HEALTH_RETRIES; i++)); do
        local status
        status=$(curl -s -o "$TMP_DIR/health.json" -w "%{http_code}" \
            -H "$AUTH_HEADER" "$url" || true)
        if [[ "$status" == "200" ]]; then
            ok "API saudável (tentativa $i)"
            return 0
        fi
        sleep "$HEALTH_DELAY"
    done
    cat "$TMP_DIR/health.json" >&2 || true
    fail "API não respondeu com 200 após $((HEALTH_RETRIES * HEALTH_DELAY))s"
}

run_chat_completion() {
    local payload_file="$TMP_DIR/chat.json"
    cat <<'JSON' >"$payload_file"
{
  "model": "qwen2.5-14b-instruct",
  "temperature": 0.3,
  "max_tokens": 200,
  "messages": [
    {"role": "system", "content": "Você é um assistente cordial."},
    {"role": "user", "content": "Explique em uma frase curta o que é transcrição automática."}
  ]
}
JSON
    info "Testando chat completions (modo síncrono)"
    local status
    status=$(curl -sS -o "$TMP_DIR/chat_response.json" -w "%{http_code}" \
        -H "$AUTH_HEADER" \
        -H "$CONTENT_JSON_HEADER" \
        -d @"$payload_file" \
        "${API_BASE%/}/api/v1/chat/completions")
    if [[ "$status" != "200" ]]; then
        cat "$TMP_DIR/chat_response.json" >&2 || true
        fail "Chat completions retornou HTTP $status"
    fi
    grep -q '"choices"' "$TMP_DIR/chat_response.json" || fail "Resposta de chat sem campo choices"
    ok "Chat completions ok"
}

run_chat_stream() {
    local payload_file="$TMP_DIR/chat_stream.json"
    cat <<'JSON' >"$payload_file"
{
  "model": "qwen2.5-14b-instruct",
  "temperature": 0.3,
  "stream": true,
  "max_tokens": 200,
  "messages": [
    {"role": "system", "content": "Você é um assistente cordial."},
    {"role": "user", "content": "Resuma em poucas palavras o objetivo do core stack."}
  ]
}
JSON
    info "Testando chat completions (stream SSE)"
    local headers_file="$TMP_DIR/chat_stream_headers.txt"
    local body_file="$TMP_DIR/chat_stream_body.txt"
    if ! curl -sS -N \
        --max-time "$STREAM_TIMEOUT" \
        -D "$headers_file" \
        -o "$body_file" \
        -H "$AUTH_HEADER" \
        -H "$CONTENT_JSON_HEADER" \
        -d @"$payload_file" \
        "${API_BASE%/}/api/v1/chat/completions"; then
        cat "$headers_file" >&2 || true
        cat "$body_file" >&2 || true
        fail "Chat stream falhou"
    fi
    grep -Eq '^HTTP/.* 200' "$headers_file" || fail "Chat stream sem HTTP 200"
    grep -q '\[DONE\]' "$body_file" || fail "Chat stream sem marcador [DONE]"
    ok "Chat stream ok"
}

run_batch_asr() {
    if [[ ! -f "$ASR_FILE" ]]; then
        fail "Arquivo de áudio não encontrado: $ASR_FILE"
    fi
    info "Testando transcrição batch (/api/v1/asr)"
    local status
    status=$(curl -sS -o "$TMP_DIR/asr_response.json" -w "%{http_code}" \
        -H "$AUTH_HEADER" \
        -F "file=@${ASR_FILE}" \
        -F "language=pt" \
        "${API_BASE%/}/api/v1/asr")
    if [[ "$status" != "200" ]]; then
        cat "$TMP_DIR/asr_response.json" >&2 || true
        fail "ASR retornou HTTP $status"
    fi
    grep -q '"text"' "$TMP_DIR/asr_response.json" || fail "Resposta de ASR sem campo text"
    ok "Transcrição batch ok"
}

main() {
    command -v curl >/dev/null 2>&1 || fail "curl é necessário"
    wait_for_health
    run_chat_completion
    run_chat_stream
    run_batch_asr
    info "Todos os testes essenciais concluídos com sucesso."
}

main "$@"
