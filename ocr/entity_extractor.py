"""
Entity extractor for OCR results.

Extracts structured entities like CPF, CNPJ, dates, money values, etc.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Tuple


class EntityType(str, Enum):
    """Supported entity types."""

    CPF = "CPF"
    CNPJ = "CNPJ"
    DATE = "DATE"
    MONEY = "MONEY"
    CEP = "CEP"
    PHONE = "PHONE"
    EMAIL = "EMAIL"


@dataclass
class ExtractedEntity:
    """Represents an extracted entity from text."""

    type: EntityType
    value: str  # Normalized value
    raw_value: str  # As it appears in text
    confidence: float
    position: Optional[Dict[str, int]] = None  # {char_start, char_end, block_index}
    validated: bool = False


class EntityExtractor:
    """
    Extracts structured entities from text.

    Supports CPF, CNPJ, dates, monetary values, CEP, phone, and email.
    """

    # Regex patterns for entity extraction
    PATTERNS = {
        EntityType.CPF: [
            r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b',  # XXX.XXX.XXX-XX or XXXXXXXXXXX
        ],
        EntityType.CNPJ: [
            r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b',  # XX.XXX.XXX/XXXX-XX
        ],
        EntityType.DATE: [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # DD/MM/YYYY or DD-MM-YYYY
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY-MM-DD
        ],
        EntityType.MONEY: [
            r'R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?',  # R$ 1.234,56
            r'\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:reais?|R\$)',  # 1.234,56 reais
        ],
        EntityType.CEP: [
            r'\b\d{5}-?\d{3}\b',  # XXXXX-XXX
        ],
        EntityType.PHONE: [
            r'\(?\d{2}\)?\s*\d{4,5}-?\d{4}\b',  # (XX) XXXXX-XXXX
            r'\b\d{2}\s*\d{4,5}-?\d{4}\b',  # XX XXXXX-XXXX
        ],
        EntityType.EMAIL: [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ],
    }

    def __init__(self):
        """Initialize the entity extractor."""
        pass

    def extract(self, text: str, blocks: Optional[List[Dict]] = None) -> List[ExtractedEntity]:
        """
        Extract all entities from text.

        Args:
            text: Full text to extract entities from
            blocks: Optional list of OCR blocks for position tracking

        Returns:
            List of extracted entities
        """
        if not text:
            return []

        entities = []

        # Extract each entity type
        entities.extend(self._extract_cpf(text))
        entities.extend(self._extract_cnpj(text))
        entities.extend(self._extract_dates(text))
        entities.extend(self._extract_money(text))
        entities.extend(self._extract_cep(text))
        entities.extend(self._extract_phone(text))
        entities.extend(self._extract_email(text))

        # Deduplicate and sort by position
        entities = self._deduplicate_entities(entities)
        entities.sort(key=lambda e: e.position['char_start'] if e.position else 0)

        return entities

    def _extract_cpf(self, text: str) -> List[ExtractedEntity]:
        """Extract and validate CPF numbers."""
        entities = []
        for pattern in self.PATTERNS[EntityType.CPF]:
            for match in re.finditer(pattern, text):
                raw_value = match.group()
                # Normalize: remove punctuation
                normalized = re.sub(r'[^\d]', '', raw_value)

                if len(normalized) == 11:
                    # Validate CPF
                    is_valid = self._validate_cpf(normalized)
                    confidence = 0.95 if is_valid else 0.70

                    entities.append(ExtractedEntity(
                        type=EntityType.CPF,
                        value=normalized,
                        raw_value=raw_value,
                        confidence=confidence,
                        position={'char_start': match.start(), 'char_end': match.end()},
                        validated=is_valid,
                    ))

        return entities

    def _extract_cnpj(self, text: str) -> List[ExtractedEntity]:
        """Extract and validate CNPJ numbers."""
        entities = []
        for pattern in self.PATTERNS[EntityType.CNPJ]:
            for match in re.finditer(pattern, text):
                raw_value = match.group()
                # Normalize: remove punctuation
                normalized = re.sub(r'[^\d]', '', raw_value)

                if len(normalized) == 14:
                    # Validate CNPJ
                    is_valid = self._validate_cnpj(normalized)
                    confidence = 0.95 if is_valid else 0.70

                    entities.append(ExtractedEntity(
                        type=EntityType.CNPJ,
                        value=normalized,
                        raw_value=raw_value,
                        confidence=confidence,
                        position={'char_start': match.start(), 'char_end': match.end()},
                        validated=is_valid,
                    ))

        return entities

    def _extract_dates(self, text: str) -> List[ExtractedEntity]:
        """Extract dates in various formats."""
        entities = []
        for pattern in self.PATTERNS[EntityType.DATE]:
            for match in re.finditer(pattern, text):
                raw_value = match.group()
                # Try to parse and normalize
                normalized, is_valid = self._parse_date(raw_value)

                if normalized:
                    confidence = 0.90 if is_valid else 0.70
                    entities.append(ExtractedEntity(
                        type=EntityType.DATE,
                        value=normalized,
                        raw_value=raw_value,
                        confidence=confidence,
                        position={'char_start': match.start(), 'char_end': match.end()},
                        validated=is_valid,
                    ))

        return entities

    def _extract_money(self, text: str) -> List[ExtractedEntity]:
        """Extract monetary values."""
        entities = []
        for pattern in self.PATTERNS[EntityType.MONEY]:
            for match in re.finditer(pattern, text):
                raw_value = match.group()
                # Normalize to float value
                normalized = self._parse_money(raw_value)

                if normalized:
                    entities.append(ExtractedEntity(
                        type=EntityType.MONEY,
                        value=normalized,
                        raw_value=raw_value,
                        confidence=0.92,
                        position={'char_start': match.start(), 'char_end': match.end()},
                        validated=True,
                    ))

        return entities

    def _extract_cep(self, text: str) -> List[ExtractedEntity]:
        """Extract CEP (postal code)."""
        entities = []
        for pattern in self.PATTERNS[EntityType.CEP]:
            for match in re.finditer(pattern, text):
                raw_value = match.group()
                # Normalize: XXXXX-XXX format
                normalized = re.sub(r'[^\d]', '', raw_value)
                if len(normalized) == 8:
                    formatted = f"{normalized[:5]}-{normalized[5:]}"
                    entities.append(ExtractedEntity(
                        type=EntityType.CEP,
                        value=formatted,
                        raw_value=raw_value,
                        confidence=0.88,
                        position={'char_start': match.start(), 'char_end': match.end()},
                        validated=True,
                    ))

        return entities

    def _extract_phone(self, text: str) -> List[ExtractedEntity]:
        """Extract phone numbers."""
        entities = []
        for pattern in self.PATTERNS[EntityType.PHONE]:
            for match in re.finditer(pattern, text):
                raw_value = match.group()
                # Normalize: remove punctuation
                normalized = re.sub(r'[^\d]', '', raw_value)

                if len(normalized) in [10, 11]:  # Valid phone lengths
                    entities.append(ExtractedEntity(
                        type=EntityType.PHONE,
                        value=normalized,
                        raw_value=raw_value,
                        confidence=0.85,
                        position={'char_start': match.start(), 'char_end': match.end()},
                        validated=True,
                    ))

        return entities

    def _extract_email(self, text: str) -> List[ExtractedEntity]:
        """Extract email addresses."""
        entities = []
        for pattern in self.PATTERNS[EntityType.EMAIL]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_value = match.group()
                # Normalize: lowercase
                normalized = raw_value.lower()

                entities.append(ExtractedEntity(
                    type=EntityType.EMAIL,
                    value=normalized,
                    raw_value=raw_value,
                    confidence=0.90,
                    position={'char_start': match.start(), 'char_end': match.end()},
                    validated=True,
                ))

        return entities

    def _validate_cpf(self, cpf: str) -> bool:
        """Validate CPF using check digits."""
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        # Calculate first check digit
        sum_val = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digit1 = 11 - (sum_val % 11)
        digit1 = 0 if digit1 >= 10 else digit1

        # Calculate second check digit
        sum_val = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digit2 = 11 - (sum_val % 11)
        digit2 = 0 if digit2 >= 10 else digit2

        return int(cpf[9]) == digit1 and int(cpf[10]) == digit2

    def _validate_cnpj(self, cnpj: str) -> bool:
        """Validate CNPJ using check digits."""
        if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
            return False

        # First check digit
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        sum_val = sum(int(cnpj[i]) * weights1[i] for i in range(12))
        digit1 = 11 - (sum_val % 11)
        digit1 = 0 if digit1 >= 10 else digit1

        # Second check digit
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        sum_val = sum(int(cnpj[i]) * weights2[i] for i in range(13))
        digit2 = 11 - (sum_val % 11)
        digit2 = 0 if digit2 >= 10 else digit2

        return int(cnpj[12]) == digit1 and int(cnpj[13]) == digit2

    def _parse_date(self, date_str: str) -> Tuple[Optional[str], bool]:
        """
        Parse date string to ISO format.

        Returns:
            Tuple of (iso_date_string, is_valid)
        """
        # Try different date formats
        formats = [
            '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
            '%Y-%m-%d', '%Y/%m/%d',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Check if date is reasonable (not in distant past/future)
                current_year = datetime.now().year
                if 1900 <= dt.year <= current_year + 50:
                    return dt.strftime('%Y-%m-%d'), True
            except ValueError:
                continue

        return None, False

    def _parse_money(self, money_str: str) -> Optional[str]:
        """Parse monetary value to normalized string."""
        # Remove currency symbols and text
        cleaned = re.sub(r'R\$|reais?', '', money_str, flags=re.IGNORECASE).strip()

        # Replace thousand separator and decimal comma
        cleaned = cleaned.replace('.', '').replace(',', '.')

        try:
            value = float(cleaned)
            return f"{value:.2f}"
        except ValueError:
            return None

    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove duplicate entities (same value and type)."""
        seen = set()
        unique = []

        for entity in entities:
            key = (entity.type, entity.value)
            if key not in seen:
                seen.add(key)
                unique.append(entity)

        return unique


def extract_entities(text: str, blocks: Optional[List[Dict]] = None) -> List[ExtractedEntity]:
    """
    Convenience function to extract entities from text.

    Args:
        text: Text to extract entities from
        blocks: Optional OCR blocks for position tracking

    Returns:
        List of extracted entities
    """
    extractor = EntityExtractor()
    return extractor.extract(text, blocks)
