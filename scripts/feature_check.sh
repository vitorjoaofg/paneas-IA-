#!/usr/bin/env bash
# Comprehensive feature check script.
# Runs real curl calls against the gateway, printing responses and pass/fail status.

set -euo pipefail

command -v curl >/dev/null 2>&1 || {
    echo "curl is required to run this script." >&2
    exit 1
}

JQ_BIN="${JQ_BIN:-jq}"
command -v "$JQ_BIN" >/dev/null 2>&1 || {
    echo "jq (or set JQ_BIN) is required for pretty-printing JSON responses." >&2
    exit 1
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

API_BASE="${API_BASE:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-token_abc123}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
OPENAI_INSIGHT_MODEL="${OPENAI_INSIGHT_MODEL:-}"

WS_BASE=$(printf '%s' "$API_BASE" | sed -e 's#^http://#ws://#' -e 's#^https://#wss://#')
WS_STREAM_URL="${WS_STREAM_URL:-${WS_BASE%/}/api/v1/asr/stream}"

# Use smaller fixtures from test-data when available.
ASR_FILE="${ASR_FILE:-$REPO_ROOT/test-data/audio/sample4_8s.wav}"
OCR_FILE="${OCR_FILE:-$REPO_ROOT/test-data/documents/sample1.pdf}"

LLM_MODEL="${LLM_MODEL:-paneas-v1}"
LLM_PROMPT="${LLM_PROMPT:-Olá, responda com uma frase curta.}"

RUN_LLM="${RUN_LLM:-1}"
RUN_ANALYTICS="${RUN_ANALYTICS:-1}"
RUN_ALIGN="${RUN_ALIGN:-0}"
LLM_HOST_OVERRIDE="${LLM_HOST_OVERRIDE:-llm-int4}"
RUN_STREAM="${RUN_STREAM:-1}"

cleanup_files=()
cleanup_dirs=()

STAGE_DIR="$(mktemp -d)"
cleanup_dirs+=("$STAGE_DIR")

TTS_PAYLOAD_FILE="$(mktemp)"
cleanup_files+=("$TTS_PAYLOAD_FILE")
cat <<'JSON' >"$TTS_PAYLOAD_FILE"
{
  "text": "Olá! Este é um teste rápido da API de síntese.",
  "language": "pt"
}
JSON

# Analytics optional transcript file (used when URIs are not provided).
ANALYTICS_TRANSCRIPT_FILE="$STAGE_DIR/analytics_transcript.json"
cleanup_files+=("$ANALYTICS_TRANSCRIPT_FILE")
cat <<'JSON' >"$ANALYTICS_TRANSCRIPT_FILE"
{
  "text": "Cliente reportou problemas de conexão e solicitou revisão do plano.",
  "segments": [
    {
      "start": 0.0,
      "end": 4.0,
      "text": "Cliente reportou problemas de conexão.",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 4.0,
      "end": 8.0,
      "text": "Solicitou revisão do plano e desconto.",
      "speaker": "SPEAKER_01"
    }
  ]
}
JSON

# Configurable URIs for analytics/align (default to staged assets inside containers).
analytics_audio_ext="${ASR_FILE##*.}"
ANALYTICS_AUDIO_STAGED="$STAGE_DIR/analytics_audio.${analytics_audio_ext}"
cleanup_files+=("$ANALYTICS_AUDIO_STAGED")
cp "$ASR_FILE" "$ANALYTICS_AUDIO_STAGED"

ANALYTICS_AUDIO_URI="${ANALYTICS_AUDIO_URI:-/tmp/feature-check/analytics_audio.${analytics_audio_ext}}"
ANALYTICS_TRANSCRIPT_URI="${ANALYTICS_TRANSCRIPT_URI:-/tmp/feature-check/analytics_transcript.json}"
ALIGN_AUDIO_URI="${ALIGN_AUDIO_URI:-$ANALYTICS_AUDIO_URI}"

TTS_OUTPUT_FILE="$(mktemp)"
cleanup_files+=("$TTS_OUTPUT_FILE")
trap 'rm -f "${cleanup_files[@]}" 2>/dev/null || true; rm -rf "${cleanup_dirs[@]}" 2>/dev/null || true' EXIT INT TERM

# ANSI colors for visual summary.
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BLUE="\033[1;34m"
MAGENTA="\033[1;35m"
NC="\033[0m"

TICK="${GREEN}✔${NC}"
CROSS="${RED}✖${NC}"
WARN="${YELLOW}⚠${NC}"

print_header() {
    printf "\n${BLUE}▸ %-45s${NC}\n" "$1"
}

print_command() {
    printf "${MAGENTA}%s${NC}\n" "$1"
}

print_response() {
    local body=$1 format=$2
    if [ "$format" = "json" ]; then
        if [ -s "$body" ]; then
            "$JQ_BIN" '.' "$body" || cat "$body"
        else
            echo "(empty response)"
        fi
    else
        if [ -s "$body" ]; then
            head -c 200 "$body"
            [ "$(wc -c <"$body")" -gt 200 ] && printf "\n... (truncated)\n"
        else
            echo "(empty response)"
        fi
    fi
}

copy_into_service() {
    local service=$1
    local src=$2
    local dest=$3

    local container_id
    container_id=$(docker compose ps -q "$service" 2>/dev/null || true)
    if [ -z "$container_id" ]; then
        return 1
    fi

    docker compose exec -T "$service" mkdir -p "$(dirname "$dest")" >/dev/null 2>&1 || true
    docker cp "$src" "${container_id}:${dest}" >/dev/null 2>&1
}

total_tests=0
passed_tests=0
skipped_tests=0
failed_tests=""

do_curl() {
    # Arguments: label, output_format(json|text), command...
    local label=$1
    local format=$2
    shift 2

    total_tests=$((total_tests + 1))

    print_header "$label"
    local printable="$"
    local arg
    for arg in "$@"; do
        case $arg in
            *" "*|*"\""*)
                printable="$printable \"$arg\""
                ;;
            *)
                printable="$printable $arg"
                ;;
        esac
    done
    print_command "$printable"

    local tmp_body tmp_err exit_code
    tmp_body="$(mktemp)"
    tmp_err="$(mktemp)"

    if "$@" >"$tmp_body" 2>"$tmp_err"; then
        exit_code=0
    else
        exit_code=$?
    fi

    if [ "$exit_code" -eq 0 ]; then
        print_response "$tmp_body" "$format"
        printf "%s OK\n" "$TICK"
        passed_tests=$((passed_tests + 1))
    else
        if [ -s "$tmp_body" ]; then
            print_response "$tmp_body" "$format"
        fi
        if [ -s "$tmp_err" ]; then
            printf "\n%s\n" "$(cat "$tmp_err")"
        fi
        printf "%s FAILED (exit %s)\n" "$CROSS" "$exit_code"
        failed_tests="${failed_tests}\n- ${label}"
    fi

    rm -f "$tmp_body" "$tmp_err"
    return "$exit_code"
}

