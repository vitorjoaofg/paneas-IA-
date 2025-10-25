import io
import os
import shutil
import time
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR

MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/models"))
CACHE_DIR = Path(os.environ.get("OCR_CACHE_DIR", "/tmp/paddleocr"))
USE_TENSORRT = os.environ.get("USE_TENSORRT", "true").lower() == "true"
FALLBACK_CPU = os.environ.get("FALLBACK_TO_CPU", "true").lower() == "true"

app = FastAPI(title="OCR Service", version="1.0.0")


class OCRService:
    def __init__(self) -> None:
        base_det = self._prepare_model_dir("det")
        base_rec = self._prepare_model_dir("rec")
        base_cls = self._prepare_model_dir("cls")

        self.ocr = PaddleOCR(
            use_gpu=USE_TENSORRT,
            det_model_dir=str(base_det),
            rec_model_dir=str(base_rec),
            cls_model_dir=str(base_cls),
            use_angle_cls=True,
            lang="pt",
        )

    def process_page(self, image: np.ndarray) -> Dict[str, Any]:
        start = time.perf_counter()
        result = self.ocr.ocr(image, cls=True)
        duration = int((time.perf_counter() - start) * 1000)
        blocks = []
        for line in result:
            for box, text in line:
                blocks.append(
                    {
                        "bbox": [int(coord) for coord in np.array(box).flatten()],
                        "text": text[0],
                        "confidence": float(text[1]),
                    }
                )
        text_joined = "\n".join(block["text"] for block in blocks)
        engine = "tensorrt" if USE_TENSORRT else "onnxruntime"
        return {
            "text": text_joined,
            "blocks": blocks,
            "metadata": {"processing_time_ms": duration, "engine": engine},
        }

    def process(self, contents: bytes, languages: List[str], output_format: str) -> Dict[str, Any]:
        images = self._load_images(contents)
        pages = []
        for idx, image in enumerate(images, start=1):
            page_result = self.process_page(image)
            pages.append(
                {
                    "page_num": idx,
                    "text": page_result["text"],
                    "blocks": page_result["blocks"],
                    "metadata": page_result["metadata"],
                }
            )
        return {
            "request_id": str(uuid.uuid4()),
            "pages": pages,
        }

    @staticmethod
    def _load_images(contents: bytes) -> List[np.ndarray]:
        if contents[:4] == b"%PDF":
            pil_images = convert_from_bytes(contents, dpi=300)
            return [cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) for img in pil_images]
        image_array = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return [image]

    def _prepare_model_dir(self, name: str) -> Path:
        """Resolve model directory into a writable cache location."""
        source = MODELS_DIR / name
        if not source.exists():
            source = MODELS_DIR / "paddleocr" / name
        if not source.exists():
            raise RuntimeError(f"PaddleOCR model directory not found for {name} under {MODELS_DIR}")

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        target = CACHE_DIR / name
        if not target.exists():
            shutil.copytree(source, target)
        return target


service = OCRService()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "up", "backend": "TensorRT" if USE_TENSORRT else "GPU"}


@app.post("/ocr")
async def ocr_endpoint(
    file: UploadFile = File(...),
    languages: str = Form('["pt"]'),
    output_format: str = Form("json"),
    use_gpu: bool = Form(True),
    deskew: bool = Form(True),
    denoise: bool = Form(False),
) -> Dict[str, Any]:
    contents = await file.read()
    try:
        language_list = json.loads(languages)
    except json.JSONDecodeError:
        language_list = [languages]
    result = service.process(contents, language_list, output_format)
    return result
