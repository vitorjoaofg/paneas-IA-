from __future__ import annotations

from typing import Any, Dict

from .base import DocumentInterpreter


class GenericInterpreter(DocumentInterpreter):
    """Default interpreter that simply surfaces the extracted text."""

    def interpret(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        text = self._extract_text(ocr_json)
        return {
            "document_type": "generic",
            "text": text,
            "metadata": self._extract_metadata(ocr_json),
        }
