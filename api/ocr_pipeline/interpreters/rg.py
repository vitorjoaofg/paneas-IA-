from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base import DocumentInterpreter


class RgInterpreter(DocumentInterpreter):
    DATE_REGEX = re.compile(r"(\d{2}[./-]\d{2}[./-]\d{4})")
    NUMBER_REGEX = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}-?[0-9X]\b", re.IGNORECASE)

    def interpret(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        text = self._extract_text(ocr_json)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        return {
            "document_type": "rg",
            "nome": self._extract_labeled_value(lines, ["nome"]),
            "rg": self._extract_number(text, lines),
            "orgao_emissor": self._extract_labeled_value(lines, ["orgao emissor", "orgão emissor", "expeditor"]),
            "data_emissao": self._extract_date(lines, ["data de emissão", "emissão"]),
            "text": text,
            "metadata": self._extract_metadata(ocr_json),
        }

    def _extract_labeled_value(self, lines: List[str], labels: List[str]) -> Optional[str]:
        normalized_labels = [label.lower() for label in labels]
        for idx, line in enumerate(lines):
            lower_line = line.lower()
            for label in normalized_labels:
                if label in lower_line:
                    cleaned = re.sub(rf"(?i){re.escape(label)}\s*[:\-]?\s*", "", line).strip()
                    if cleaned:
                        return cleaned
                    if idx + 1 < len(lines):
                        return lines[idx + 1].strip()
        return None

    def _extract_number(self, text: str, lines: List[str]) -> Optional[str]:
        labeled = self._extract_labeled_value(lines, ["registro", "número"])
        if labeled:
            digits = re.sub(r"[^\w-]", "", labeled)
            if digits:
                return digits.upper()
        match = self.NUMBER_REGEX.search(text)
        return match.group(0).replace(".", "").replace("-", "").upper() if match else None

    def _extract_date(self, lines: List[str], labels: List[str]) -> Optional[str]:
        value = self._extract_labeled_value(lines, labels)
        if not value:
            return None
        match = self.DATE_REGEX.search(value)
        if match:
            return self._normalize_date(match.group(1))
        return value

    def _normalize_date(self, date_str: str) -> str:
        sanitized = date_str.replace(".", "/").replace("-", "/")
        return sanitized
