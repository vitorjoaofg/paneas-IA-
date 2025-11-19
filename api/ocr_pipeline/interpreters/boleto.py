from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .base import DocumentInterpreter


class BoletoInterpreter(DocumentInterpreter):
    DATE_REGEX = re.compile(r"(\d{2}[./-]\d{2}[./-]\d{4})")
    MONEY_REGEX = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")

    def interpret(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        text = self._extract_text(ocr_json)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        return {
            "document_type": "boleto",
            "linha_digitavel": self._extract_linha_digitavel(text),
            "valor": self._extract_labeled_value(lines, ["valor do documento", "valor", "valor documento"]),
            "vencimento": self._extract_date(lines, ["vencimento", "data de vencimento"]),
            "sacado": self._extract_labeled_value(lines, ["sacado"]),
            "cedente": self._extract_labeled_value(lines, ["cedente"]),
            "text": text,
            "metadata": self._extract_metadata(ocr_json),
        }

    def _extract_linha_digitavel(self, text: str) -> Optional[str]:
        cleaned = re.sub(r"\s+", "", text)
        matches = re.findall(r"\d{40,}", cleaned)
        if matches:
            # Prefer the longest numeric sequence (boleto lines usually have 47 or 48 digits)
            candidate = max(matches, key=len)
            if 40 <= len(candidate) <= 56:
                return candidate
        return None

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

    def _extract_date(self, lines: List[str], labels: List[str]) -> Optional[str]:
        value = self._extract_labeled_value(lines, labels)
        if not value:
            return None
        match = self.DATE_REGEX.search(value)
        return match.group(1) if match else None