run_stream_test() {
    local label=$1
    local provider=$2
    total_tests=$((total_tests + 1))
    print_header "$label"

    local tmp_output exit_code
    tmp_output="$(mktemp)"
    local cmd=(python3 "$REPO_ROOT/scripts/streaming/asr_stream_client.py"
        --url "$WS_STREAM_URL"
        --token "$API_TOKEN"
        --file "$ASR_FILE"
        --language pt
        --batch-window-sec 5
        --max-batch-window-sec 10
        --post-audio-wait "${STREAM_POST_AUDIO_WAIT:-2}"
        --provider "$provider"
        --insight-provider "$provider"
    )

    if [ "$provider" = "openai" ] && [ -n "$OPENAI_INSIGHT_MODEL" ]; then
        cmd+=(--insight-openai-model "$OPENAI_INSIGHT_MODEL")
    fi

    print_command "${cmd[*]}"
    if "${cmd[@]}" >"$tmp_output" 2>&1; then
        exit_code=0
    else
        exit_code=$?
    fi

    if [ "$exit_code" -eq 0 ] && grep -q '"event": "insight"' "$tmp_output"; then
        tail -n 10 "$tmp_output"
        printf "%s OK\n" "$TICK"
        passed_tests=$((passed_tests + 1))
    else
        tail -n 20 "$tmp_output"
        if [ "$exit_code" -ne 0 ]; then
            printf "%s FAILED (exit %s)\n" "$CROSS" "$exit_code"
        else
            printf "%s FAILED (missing insight event)\n" "$CROSS"
        fi
        failed_tests="${failed_tests}\n- ${label}"
    fi

    rm -f "$tmp_output"
}

