from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .base import DocumentInterpreter


class CnhInterpreter(DocumentInterpreter):
    """Interpreter with heuristics tailored to Brazilian CNH documents."""

    DATE_REGEX = re.compile(r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})")
    CPF_REGEX = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
    ELEVEN_DIGITS_REGEX = re.compile(r"\b\d{11}\b")
    REGISTRO_REGEX = re.compile(r"\b(\d{5,12})\s*(?=SSP|DETRAN)", re.IGNORECASE)
    ORGAO_REGEX = re.compile(r"(SSP/[A-Z]{2}|DETRAN/[A-Z]{2}|DETRAN-[A-Z]{2})", re.IGNORECASE)

    def interpret(self, ocr_json: Dict[str, Any]) -> Dict[str, Any]:
        text = self._extract_text(ocr_json)
        lines = self._prepare_lines(text)
        name, name_end_idx = self._extract_name(lines)
        entities = self._collect_entities(ocr_json)

        registro, orgao = self._extract_registro_e_orgao(text)
        date_candidates = self._collect_dates(text)

        structured: Dict[str, Any] = {
            "document_type": "cnh",
            "nome": name,
            "registro": registro,
            "orgao_emissor": orgao,
            "documento": self._extract_document_number(text, entities),
            "data_nascimento": None,
            "validade": None,
            "primeira_habilitacao": None,
            "filiacao": self._extract_filiation(lines, start_index=name_end_idx),
            "local_emissao": self._extract_emission_location(lines),
            "data_emissao": None,
            "text": text,
            "metadata": self._extract_metadata(ocr_json),
        }
        structured.update(self._assign_dates(date_candidates))

        return structured

    def _prepare_lines(self, text: str) -> List[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _collect_entities(self, ocr_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        for page in ocr_json.get("pages", []):
            if isinstance(page, dict):
                entities.extend(page.get("entities") or [])
        return entities

    def _extract_name(self, lines: List[str]) -> Tuple[Optional[str], int]:
        buffer: List[str] = []
        end_index = 0
        for idx, line in enumerate(lines):
            normalized = self._normalize_whitespace(line)
            if not normalized or self._is_header_line(normalized):
                continue
            if self._contains_digits(normalized):
                if buffer:
                    break
                continue
            buffer.append(normalized)
            candidate = " ".join(buffer)
            if self._looks_like_name(candidate):
                return self._normalize_name(candidate), idx + 1
            end_index = idx + 1
        if buffer:
            return self._normalize_name(" ".join(buffer)), end_index
        return None, 0

    def _extract_filiation(self, lines: List[str], start_index: int) -> Optional[List[str]]:
        stop_keywords = {
            "proibido",
            "ataemiss",
            "emissao",
            "validade",
            "registro",
            "habilit",
            "doc",
            "documento",
            "ata",
            "org",
            "cpf",
            "filiacao",
            "filiação",
        }
        parents: List[str] = []
        allow_suffix_for_last = False
        collector: List[str] = []
        for line in lines[start_index:]:
            normalized = self._normalize_whitespace(line)
            if not normalized:
                continue
            lower_value = normalized.lower()
            if any(keyword in lower_value for keyword in stop_keywords):
                collector.clear()
                continue
            if self._contains_digits(normalized):
                collector.clear()
                continue
            cleaned = re.sub(r"[^a-zA-ZÀ-ÿ\s]", " ", normalized).strip()
            cleaned = self._normalize_whitespace(cleaned)
            parts = cleaned.split()
            if len(parts) == 1 and parents and allow_suffix_for_last:
                parents[-1] = f"{parents[-1]} {parts[0].title()}"
                allow_suffix_for_last = False
                continue
            if len(parts) < 2:
                collector.extend(parts)
                continue
            candidate_parts = collector + parts
            collector.clear()
            parents.append(self._normalize_name(" ".join(candidate_parts)))
            allow_suffix_for_last = True
            if len(parents) == 2:
                break
        if collector and len(parents) < 2:
            parents.append(self._normalize_name(" ".join(collector)))
        return parents or None

    def _extract_document_number(self, text: str, entities: List[Dict[str, Any]]) -> Optional[str]:
        for entity in entities:
            if entity.get("type") == "CPF":
                value = entity.get("value") or entity.get("raw_value")
                if value:
                    return self._format_cpf(value)
        cpf_match = self.CPF_REGEX.search(text)
        if cpf_match:
            return self._format_cpf(cpf_match.group(0))
        digits_match = self.ELEVEN_DIGITS_REGEX.search(text)
        if digits_match:
            return self._format_cpf(digits_match.group(0))
        return None

    def _extract_registro_e_orgao(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        registro = None
        orgao = None
        registro_match = self.REGISTRO_REGEX.search(text)
        if registro_match:
            registro = registro_match.group(1)
        orgao_match = self.ORGAO_REGEX.search(text)
        if orgao_match:
            orgao = orgao_match.group(1).upper()
        return registro, orgao

    def _collect_dates(self, text: str) -> List[Dict[str, Any]]:
        dates: List[Dict[str, Any]] = []
        for match in self.DATE_REGEX.finditer(text):
            raw = match.group(1)
            normalized = self._normalize_date(raw, text, match.end())
            if normalized:
                context_start = max(0, match.start() - 30)
                context_end = min(len(text), match.end() + 30)
                dates.append(
                    {
                        "value": normalized,
                        "start": match.start(),
                        "raw": raw,
                        "context": text[context_start:context_end].lower(),
                    }
                )
        return dates

    def _assign_dates(self, dates: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        assigned = {
            "data_nascimento": None,
            "validade": None,
            "primeira_habilitacao": None,
            "data_emissao": None,
        }
        if not dates:
            return assigned

        remaining = list(dates)
        label_map = {
            "data_nascimento": ["nascimento", "nasc"],
            "validade": ["validade", "val"],
            "primeira_habilitacao": ["1a habil", "primeira habil"],
            "data_emissao": ["emissão", "emissao", "expedi"],
        }

        for field, labels in label_map.items():
            match = self._find_date_with_keywords(remaining, labels)
            if match:
                assigned[field] = match["value"]
                remaining.remove(match)

        years = [(entry, int(entry["value"][:4])) for entry in remaining if entry.get("value")]

        if assigned["data_nascimento"] is None:
            birth = self._pick_date_by_year(years, max_year=2000, prefer_highest=False)
            if birth:
                entry, _ = birth
                assigned["data_nascimento"] = entry["value"]
                years.remove(birth)

        if assigned["validade"] is None:
            validity = self._pick_date_by_year(
                years,
                min_year=2000,
                prefer_highest=True,
                allow_fallback=True,
            )
            if validity:
                entry, _ = validity
                assigned["validade"] = entry["value"]
                years.remove(validity)

        if assigned["primeira_habilitacao"] is None:
            first = self._pick_date_by_year(years, min_year=1950, max_year=2020, prefer_highest=False)
            if first:
                entry, _ = first
                assigned["primeira_habilitacao"] = entry["value"]
                years.remove(first)

        if assigned["data_emissao"] is None:
            emission = self._pick_date_by_year(years, prefer_highest=True, allow_fallback=True)
            if emission:
                entry, _ = emission
                assigned["data_emissao"] = entry["value"]

        return assigned

    def _find_date_with_keywords(
        self,
        dates: List[Dict[str, Any]],
        keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        lowered = [keyword.lower() for keyword in keywords]
        for candidate in dates:
            context = candidate.get("context", "")
            if any(keyword in context for keyword in lowered):
                return candidate
        return None

    def _pick_date_by_year(
        self,
        year_entries: List[Tuple[Dict[str, Any], int]],
        *,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        prefer_highest: bool,
        allow_fallback: bool = False,
    ) -> Optional[Tuple[Dict[str, Any], int]]:
        filtered: List[Tuple[Dict[str, Any], int]] = []
        for entry, year in year_entries:
            if min_year is not None and year < min_year:
                continue
            if max_year is not None and year > max_year:
                continue
            filtered.append((entry, year))
        if not filtered and allow_fallback:
            filtered = list(year_entries)
        if not filtered:
            return None
        filtered.sort(key=lambda item: item[1], reverse=prefer_highest)
        return filtered[0]

    def _extract_emission_location(self, lines: List[str]) -> Optional[str]:
        for line in reversed(lines):
            if "emissão" in line.lower() or "emissao" in line.lower():
                cleaned = self.DATE_REGEX.sub("", line)
                cleaned = self._normalize_whitespace(cleaned)
                if cleaned:
                    return cleaned.title()
        # fallback: look for state/city near bottom
        for line in reversed(lines):
            if any(city in line.lower() for city in ("sao paulo", "rio de janeiro", "curitiba", "porto alegre")):
                return line.title()
        return None

    def _format_cpf(self, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) != 11:
            return value
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"

    def _normalize_date(self, value: str, text: str, end_index: int) -> Optional[str]:
        if not value:
            return None
        sanitized = value.replace(".", "/").replace("-", "/")
        parts = sanitized.split("/")
        if len(parts) != 3:
            return None
        day, month, year = parts
        if len(year) < 4:
            year = self._complete_year(year, text, end_index)
            if len(year) != 4:
                return None
        try:
            parsed = datetime.strptime(f"{day.zfill(2)}/{month.zfill(2)}/{year}", "%d/%m/%Y")
            return parsed.date().isoformat()
        except ValueError:
            return None

    def _complete_year(self, partial_year: str, text: str, end_index: int) -> str:
        year = partial_year
        idx = end_index
        while len(year) < 4 and idx < len(text) and text[idx].isdigit():
            year += text[idx]
            idx += 1
        return year

    def _normalize_whitespace(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _is_header_line(self, line: str) -> bool:
        keywords = (
            "republica",
            "federativa",
            "brasil",
            "carteira",
            "governo",
            "qr",
            "documento",
            "doc.",
            "doc",
            "proibido",
        )
        lowered = line.lower()
        return any(keyword in lowered for keyword in keywords)

    def _contains_digits(self, value: str) -> bool:
        return any(char.isdigit() for char in value)

    def _looks_like_name(self, value: str) -> bool:
        tokens = value.split()
        return len(tokens) >= 2 and all(token.isalpha() for token in tokens)

    def _normalize_name(self, value: str) -> str:
        return " ".join(part.capitalize() for part in value.split())
