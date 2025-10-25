import re
from typing import Dict


class PIIMasker:
    PATTERNS = {
        "cpf": re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
        "cnpj": re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"),
        "phone": re.compile(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"),
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "credit_card": re.compile(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"),
    }

    @classmethod
    def mask_text(cls, text: str) -> str:
        masked = text
        for pii_type, pattern in cls.PATTERNS.items():
            if pii_type == "email":
                masked = pattern.sub(
                    lambda match: (
                        match.group(0).split("@")[0][:2]
                        + "***@"
                        + match.group(0).split("@")[1]
                    ),
                    masked,
                )
            elif pii_type == "cpf":
                masked = pattern.sub("***.***.***.XX", masked)
            elif pii_type == "cnpj":
                masked = pattern.sub("**.***.***/****-**", masked)
            elif pii_type == "phone":
                masked = pattern.sub("(XX) XXXX-XXXX", masked)
            elif pii_type == "credit_card":
                masked = pattern.sub("XXXX-XXXX-XXXX-XXXX", masked)
        return masked

    @classmethod
    def mask_payload(cls, payload: Dict) -> Dict:
        sanitized = {}
        for key, value in payload.items():
            if isinstance(value, str):
                sanitized[key] = cls.mask_text(value)
            else:
                sanitized[key] = value
        return sanitized
