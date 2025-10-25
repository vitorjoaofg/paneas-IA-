#!/bin/bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-token_abc123}"
TEST_DATA_DIR="${TEST_DATA_DIR:-./test-data}"
STREAM_SAMPLE="${STREAM_SAMPLE:-$TEST_DATA_DIR/audio/sample_stream.wav}"
STREAM_CHUNK_MS="${STREAM_CHUNK_MS:-600}"
export STREAM_SAMPLE

SCHEME="ws"
HOST="${API_BASE#http://}"
if [[ "$API_BASE" == https://* ]]; then
    SCHEME="wss"
    HOST="${API_BASE#https://}"
elif [[ "$API_BASE" != http://* ]]; then
    HOST="${API_BASE#ws://}"
    HOST="${HOST#wss://}"
    SCHEME="ws"
fi
STREAM_URL="${STREAM_URL:-$SCHEME://$HOST/api/v1/asr/stream}"

ensure_sample() {
    local path=$1
    if [ -f "$path" ]; then
        return 0
    fi

    echo "Gerando áudio sintético para streaming em $path"
    mkdir -p "$(dirname "$path")"
    python3 - <<'PY'
import math, os, struct, wave, pathlib
target = pathlib.Path(os.environ["STREAM_SAMPLE"])
with wave.open(str(target), "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    duration = 3
    freq = 440
    amplitude = 0.2
    for i in range(16000 * duration):
        value = int(32767 * amplitude * math.sin(2 * math.pi * freq * i / 16000))
        w.writeframes(struct.pack("<h", value))
PY
}

ensure_sample "$STREAM_SAMPLE"

echo "=== Streaming ASR Smoke Test ==="
echo "API Base: $API_BASE"
echo "Stream URL: $STREAM_URL"
echo "Sample: $STREAM_SAMPLE"

OUTPUT_FILE=$(mktemp)
trap 'rm -f "$OUTPUT_FILE"' EXIT

if python3 scripts/streaming/asr_stream_client.py \
    --url "$STREAM_URL" \
    --token "$API_TOKEN" \
    --file "$STREAM_SAMPLE" \
    --chunk-ms "$STREAM_CHUNK_MS" \
    >"$OUTPUT_FILE" 2>&1; then
    cat "$OUTPUT_FILE"
else
    cat "$OUTPUT_FILE"
    echo "Streaming client returned non-zero exit code."
    exit 1
fi

if grep -Eq '"event"\s*:\s*"final"' "$OUTPUT_FILE"; then
    echo "✓ Streaming ASR smoke test passed."
else
    echo "✗ Streaming ASR smoke test failed (final event not observed)."
    exit 1
fi
