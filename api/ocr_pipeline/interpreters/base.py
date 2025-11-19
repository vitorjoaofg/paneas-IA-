from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DocumentInterpreter(ABC):
    """Common contract for OCR post-processors."""

    @abstractmethod
    def interpret(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _extract_text(self, ocr_json: Dict[str, Any]) -> str:
        text = ocr_json.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        pages = ocr_json.get("pages") or []
        page_texts: List[str] = []
        for page in pages:
            page_text = page.get("text")
            if isinstance(page_text, str) and page_text.strip():
                page_texts.append(page_text.strip())
        if page_texts:
            return "\n".join(page_texts)
        blocks = ocr_json.get("blocks") or []
        block_texts = [
            block.get("text", "").strip()
            for block in blocks
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        return "\n".join(text for text in block_texts if text)

    def _extract_blocks(self, ocr_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        blocks = ocr_json.get("blocks")
        return blocks if isinstance(blocks, list) else []

    def _extract_metadata(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        metadata = ocr_json.get("metadata")
        return metadata if isinstance(metadata, dict) else {}