ensure_file_exists() {
    local path=$1 description=$2
    if [ ! -f "$path" ]; then
        printf "${RED}Required %s not found at %s${NC}\n" "$description" "$path" >&2
        exit 1
    fi
}

ensure_file_exists "$ASR_FILE" "ASR sample audio"
ensure_file_exists "$OCR_FILE" "OCR sample document"

printf "${CYAN}API base:${NC} %s\n" "$API_BASE"
printf "${CYAN}Using ASR sample:${NC} %s\n" "$ASR_FILE"
printf "${CYAN}Using OCR sample:${NC} %s\n" "$OCR_FILE"
printf "${CYAN}Streaming endpoint:${NC} %s\n" "$WS_STREAM_URL"

AUTH_HEADER="Authorization: Bearer $API_TOKEN"

# Health endpoint
do_curl "Gateway Health" "json" \
    curl -sS -f -H "$AUTH_HEADER" "$API_BASE/api/v1/health"

# ASR endpoint
do_curl "ASR Transcription" "json" \
    curl -sS -H "$AUTH_HEADER" \
        -F "file=@${ASR_FILE}" \
        -F "language=pt" \
        -F "model=whisper/medium" \
        "$API_BASE/api/v1/asr"

if [ -n "$OPENAI_API_KEY" ]; then
    do_curl "ASR Transcription (OpenAI)" "json" \
        curl -sS -H "$AUTH_HEADER" \
            -F "file=@${ASR_FILE}" \
            -F "language=pt" \
            -F "model=whisper/medium" \
            -F "provider=openai" \
            "$API_BASE/api/v1/asr"
else
    print_header "ASR Transcription (OpenAI)"
    printf "%s Skipped (set OPENAI_API_KEY)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
fi

# OCR endpoint
do_curl "OCR Extraction" "json" \
    curl -sS -H "$AUTH_HEADER" \
        -F "file=@${OCR_FILE}" \
        -F 'languages=["pt"]' \
        "$API_BASE/api/v1/ocr"

# TTS endpoint (binary response)
print_header "TTS Synthesis"
print_command "$ curl -sS -H '$AUTH_HEADER' -H 'Content-Type: application/json' --data @$TTS_PAYLOAD_FILE $API_BASE/api/v1/tts --output $TTS_OUTPUT_FILE"
total_tests=$((total_tests + 1))
tts_http_status=$(curl -sS -w '%{http_code}' -o "$TTS_OUTPUT_FILE" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    --data @"$TTS_PAYLOAD_FILE" \
    "$API_BASE/api/v1/tts") || tts_http_status="000"

if [ "$tts_http_status" = "200" ] && [ -s "$TTS_OUTPUT_FILE" ]; then
    file_size=$(wc -c <"$TTS_OUTPUT_FILE")
    printf "Audio saved to %s (%s bytes)\n" "$TTS_OUTPUT_FILE" "$file_size"
    printf "%s OK\n" "$TICK"
    passed_tests=$((passed_tests + 1))
else
    printf "%s FAILED (status %s)\n" "$CROSS" "$tts_http_status"
    failed_tests="${failed_tests}\n- TTS Synthesis"
fi

