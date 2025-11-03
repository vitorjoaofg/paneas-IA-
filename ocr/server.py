import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Sequence

import cv2
import numpy as np
import structlog
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pdf2image import convert_from_bytes
from paddleocr import PaddleOCR
from prometheus_fastapi_instrumentator import Instrumentator

from document_classifier import classify_document
from entity_extractor import extract_entities
from image_preprocessor import preprocess_image

MODELS_DIR = Path(os.environ.get("MODELS_DIR", "/models"))
CACHE_DIR = Path(os.environ.get("OCR_CACHE_DIR", "/tmp/paddleocr"))
USE_TENSORRT = os.environ.get("USE_TENSORRT", "true").lower() == "true"
FALLBACK_CPU = os.environ.get("FALLBACK_TO_CPU", "true").lower() == "true"

LOGGER = structlog.get_logger(__name__)

app = FastAPI(title="OCR Service", version="1.1.0")
Instrumentator().instrument(app).expose(app, include_in_schema=False)


class OCRService:
    def __init__(self) -> None:
        self._base_det = self._prepare_model_dir("det")
        self._base_rec = self._prepare_model_dir("rec")
        self._base_cls = self._prepare_model_dir("cls")
        self._gpu_engine: PaddleOCR | None = None
        self._cpu_engine: PaddleOCR | None = None

    def process(
        self,
        contents: bytes,
        languages: Sequence[str],
        output_format: str,
        prefer_gpu: bool,
        *,
        deskew: bool,
        denoise: bool,
    ) -> Dict[str, Any]:
        images = self._load_images(contents)
        if not images:
            raise ValueError("Unable to decode input image or PDF")

        engine, engine_label = self._select_engine(prefer_gpu)
        pages = []
        for idx, image in enumerate(images, start=1):
            # Apply preprocessing if requested
            preprocessed_image = image
            if deskew or denoise:
                LOGGER.info(
                    "applying_image_preprocessing",
                    page=idx,
                    deskew=deskew,
                    denoise=denoise,
                )
                preprocessed_image = preprocess_image(
                    image,
                    deskew=deskew,
                    denoise=denoise,
                    enhance_contrast=True,  # Always enhance contrast for better OCR
                )

            try:
                page_result = self._process_page(engine, preprocessed_image, engine_label)
            except Exception as exc:  # noqa: BLE001
                if prefer_gpu and FALLBACK_CPU:
                    LOGGER.warning(
                        "ocr_gpu_processing_failed_falling_back",
                        page=idx,
                        error=str(exc),
                    )
                    engine, engine_label = self._select_engine(False)
                    page_result = self._process_page(engine, image, engine_label)
                else:
                    raise
            page_result["metadata"].update(
                {
                    "deskew": deskew,
                    "denoise": denoise,
                    "languages": list(languages),
                }
            )
            pages.append(
                {
                    "page_num": idx,
                    "text": page_result["text"],
                    "blocks": page_result["blocks"],
                    "document_type": page_result.get("document_type"),
                    "entities": page_result.get("entities", []),
                    "metadata": page_result["metadata"],
                }
            )

        return {
            "request_id": str(uuid.uuid4()),
            "pages": pages,
            "output_format": output_format,
        }

    def _process_page(self, engine: PaddleOCR, image: np.ndarray, engine_label: str) -> Dict[str, Any]:
        start = time.perf_counter()
        result = engine.ocr(image, cls=True)
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

        # Classify document type
        doc_classification = classify_document(text_joined)
        document_type = {
            "type": doc_classification.type.value,
            "confidence": doc_classification.confidence,
            "detected_by": doc_classification.detected_by,
            "matched_patterns": doc_classification.matched_patterns,
        }

        # Extract entities
        entities_raw = extract_entities(text_joined, blocks)
        entities = [
            {
                "type": e.type.value,
                "value": e.value,
                "raw_value": e.raw_value,
                "confidence": e.confidence,
                "position": e.position,
                "validated": e.validated,
            }
            for e in entities_raw
        ]

        return {
            "text": text_joined,
            "blocks": blocks,
            "document_type": document_type,
            "entities": entities,
            "metadata": {"processing_time_ms": duration, "engine": engine_label},
        }

    def _select_engine(self, prefer_gpu: bool) -> tuple[PaddleOCR, str]:
        if prefer_gpu:
            engine = self._ensure_gpu_engine()
            if engine is not None:
                return engine, "gpu-tensorrt" if USE_TENSORRT else "gpu"
            if FALLBACK_CPU:
                LOGGER.warning("ocr_gpu_unavailable_falling_back_to_cpu")
                return self._ensure_cpu_engine(), "cpu"
            raise RuntimeError("GPU OCR engine unavailable and CPU fallback disabled")
        return self._ensure_cpu_engine(), "cpu"

    def _ensure_gpu_engine(self) -> PaddleOCR | None:
        if self._gpu_engine is not None:
            return self._gpu_engine
        try:
            self._gpu_engine = self._create_engine(use_gpu=True, use_tensorrt=USE_TENSORRT)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("ocr_gpu_initialization_failed", error=str(exc))
            self._gpu_engine = None
        return self._gpu_engine

    def _ensure_cpu_engine(self) -> PaddleOCR:
        if self._cpu_engine is None:
            self._cpu_engine = self._create_engine(use_gpu=False, use_tensorrt=False)
        return self._cpu_engine

    def _create_engine(self, *, use_gpu: bool, use_tensorrt: bool) -> PaddleOCR:
        return PaddleOCR(
            use_gpu=use_gpu,
            use_tensorrt=use_gpu and use_tensorrt,
            det_model_dir=str(self._base_det),
            rec_model_dir=str(self._base_rec),
            cls_model_dir=str(self._base_cls),
            use_angle_cls=True,
            lang="pt",
        )

    @staticmethod
    def _load_images(contents: bytes) -> List[np.ndarray]:
        if contents[:4] == b"%PDF":
            pil_images = convert_from_bytes(contents, dpi=300)
            return [cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) for img in pil_images]
        image_array = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return [image] if image is not None else []

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
    backend = "gpu"
    if service._gpu_engine is None:
        backend = "cpu"
    return {"status": "up", "backend": backend}


def _parse_languages(raw: str) -> List[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw

    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValueError("languages must be a string or list of strings")

    languages: List[str] = []
    for item in parsed:
        if not isinstance(item, str):
            raise ValueError("languages list must contain strings only")
        languages.append(item.strip() or "pt")
    return languages or ["pt"]


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
        language_list = _parse_languages(languages)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = service.process(
            contents,
            language_list,
            output_format,
            prefer_gpu=use_gpu,
            deskew=deskew,
            denoise=denoise,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("ocr_processing_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="OCR processing failed") from exc
    return result
