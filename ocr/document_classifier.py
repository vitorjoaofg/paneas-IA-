"""
Document type classifier for OCR results.

Detects document types based on text patterns and keywords.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Tuple


class DocumentType(str, Enum):
    """Supported document types."""

    CNH = "CNH"
    RG = "RG"
    CPF = "CPF"
    NOTA_FISCAL = "NOTA_FISCAL"
    RECIBO = "RECIBO"
    COMPROVANTE = "COMPROVANTE"
    GENERICO = "GENERICO"


@dataclass
class DocumentTypeResult:
    """Result of document type classification."""

    type: DocumentType
    confidence: float
    detected_by: str
    matched_patterns: List[str]


class DocumentClassifier:
    """
    Classifies documents based on text content patterns.

    Uses keyword matching and regex patterns to identify document types.
    """

    # Pattern definitions for each document type
    PATTERNS: Dict[DocumentType, Dict[str, any]] = {
        DocumentType.CNH: {
            "keywords": [
                "carteira nacional",
                "habilitação",
                "cnh",
                "categoria",
                "validade",
                "permissão",
                "condutor",
                "detran",
                "registro nacional",
            ],
            "required_count": 2,
            "weight": 1.0,
        },
        DocumentType.RG: {
            "keywords": [
                "identidade",
                "rg",
                "órgão expedidor",
                "naturalidade",
                "filiação",
                "data de nascimento",
                "doc identidade",
                "carteira de identidade",
            ],
            "required_count": 2,
            "weight": 1.0,
        },
        DocumentType.CPF: {
            "keywords": [
                "cadastro de pessoa física",
                "cpf",
                "situação cadastral",
                "receita federal",
                "número de inscrição",
            ],
            "required_count": 2,
            "weight": 1.0,
            "regex": [
                r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',  # CPF format
            ],
        },
        DocumentType.NOTA_FISCAL: {
            "keywords": [
                "nota fiscal",
                "nf-e",
                "nfe",
                "danfe",
                "icms",
                "valor total",
                "cfop",
                "chave de acesso",
                "emitente",
                "destinatário",
                "natureza da operação",
            ],
            "required_count": 3,
            "weight": 1.2,
        },
        DocumentType.RECIBO: {
            "keywords": [
                "recibo",
                "recebi",
                "importância",
                "quantia",
                "a quantia de",
                "valor de",
                "por extenso",
            ],
            "required_count": 2,
            "weight": 0.9,
        },
        DocumentType.COMPROVANTE: {
            "keywords": [
                "comprovante",
                "transação",
                "pagamento",
                "pix",
                "transferência",
                "débito",
                "crédito",
                "agência",
                "conta",
                "banco",
            ],
            "required_count": 2,
            "weight": 0.8,
        },
    }

    def __init__(self):
        """Initialize the classifier."""
        pass

    def classify(self, text: str) -> DocumentTypeResult:
        """
        Classify document type based on text content.

        Args:
            text: Full text extracted from document

        Returns:
            DocumentTypeResult with type, confidence, and matched patterns
        """
        if not text or len(text.strip()) < 10:
            return DocumentTypeResult(
                type=DocumentType.GENERICO,
                confidence=0.5,
                detected_by="fallback",
                matched_patterns=[],
            )

        # Normalize text for matching
        normalized_text = self._normalize_text(text)

        # Score each document type
        scores: List[Tuple[DocumentType, float, List[str]]] = []

        for doc_type, patterns in self.PATTERNS.items():
            score, matched = self._score_document_type(normalized_text, doc_type, patterns)
            if score > 0:
                scores.append((doc_type, score, matched))

        # Get best match
        if not scores:
            return DocumentTypeResult(
                type=DocumentType.GENERICO,
                confidence=0.6,
                detected_by="no_patterns_matched",
                matched_patterns=[],
            )

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        best_type, best_score, matched_patterns = scores[0]

        # Calculate confidence based on score and difference from second best
        confidence = min(best_score, 1.0)
        if len(scores) > 1:
            second_score = scores[1][1]
            score_diff = best_score - second_score
            # Boost confidence if there's clear winner
            if score_diff > 0.3:
                confidence = min(confidence + 0.1, 0.98)

        return DocumentTypeResult(
            type=best_type,
            confidence=confidence,
            detected_by="pattern_matching",
            matched_patterns=matched_patterns,
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for pattern matching."""
        # Convert to lowercase
        normalized = text.lower()
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove special characters but keep common punctuation
        normalized = re.sub(r'[^\w\s\.\-/]', ' ', normalized)
        return normalized.strip()

    def _score_document_type(
        self,
        text: str,
        doc_type: DocumentType,
        patterns: Dict[str, any],
    ) -> Tuple[float, List[str]]:
        """
        Calculate score for a specific document type.

        Args:
            text: Normalized document text
            doc_type: Document type to score
            patterns: Pattern configuration for this type

        Returns:
            Tuple of (score, matched_patterns)
        """
        keywords = patterns.get("keywords", [])
        required_count = patterns.get("required_count", 1)
        weight = patterns.get("weight", 1.0)
        regex_patterns = patterns.get("regex", [])

        matched_keywords = []
        keyword_score = 0.0

        # Check keyword matches
        for keyword in keywords:
            if keyword in text:
                matched_keywords.append(keyword)
                keyword_score += 1.0

        # Check regex patterns
        regex_matches = []
        for pattern in regex_patterns:
            if re.search(pattern, text):
                regex_matches.append(pattern)
                keyword_score += 0.5  # Regex match gives half point

        # Only consider if minimum keywords found
        if len(matched_keywords) < required_count:
            return 0.0, []

        # Calculate normalized score
        total_patterns = len(keywords) + len(regex_patterns)
        if total_patterns == 0:
            return 0.0, []

        # Normalize by total possible matches and apply weight
        normalized_score = (keyword_score / total_patterns) * weight

        # Boost score if more than required keywords found
        if len(matched_keywords) > required_count:
            boost = min((len(matched_keywords) - required_count) * 0.1, 0.3)
            normalized_score += boost

        all_matched = matched_keywords + [f"regex:{p}" for p in regex_matches]

        return normalized_score, all_matched


def classify_document(text: str) -> DocumentTypeResult:
    """
    Convenience function to classify a document.

    Args:
        text: Document text to classify

    Returns:
        DocumentTypeResult with classification
    """
    classifier = DocumentClassifier()
    return classifier.classify(text)