# LLM endpoint
if [ "$RUN_LLM" = "1" ]; then
    LLM_PAYLOAD_FILE="$(mktemp)"
    cleanup_files+=("$LLM_PAYLOAD_FILE")
    cat <<JSON >"$LLM_PAYLOAD_FILE"
{
  "model": "$LLM_MODEL",
  "messages": [
    {"role": "user", "content": "$LLM_PROMPT"}
  ],
  "max_tokens": 64
}
JSON

    do_curl "LLM Chat Completion" "json" \
        curl -sS -f --max-time "${LLM_CURL_TIMEOUT:-15}" \
            -H "$AUTH_HEADER" -H "Content-Type: application/json" \
            --data @"$LLM_PAYLOAD_FILE" \
            "$API_BASE/api/v1/chat/completions"

    if [ -n "$OPENAI_API_KEY" ]; then
        LLM_OPENAI_PAYLOAD_FILE="$(mktemp)"
        cleanup_files+=("$LLM_OPENAI_PAYLOAD_FILE")
        cat <<JSON >"$LLM_OPENAI_PAYLOAD_FILE"
{
  "model": "$LLM_MODEL",
  "provider": "openai",
  "messages": [
    {"role": "user", "content": "$LLM_PROMPT"}
  ],
  "max_tokens": 64
}
JSON

        do_curl "LLM Chat Completion (OpenAI)" "json" \
            curl -sS -f --max-time "${LLM_CURL_TIMEOUT:-25}" \
                -H "$AUTH_HEADER" -H "Content-Type: application/json" \
                --data @"$LLM_OPENAI_PAYLOAD_FILE" \
                "$API_BASE/api/v1/chat/completions"
    else
        print_header "LLM Chat Completion (OpenAI)"
        printf "%s Skipped (set OPENAI_API_KEY)\n" "$WARN"
        skipped_tests=$((skipped_tests + 1))
    fi
else
    print_header "LLM Chat Completion"
    printf "%s Skipped (set RUN_LLM=1 to enable)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
fi

if [ "$RUN_STREAM" = "1" ]; then
    run_stream_test "Streaming Insights (paneas)" "paneas"
    if [ -n "$OPENAI_API_KEY" ]; then
        run_stream_test "Streaming Insights (OpenAI)" "openai"
    else
        print_header "Streaming Insights (OpenAI)"
        printf "%s Skipped (set OPENAI_API_KEY)\n" "$WARN"
        skipped_tests=$((skipped_tests + 1))
    fi
else
    print_header "Streaming Insights"
    printf "%s Skipped (set RUN_STREAM=1)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
fi

# Analytics optional test
if [ "$RUN_ANALYTICS" = "1" ]; then
  analytics_copy_failed=false
  copy_into_service analytics "$ANALYTICS_AUDIO_STAGED" "$ANALYTICS_AUDIO_URI" || analytics_copy_failed=true
  copy_into_service analytics "$ANALYTICS_TRANSCRIPT_FILE" "$ANALYTICS_TRANSCRIPT_URI" || analytics_copy_failed=true

  if [ "${analytics_copy_failed:-false}" = true ]; then
    print_header "Analytics Speech Job"
    printf "%s Skipped (unable to stage files in analytics container)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
  elif [ -n "$ANALYTICS_AUDIO_URI" ] && [ -n "$ANALYTICS_TRANSCRIPT_URI" ]; then
    ANALYTICS_PAYLOAD_FILE="$(mktemp)"
    cat <<JSON >"$ANALYTICS_PAYLOAD_FILE"
{
  "call_id": "00000000-0000-0000-0000-000000000001",
  "audio_uri": "$ANALYTICS_AUDIO_URI",
  "transcript_uri": "$ANALYTICS_TRANSCRIPT_URI",
  "analysis_types": ["sentiment", "keywords", "summary"],
  "keywords": ["plano", "desconto"]
}
JSON

    print_header "Analytics Speech Job"
    print_command "$ curl -sS -H '$AUTH_HEADER' -H 'Content-Type: application/json' --data @$ANALYTICS_PAYLOAD_FILE $API_BASE/api/v1/analytics/speech"
    total_tests=$((total_tests + 1))
    analytics_response=$(curl -sS -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        --data @"$ANALYTICS_PAYLOAD_FILE" \
        "$API_BASE/api/v1/analytics/speech") || analytics_response=""
    if printf '%s' "$analytics_response" | "$JQ_BIN" -e '.job_id' >/dev/null 2>&1; then
        job_id=$(printf '%s' "$analytics_response" | "$JQ_BIN" -r '.job_id')
        printf "%s\n" "$analytics_response" | "$JQ_BIN" '.'
        printf "${GREEN}✓ Job submitted (ID %s)${NC}\n" "$job_id"
        passed_tests=$((passed_tests + 1))

        print_header "Analytics Job Poll"
        attempts=0
        status="processing"
        while [ "$status" = "processing" ] && [ "$attempts" -lt 10 ]; do
            sleep 2
            job_response=$(curl -sS -H "$AUTH_HEADER" "$API_BASE/api/v1/analytics/speech/$job_id") || job_response=""
            printf "%s\n" "$job_response" | "$JQ_BIN" '.'
            status=$(printf '%s' "$job_response" | "$JQ_BIN" -r '.status // "failed"')
            attempts=$((attempts + 1))
        done
        if [ "$status" = "completed" ]; then
            printf "${GREEN}✓ Analytics completed${NC}\n"
        else
            printf "${YELLOW}⚠ Analytics status: %s${NC}\n" "$status"
        fi
    else
        printf "%s\n" "$analytics_response"
        printf "${RED}✗ FAILED to submit analytics job${NC}\n"
        failed_tests="${failed_tests}\n- Analytics Speech Job"
    fi
    rm -f "$ANALYTICS_PAYLOAD_FILE"
  else
    print_header "Analytics Speech Job"
    printf "%s Skipped (provide ANALYTICS_AUDIO_URI & ANALYTICS_TRANSCRIPT_URI)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
  fi
