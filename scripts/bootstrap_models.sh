#!/bin/bash
set -euo pipefail

MODELS_DIR="/srv/models"
MANIFEST_FILE="$MODELS_DIR/manifests/manifest.json"

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

if ! command -v hf >/dev/null 2>&1; then
    echo "ERROR: 'hf' CLI not found. Install it with: pip install huggingface_hub[cli]"
    exit 1
fi

echo "=== AI Stack Models Bootstrap ==="
echo "Target directory: $MODELS_DIR"
echo ""

mkdir -p "$MODELS_DIR"/{whisper,pyannote,llama,xtts,paddleocr,embeddings}
mkdir -p "$MODELS_DIR"/manifests/licenses

model_exists() {
    local model_path=$1
    local model_name=$2

    if [ -d "$model_path" ] && [ "$(ls -A "$model_path" 2>/dev/null)" ]; then
        echo "✓ $model_name already exists at $model_path"
        return 0
    else
        echo "✗ $model_name not found, will download..."
        return 1
    fi
}

download_with_retry() {
    local url=$1
    local output=$2
    local retries=3

    for i in $(seq 1 $retries); do
        echo "Downloading $output (attempt $i/$retries)..."
        if wget -c -O "$output" "$url"; then
            return 0
        fi
        sleep 5
    done

    echo "Failed to download $output after $retries attempts"
    return 1
}

hf_download_public() {
    local repo_id=$1
    local target_dir=$2
    local token_args=()
    if [ -n "${HF_TOKEN:-}" ]; then
        token_args+=(--token "$HF_TOKEN")
    fi
    hf download "$repo_id" \
        --repo-type model \
        --local-dir "$target_dir" \
        --include "*" \
        "${token_args[@]}"
}

hf_download_private() {
    local repo_id=$1
    local target_dir=$2
    if [ -z "${HF_TOKEN:-}" ]; then
        echo "ERROR: HF_TOKEN is required to download $repo_id"
        return 1
    fi
    hf download "$repo_id" \
        --repo-type model \
        --local-dir "$target_dir" \
        --include "*" \
        --token "$HF_TOKEN"
}

hf_download_public_any() {
    local target_dir=$1
    shift
    local repos=("$@")

    local token_args=()
    if [ -n "${HF_TOKEN:-}" ]; then
        token_args+=(--token "$HF_TOKEN")
    fi

    rm -rf "$target_dir"
    mkdir -p "$target_dir"

    for repo_id in "${repos[@]}"; do
        echo "Attempting download from $repo_id"
        rm -rf "$target_dir"
        mkdir -p "$target_dir"
        if hf download "$repo_id" \
            --repo-type model \
            --local-dir "$target_dir" \
            --include "*" \
            "${token_args[@]}"; then
            return 0
        else
            status=$?
            echo "Failed to download from $repo_id (exit $status)."
        fi
    done

    echo "ERROR: Unable to download any of the candidates: ${repos[*]}"
    rm -rf "$target_dir"
    return 1
}

hf_download_file_any() {
    local target_path=$1
    shift
    local urls=("$@")

    local tmp_target
    tmp_target=$(mktemp)
    for url in "${urls[@]}"; do
        echo "Attempting download from $url"
        if curl -fL "$url" -o "$tmp_target"; then
            mkdir -p "$(dirname "$target_path")"
            mv "$tmp_target" "$target_path"
            return 0
        fi
        echo "Failed to download $url"
    done
    rm -f "$tmp_target"
    echo "ERROR: Unable to download any of URLs: ${urls[*]}"
    return 1
}

verify_checksum() {
    local file=$1
    local expected_sha256=$2

    echo "Verifying checksum for $file..."
    local actual_sha256
    actual_sha256=$(sha256sum "$file" | awk '{print $1}')

    if [ "$actual_sha256" != "$expected_sha256" ]; then
        echo "ERROR: Checksum mismatch for $file"
        echo "Expected: $expected_sha256"
        echo "Got: $actual_sha256"
        return 1
    fi

    echo "Checksum verified ✓"
    return 0
}

echo "=== Checking existing models in $MODELS_DIR ==="
echo ""

if command -v find >/dev/null 2>&1; then
    find "$MODELS_DIR" -type f \( -name "*.bin" -o -name "*.safetensors" -o -name "config.json" \) | head -20
fi

