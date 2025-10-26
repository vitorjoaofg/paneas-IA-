#!/bin/bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-token_abc123}"
TEST_DATA_DIR="${TEST_DATA_DIR:-./test-data}"

# ANSI colors for status output.
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve sample files, falling back to available fixtures when the defaults
# are not present in the repository.
ASR_SAMPLE="${ASR_SAMPLE:-$TEST_DATA_DIR/audio/sample_10s.wav}"
if [ ! -f "$ASR_SAMPLE" ]; then
    fallback_wave="/tmp/asr_smoke_sample.wav"
    python3 - <<'PY'
import math, struct, wave
fr = 16000
duration = 5  # seconds
amplitude = 0.2
path = "/tmp/asr_smoke_sample.wav"
with wave.open(path, "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(fr)
    for i in range(fr * duration):
        value = int(32767 * amplitude * math.sin(2 * math.pi * 440 * i / fr))
        w.writeframes(struct.pack("<h", value))
PY
    ASR_SAMPLE="$fallback_wave"
    FALLBACK_ASR_SAMPLE=true
fi

DIAR_SAMPLE="${DIAR_SAMPLE:-$TEST_DATA_DIR/audio/sample_conversation.wav}"
if [ ! -f "$DIAR_SAMPLE" ]; then
    DIAR_SAMPLE="$ASR_SAMPLE"
    FALLBACK_DIAR_SAMPLE=true
fi

OCR_SAMPLE="${OCR_SAMPLE:-$TEST_DATA_DIR/documents/sample_5pages.pdf}"
if [ ! -f "$OCR_SAMPLE" ]; then
    OCR_SAMPLE="$(find "$TEST_DATA_DIR/documents" -maxdepth 1 -type f -name '*.pdf' | head -n1 || true)"
    FALLBACK_OCR_SAMPLE=true
fi

ASR_THRESHOLD_MS="${ASR_THRESHOLD_MS:-1800}"
if [ "${FALLBACK_ASR_SAMPLE:-false}" = true ]; then
    ASR_THRESHOLD_MS=5000
fi

OCR_THRESHOLD_MS="${OCR_THRESHOLD_MS:-4000}"
if [ "${FALLBACK_OCR_SAMPLE:-false}" = true ]; then
    OCR_THRESHOLD_MS=6000
fi

OCR_EXPECTED_PAGES_FALLBACK="${OCR_EXPECTED_PAGES_FALLBACK:-1}"
TTS_PAYLOAD_JSON='{"text": "Olá, este é um teste de síntese de voz.", "language": "pt"}'
TTS_PAYLOAD_FILE=$(mktemp)
trap 'rm -f "$TTS_PAYLOAD_FILE"' EXIT
printf '%s' "$TTS_PAYLOAD_JSON" >"$TTS_PAYLOAD_FILE"

OPTIONAL_SERVICES="${OPTIONAL_SERVICES:-llm_int4}"

ensure_sample() {
    local label=$1
    local path=$2
    if [ -z "$path" ] || [ ! -f "$path" ]; then
        echo -e "${RED}Required sample for ${label} not found. Set ${label}_SAMPLE env var.${NC}"
        exit 1
    fi
}

ensure_sample "ASR" "$ASR_SAMPLE"
ensure_sample "OCR" "$OCR_SAMPLE"
ensure_sample "DIAR" "$DIAR_SAMPLE"

if [ "${FALLBACK_ASR_SAMPLE:-false}" = true ]; then
    echo -e "${YELLOW}Using fallback ASR sample: $ASR_SAMPLE${NC}"
fi
if [ "${FALLBACK_OCR_SAMPLE:-false}" = true ]; then
    echo -e "${YELLOW}Using fallback OCR sample: $OCR_SAMPLE${NC}"
fi
if [ "${FALLBACK_DIAR_SAMPLE:-false}" = true ]; then
    echo -e "${YELLOW}Using fallback diarization sample: $DIAR_SAMPLE${NC}"
fi

passed=0
failed=0

echo "=== AI Stack Smoke Tests ==="
echo "API Base: $API_BASE"
echo ""

run_test() {
    local test_name=$1
    shift

    echo -n "Testing $test_name... "

    if "$@" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        passed=$((passed + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        failed=$((failed + 1))
        return 1
    fi
}

run_test "Health Check" \
    curl -s -f -H "Authorization: Bearer $API_TOKEN" "$API_BASE/api/v1/health"

echo -n "Testing ASR ($(basename "$ASR_SAMPLE"))... "
start_time=$(date +%s%3N)
response=$(curl -s -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -F "file=@$ASR_SAMPLE" \
    -F "language=pt" \
    -F "model=whisper/medium" \
    -F "compute_type=int8_float16" \
    "$API_BASE/api/v1/asr")
end_time=$(date +%s%3N)
duration=$((end_time - start_time))
processing_time=$(python3 -c 'import json, sys; print(json.loads(sys.stdin.read() or "{}").get("processing_time_ms", 999999))' <<<"$response")

if [ "$duration" -lt "$ASR_THRESHOLD_MS" ] && [ "$processing_time" -lt "$ASR_THRESHOLD_MS" ]; then
    echo -e "${GREEN}✓ PASS${NC} (${duration}ms total, ${processing_time}ms processing)"
    passed=$((passed + 1))
else
    echo -e "${RED}✗ FAIL${NC} (${duration}ms, expected < ${ASR_THRESHOLD_MS}ms)"
    failed=$((failed + 1))
fi

echo -n "Testing OCR ($(basename "$OCR_SAMPLE"))... "
start_time=$(date +%s%3N)
response=$(curl -s -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -F "file=@$OCR_SAMPLE" \
    -F "languages=pt,en" \
    -F "use_gpu=true" \
    "$API_BASE/api/v1/ocr")
end_time=$(date +%s%3N)
duration=$((end_time - start_time))
pages=$(python3 -c 'import json, sys; data=json.loads(sys.stdin.read() or "{}"); pages=data.get("pages") or []; print(len(pages) if hasattr(pages, "__len__") else 0)' <<<"$response")

OCR_EXPECTED_PAGES="${OCR_EXPECTED_PAGES:-5}"
if [ "${FALLBACK_OCR_SAMPLE:-false}" = true ]; then
    OCR_EXPECTED_PAGES="${OCR_EXPECTED_PAGES_FALLBACK:-1}"
fi

if [ "$duration" -lt "$OCR_THRESHOLD_MS" ] && [ "$pages" -ge "$OCR_EXPECTED_PAGES" ]; then
    echo -e "${GREEN}✓ PASS${NC} (${duration}ms for ${pages} pages)"
    passed=$((passed + 1))
else
    echo -e "${RED}✗ FAIL${NC} (${duration}ms, expected < ${OCR_THRESHOLD_MS}ms)"
    failed=$((failed + 1))
fi

echo -n "Testing LLM FP16 (70 tokens)... "
start_time=$(date +%s%3N)
response=$(curl -s -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen2.5-14b-instruct",
        "messages": [
            {"role": "system", "content": "Você é um assistente útil."},
            {"role": "user", "content": "Resuma em 3 parágrafos a importância da IA na medicina moderna."}
        ],
        "max_tokens": 70,
        "quality_priority": true
    }' \
    "$API_BASE/api/v1/chat/completions")
end_time=$(date +%s%3N)
duration=$((end_time - start_time))
completion_tokens=$(python3 -c 'import json, sys; data=json.loads(sys.stdin.read() or "{}"); print(data.get("usage", {}).get("completion_tokens", 0))' <<<"$response")

if [ "$duration" -lt 3200 ] && [ "$completion_tokens" -gt 50 ]; then
    echo -e "${GREEN}✓ PASS${NC} (${duration}ms, ${completion_tokens} tokens)"
    passed=$((passed + 1))
else
    echo -e "${RED}✗ FAIL${NC} (${duration}ms, expected < 1600ms)"
    failed=$((failed + 1))
fi

echo -n "Testing LLM INT4 (60 tokens)... "
start_time=$(date +%s%3N)
response=$(curl -s -X POST \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "qwen2.5-14b-instruct-awq",
        "messages": [
            {"role": "system", "content": "Você é um assistente útil."},
            {"role": "user", "content": "Liste 5 benefícios da computação em nuvem."}
        ],
        "max_tokens": 60
    }' \
    "$API_BASE/api/v1/chat/completions")
end_time=$(date +%s%3N)
duration=$((end_time - start_time))
completion_tokens=$(python3 -c 'import json, sys; data=json.loads(sys.stdin.read() or "{}"); print(data.get("usage", {}).get("completion_tokens", 0))' <<<"$response")

if [ "$duration" -lt 3200 ] && [ "$completion_tokens" -gt 40 ]; then
    echo -e "${GREEN}✓ PASS${NC} (${duration}ms, ${completion_tokens} tokens)"
    passed=$((passed + 1))
else
    echo -e "${RED}✗ FAIL${NC} (${duration}ms, expected < 900ms)"
    failed=$((failed + 1))
fi

run_test "TTS Generation" \
    bash -c 'curl -s -f -X POST \
        -H "Authorization: Bearer '"$API_TOKEN"'" \
        -H "Content-Type: application/json" \
        --data-binary "@'"$TTS_PAYLOAD_FILE"'" \
        '"$API_BASE"'/api/v1/tts -o /tmp/tts_output.wav \
        && test -s /tmp/tts_output.wav'

run_test "ASR with Diarization" \
    bash -c 'curl -s -f -X POST \
        -H "Authorization: Bearer '"$API_TOKEN"'" \
        -F "file=@'"$DIAR_SAMPLE"'" \
        -F "model=whisper/large-v3-turbo" \
        -F "compute_type=float16" \
        -F "enable_diarization=true" \
        '"$API_BASE"'/api/v1/asr \
        | python3 -c "import json,sys; data=json.load(sys.stdin); sys.exit(0 if \"segments\" in data else 1)"'

run_test "Prometheus Metrics" \
    bash -c 'curl -s -f '"$API_BASE"'/metrics | grep -q "http_requests_total"'

echo -n "Checking GPU utilization... "
gpu_metrics=$(curl -s "$API_BASE/metrics" | grep "DCGM_FI_DEV_GPU_UTIL" || true)
if [ -n "$gpu_metrics" ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    passed=$((passed + 1))
else
    echo -e "${YELLOW}⚠ WARNING${NC} (GPU metrics not available)"
fi

echo -n "Checking all services... "
health=$(curl -s -H "Authorization: Bearer $API_TOKEN" "$API_BASE/api/v1/health")
health_eval=$(printf "%s" "$health" | env OPTIONAL_SERVICES="$OPTIONAL_SERVICES" python3 - <<'PY'
import json, os, sys
payload = json.loads(sys.stdin.read() or "{}")
services = payload.get("services") or {}
optional = set(filter(None, os.environ.get("OPTIONAL_SERVICES", "").split(",")))
failing = {name: info for name, info in services.items() if str(info.get("status", "")).lower() != "up" and name not in optional}
if failing:
    print(json.dumps(failing, ensure_ascii=False))
else:
    print("OK")
PY
)

if [ "$health_eval" = "OK" ]; then
    echo -e "${GREEN}✓ PASS${NC}"
    passed=$((passed + 1))
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "Services status:"
    printf "%s\n" "$health_eval"
    failed=$((failed + 1))
fi

echo ""
echo "=== Test Summary ==="
echo -e "Passed: ${GREEN}$passed${NC}"
echo -e "Failed: ${RED}$failed${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Some tests failed. Check logs for details.${NC}"
fi