else
  print_header "Analytics Speech Job"
  printf "%s Skipped (set RUN_ANALYTICS=1)\n" "$WARN"
  skipped_tests=$((skipped_tests + 1))
fi

# Align optional test
if [ "$RUN_ALIGN" = "1" ]; then
  align_copy_failed=false
  copy_into_service align "$ANALYTICS_AUDIO_STAGED" "$ALIGN_AUDIO_URI" || align_copy_failed=true
  if [ "${align_copy_failed:-false}" = true ]; then
    print_header "Align + Diarize"
    printf "%s Skipped (unable to stage audio in align container)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
  elif [ -n "$ALIGN_AUDIO_URI" ]; then
    ALIGN_PAYLOAD_FILE="$(mktemp)"
    cat <<JSON >"$ALIGN_PAYLOAD_FILE"
{
  "transcript_id": "00000000-0000-0000-0000-000000000999",
  "transcript": {
    "text": "Cliente confirma dados e aceita o plano."
  },
  "audio_uri": "$ALIGN_AUDIO_URI",
  "enable_alignment": true,
  "enable_diarization": false
}
JSON
    do_curl "Align + Diarize" "json" \
        curl -sS -H "$AUTH_HEADER" -H "Content-Type: application/json" \
            --data @"$ALIGN_PAYLOAD_FILE" \
            "$API_BASE/api/v1/align_diarize"
    rm -f "$ALIGN_PAYLOAD_FILE"
  else
    print_header "Align + Diarize"
    printf "%s Skipped (provide ALIGN_AUDIO_URI accessible to the service)\n" "$WARN"
    skipped_tests=$((skipped_tests + 1))
  fi
else
  print_header "Align + Diarize"
  printf "%s Skipped (set RUN_ALIGN=1)\n" "$WARN"
  skipped_tests=$((skipped_tests + 1))
fi

printf "\n${MAGENTA}┌────────────── Feature Check Summary ──────────────┐${NC}\n"
printf "${MAGENTA}│${NC}  ${GREEN}Passed${NC}:   %2d/%-2d\n" "$passed_tests" "$total_tests"
printf "${MAGENTA}│${NC}  ${YELLOW}Skipped${NC}:  %2d\n" "$skipped_tests"
fail_count=$((total_tests - passed_tests))
printf "${MAGENTA}│${NC}  ${RED}Failed${NC}:   %2d\n" "$fail_count"
printf "${MAGENTA}└──────────────────────────────────────────────────┘${NC}\n"

if [ "$fail_count" -gt 0 ] && [ -n "$failed_tests" ]; then
    printf "${RED}Failures:${NC}%s\n" "$failed_tests"
fi

printf "\n${BLUE}Tip:${NC} To exercise optional flows, set environment flags before running:\n"
printf "  RUN_LLM=1 RUN_ANALYTICS=1 RUN_ALIGN=1 scripts/feature_check.sh\n"