echo ""
echo "Found models:"
if [ -d "$MODELS_DIR" ]; then
    ls -lh "$MODELS_DIR"/*/ 2>/dev/null || true
fi

echo ""
echo "[1/8] Checking Whisper large-v3..."
if ! model_exists "$MODELS_DIR/whisper/large-v3" "Whisper large-v3"; then
    echo "Downloading Whisper large-v3..."
    hf_download_public Systran/faster-whisper-large-v3 "$MODELS_DIR/whisper/large-v3"
fi

echo ""
echo "[2/8] Checking Whisper large-v3-turbo..."
if ! model_exists "$MODELS_DIR/whisper/large-v3-turbo" "Whisper large-v3-turbo"; then
    echo "Downloading Whisper large-v3-turbo..."
    hf_download_public_any "$MODELS_DIR/whisper/large-v3-turbo" \
        Systran/faster-whisper-large-v3-turbo \
        Systran/faster-whisper-large-v3
fi

echo ""
echo "[3/8] Checking Pyannote models..."
if [ -z "${HF_TOKEN:-}" ]; then
    echo "WARNING: HF_TOKEN not set. Skipping Pyannote models (required for diarization)."
    echo "To enable diarization, set HF_TOKEN and re-run this script."
else
    if ! model_exists "$MODELS_DIR/pyannote/speaker-diarization-3.1" "Pyannote Diarization 3.1"; then
        echo "Downloading Pyannote speaker-diarization-3.1..."
        hf_download_private pyannote/speaker-diarization-3.1 "$MODELS_DIR/pyannote/speaker-diarization-3.1"
    fi

    if ! model_exists "$MODELS_DIR/pyannote/segmentation-3.0" "Pyannote Segmentation 3.0"; then
        echo "Downloading Pyannote segmentation-3.0..."
        hf_download_private pyannote/segmentation-3.0 "$MODELS_DIR/pyannote/segmentation-3.0"
    fi
fi

echo ""
echo "[4/8] Checking LLaMA-3.1-8B-Instruct FP16..."
if ! model_exists "$MODELS_DIR/llama/fp16" "LLaMA-3.1-8B FP16"; then
    echo "Downloading LLaMA-3.1-8B-Instruct FP16..."
    hf_download_public meta-llama/Meta-Llama-3.1-8B-Instruct "$MODELS_DIR/llama/fp16"
fi

echo ""
echo "[5/8] Checking LLaMA-3.1-8B-Instruct INT4/AWQ..."
if ! model_exists "$MODELS_DIR/llama/int4-awq" "LLaMA-3.1-8B INT4/AWQ"; then
    echo "Downloading LLaMA-3.1-8B-Instruct INT4/AWQ..."
    hf_download_public_any "$MODELS_DIR/llama/int4-awq" \
        TheBloke/Meta-Llama-3.1-8B-Instruct-AWQ \
        hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4
fi

echo ""
echo "[6/8] Checking XTTS-v2..."
if ! model_exists "$MODELS_DIR/xtts" "XTTS-v2"; then
    echo "Downloading XTTS-v2..."
    hf_download_public coqui/XTTS-v2 "$MODELS_DIR/xtts"
fi

echo ""
echo "[7/8] Checking PaddleOCR models..."
mkdir -p "$MODELS_DIR/paddleocr"/{det,rec,cls,onnx,engines}

if ! model_exists "$MODELS_DIR/paddleocr/det" "PaddleOCR Detection"; then
    echo "Downloading PaddleOCR detection model..."
    hf_download_public_any "$MODELS_DIR/paddleocr/det" \
        PaddlePaddle/PP-OCRv4_mobile_det \
        PaddlePaddle/PP-OCRv4_mobile_det_infer \
        PaddlePaddle/PP-OCRv4_det
fi

if ! model_exists "$MODELS_DIR/paddleocr/rec" "PaddleOCR Recognition"; then
    echo "Downloading PaddleOCR recognition model..."
    hf_download_public_any "$MODELS_DIR/paddleocr/rec" \
        PaddlePaddle/latin_PP-OCRv3_mobile_rec \
        PaddlePaddle/PP-OCRv4_mobile_rec \
        PaddlePaddle/PP-OCRv4_rec
fi

if ! model_exists "$MODELS_DIR/paddleocr/cls" "PaddleOCR Classification"; then
    echo "Downloading PaddleOCR classification model..."
    hf_download_public_any "$MODELS_DIR/paddleocr/cls" \
        PaddlePaddle/PP-OCRv3_cls \
        PaddlePaddle/PP-OCRv4_cls \
        PaddlePaddle/PP-LCNet_x1_0_doc_ori
fi

echo ""
echo "[8/8] Checking BGE-M3 embeddings..."
if ! model_exists "$MODELS_DIR/embeddings/bge-m3" "BGE-M3"; then
    echo "Downloading BGE-M3 embeddings..."
    hf_download_public BAAI/bge-m3 "$MODELS_DIR/embeddings/bge-m3"
fi

echo ""
echo "=== Verifying model integrity ==="

declare -A EXPECTED_MODELS=(
    ["whisper-large-v3"]="$MODELS_DIR/whisper/large-v3"
    ["whisper-large-v3-turbo"]="$MODELS_DIR/whisper/large-v3-turbo"
    ["pyannote-diarization"]="$MODELS_DIR/pyannote/speaker-diarization-3.1"
    ["pyannote-segmentation"]="$MODELS_DIR/pyannote/segmentation-3.0"
    ["llama-fp16"]="$MODELS_DIR/llama/fp16"
    ["llama-int4"]="$MODELS_DIR/llama/int4-awq"
    ["xtts"]="$MODELS_DIR/xtts"
    ["paddleocr-det"]="$MODELS_DIR/paddleocr/det"
    ["paddleocr-rec"]="$MODELS_DIR/paddleocr/rec"
    ["paddleocr-cls"]="$MODELS_DIR/paddleocr/cls"
    ["bge-m3"]="$MODELS_DIR/embeddings/bge-m3"
)

MISSING_MODELS=0
for model_name in "${!EXPECTED_MODELS[@]}"; do
    model_path="${EXPECTED_MODELS[$model_name]}"
    if [ ! -d "$model_path" ] || [ ! "$(ls -A "$model_path" 2>/dev/null)" ]; then
        echo "✗ MISSING: $model_name at $model_path"
        MISSING_MODELS=$((MISSING_MODELS + 1))
    else
        echo "✓ OK: $model_name"
    fi
done

if [ $MISSING_MODELS -gt 0 ]; then
    echo ""
    echo "WARNING: $MISSING_MODELS models are missing or incomplete."
    echo "Some features may not work correctly."
fi

echo ""
echo "=== Building TensorRT engines for OCR ==="
if [ -d "$MODELS_DIR/paddleocr/det" ] && [ "$(ls -A "$MODELS_DIR/paddleocr/det" 2>/dev/null)" ]; then
    echo "PaddleOCR models found, building TensorRT engines..."
    if command -v docker >/dev/null 2>&1; then
        if docker images | grep -q "stack-ocr"; then
            docker run --rm --gpus all \
                -v "$MODELS_DIR/paddleocr:/models/paddleocr" \
                stack-ocr:latest \
                bash /build_tensorrt_engines.sh
        else
            echo "WARNING: stack-ocr Docker image not found. TensorRT engines will be built on first run."
        fi
    else
        echo "WARNING: Docker not available. TensorRT engines will be built on first run."
    fi
else
    echo "PaddleOCR models not found, skipping TensorRT build."
fi

echo ""
echo "=== Generating manifest ==="
mkdir -p "$(dirname "$MANIFEST_FILE")"
cat > "$MANIFEST_FILE" <<MANIFEST_EOF
{
  "version": "1.0.0",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "server_path": "$MODELS_DIR",
  "models": {
    "whisper_large_v3": {
      "path": "whisper/large-v3",
      "size_gb": 3.1,
      "license": "MIT",
      "status": "$([ -d "$MODELS_DIR/whisper/large-v3" ] && echo "present" || echo "missing")"
    },
    "whisper_large_v3_turbo": {
      "path": "whisper/large-v3-turbo",
      "size_gb": 1.6,
      "license": "MIT",
      "status": "$([ -d "$MODELS_DIR/whisper/large-v3-turbo" ] && echo "present" || echo "missing")"
    },
    "pyannote_diarization": {
      "path": "pyannote/speaker-diarization-3.1",
      "size_gb": 0.45,
      "license": "MIT",
      "status": "$([ -d "$MODELS_DIR/pyannote/speaker-diarization-3.1" ] && echo "present" || echo "missing")"
    },
    "pyannote_segmentation": {
      "path": "pyannote/segmentation-3.0",
      "size_gb": 0.22,
      "license": "MIT",
      "status": "$([ -d "$MODELS_DIR/pyannote/segmentation-3.0" ] && echo "present" || echo "missing")"
    },
    "llama_fp16": {
      "path": "llama/fp16",
      "size_gb": 16.0,
      "license": "Llama 3.1 Community License",
      "status": "$([ -d "$MODELS_DIR/llama/fp16" ] && echo "present" || echo "missing")"
    },
    "llama_int4": {
      "path": "llama/int4-awq",
      "size_gb": 4.8,
      "license": "Llama 3.1 Community License",
      "status": "$([ -d "$MODELS_DIR/llama/int4-awq" ] && echo "present" || echo "missing")"
    },
    "xtts": {
      "path": "xtts",
      "size_gb": 2.3,
      "license": "Apache 2.0",
      "status": "$([ -d "$MODELS_DIR/xtts" ] && echo "present" || echo "missing")"
    },
    "paddleocr": {
      "path": "paddleocr",
      "size_gb": 0.38,
      "license": "Apache 2.0",
      "status": "$([ -d "$MODELS_DIR/paddleocr/det" ] && echo "present" || echo "missing")"
    },
    "bge_m3": {
      "path": "embeddings/bge-m3",
      "size_gb": 0.67,
      "license": "MIT",
      "status": "$([ -d "$MODELS_DIR/embeddings/bge-m3" ] && echo "present" || echo "missing")"
    }
  }
}
MANIFEST_EOF

echo ""
echo "=== Bootstrap Complete ==="
echo "Manifest saved to: $MANIFEST_FILE"
echo ""
echo "Summary:"
if command -v jq >/dev/null 2>&1; then
    jq -r '.models | to_entries | .[] | "\(.key): \(.value.status)"' "$MANIFEST_FILE"
else
    cat "$MANIFEST_FILE"
fi

echo ""
echo "Next steps:"
echo "  1. Review .env configuration"
echo "  2. Run: docker compose up -d"
echo "  3. Run: ./scripts/smoke_tests.sh"
