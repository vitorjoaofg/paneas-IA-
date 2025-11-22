#!/usr/bin/env python3
"""
Consolida métricas detalhadas das transcrições IZZI, detecta divergências
em relação às marcações fornecidas e gera um JSON final com mais de 40
indicadores agregados além do detalhamento por chamada.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Tuple, Set

from transformers import pipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTION_DIR = BASE_DIR
METADATA_FILE = os.path.join(TRANSCRIPTION_DIR, "metadata.csv")
OUTPUT_FILE = os.path.join(TRANSCRIPTION_DIR, "full_analysis.json")


def load_metadata(path: str) -> Dict[str, dict]:
    with open(path, newline="") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        metadata = {
            row["file_id"].replace(".WAV", ""): {
                key: (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
            }
            for row in reader
        }
    return metadata


def list_transcription_files(directory: str) -> List[str]:
    return sorted(
        [
            fname
            for fname in os.listdir(directory)
            if fname.endswith(".json")
            and not fname.endswith(".analysis.json")
            and fname not in {"global_metrics.json", "full_analysis.json"}
        ]
    )


def tokenize_words(text: str) -> List[str]:
    return re.findall(r"\b[\wáéíóúüñ]+\b", text.lower(), flags=re.UNICODE)


def clean_text_value(raw: str) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.lower() in {"null", "n/a", "na", "-"}:
        return None
    return text


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    text = value.strip()
    if not text:
        return default
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return default


def chunk_text(text: str, max_words: int = 180, max_chunks: int = 3) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    for idx in range(0, len(words), max_words):
        chunk_words = words[idx: idx + max_words]
        chunk = " ".join(chunk_words).strip()
        if chunk:
            chunks.append(chunk)
        if len(chunks) >= max_chunks:
            break
    return chunks


@dataclass
class SentimentResult:
    score: float
    label: str


class SentimentAnalyzer:
    def __init__(self) -> None:
        self._pipeline = pipeline(
            "sentiment-analysis",
            model="nlptown/bert-base-multilingual-uncased-sentiment",
        )

    @staticmethod
    def _label_from_score(score: float) -> str:
        if score >= 0.25:
            return "positive"
        if score <= -0.25:
            return "negative"
        return "neutral"

    @staticmethod
    def _normalize_label(label: str) -> int:
        # Labels like "1 star", "5 stars"
        match = re.search(r"\d", label)
        stars = int(match.group()) if match else 3
        return stars

    def run(self, text: str) -> SentimentResult:
        if not text.strip():
            return SentimentResult(0.0, "neutral")
        chunks = chunk_text(text)
        if not chunks:
            return SentimentResult(0.0, "neutral")
        outputs = self._pipeline(chunks)
        total = 0.0
        for out in outputs:
            stars = self._normalize_label(out["label"])
            # map 1..5 stars to [-1, 1]
            normalized = (stars - 3) / 2.0
            total += normalized
        avg = total / len(outputs)
        return SentimentResult(round(avg, 4), self._label_from_score(avg))


def detect_keywords(text: str, patterns: Iterable[str]) -> bool:
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in patterns)


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_statistics(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"avg": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
    avg = statistics.mean(values)
    median = statistics.median(values)
    min_val = min(values)
    max_val = max(values)
    std_val = statistics.pstdev(values) if len(values) > 1 else 0.0
    return {
        "avg": round(avg, 4),
        "median": round(median, 4),
        "min": round(min_val, 4),
        "max": round(max_val, 4),
        "std": round(std_val, 4),
    }


VOICEMAIL_KEYWORDS = [
    "buzón", "buzon", "mensaje después del tono", "deje su mensaje",
    "grabadora", "casilla de voz", "deja tu mensaje", "tone señal",
]
FAX_KEYWORDS = [
    "fax", "contestadora fax", "tono de fax", "señal de fax",
]
INVALID_NUMBER_KEYWORDS = [
    "número que marcó no existe",
    "número marcado no existe",
    "número no está en servicio",
    "número no existe",
    "numero que marco no existe",
    "numero marcado no existe",
]
SUSPENDED_KEYWORDS = [
    "servicio ha sido suspendido",
    "servicio fue suspendido",
    "línea ha sido suspendida",
    "linea ha sido suspendida",
]
ORDER_KEYWORDS = [
    "orden abierta",
    "ordenes abiertas",
    "cuenta con orden abierta",
]

HOLD_KEYWORDS = [
    "por favor, continúe en la línea",
    "por favor, continue en la linea",
    "estaremos con usted",
    "permanezca en la línea",
    "permanezca en la linea",
    "en un minuto más",
    "en un minuto mas",
    "gracias por tu espera",
    "gracias por su espera",
    "gracias por su paciencia",
    "por favor, no cuelgue",
    "no cuelgue",
    "lo atenderemos en breve",
    "atenderemos su llamada",
    "continúe en la línea",
    "continue en la linea",
]

AGENT_TALK_THRESHOLD = 5.0
CUSTOMER_TALK_THRESHOLD = 5.0
AGENT_WORD_THRESHOLD = 18
CUSTOMER_WORD_THRESHOLD = 18
MIN_DURATION_FOR_SPEECH_RATE = 3.0
SENTIMENT_WORD_THRESHOLD = 10

AGENT_LANGUAGE_PATTERNS = [
    "no se preocupe",
    "permítame",
    "permitame",
    "lo pondremos",
    "lo canalizo",
    "la canalizo",
    "lo transfiero",
    "quedo atenta",
    "quedo atento",
    "con gusto",
    "le comento",
    "le informo",
    "le indico",
    "en comentarios",
    "comentarios para que",
    "estoy verificando",
    "estamos verificando",
    "muchísimas gracias",
    "muchisimas gracias",
    "gracias por comunicarse",
    "gracias por tu tiempo",
    "gracias por su tiempo",
    "me puede apoyar",
    "me podrías apoyar",
    "me podria apoyar",
    "me ayudas con",
    "le apoyo",
    "le puedo ayudar",
    "puede confirmarme",
    "puede proporcionarme",
    "me confirma",
    "puede indicarme",
    "colonia o su privada",
    "me comparte su calle",
    "le transfiero",
    "permanezca en la línea",
    "permanezca en la linea",
    "en que colonia",
    "quedo a sus órdenes",
    "quedo a sus ordenes",
    "quedo pendiente",
    "cualquier cosa",
    "con gusto le apoyo",
    "en seguida",
    "será un placer",
    "sera un placer",
]

AGENT_LANGUAGE_STRONG = [
    "lo pondremos en los comentarios",
    "lo registramos en comentarios",
    "gracias por llamar",
    "que tenga excelente día",
    "que tenga excelente dia",
    "que tenga buen día",
    "que tenga buen dia",
    "quedo atenta a sus comentarios",
]

def compute_speech_rate(words: int, talk_time_seconds: float) -> float:
    if talk_time_seconds < MIN_DURATION_FOR_SPEECH_RATE or words <= 0:
        return 0.0
    rate = words / (talk_time_seconds / 60.0)
    return round(min(rate, 240.0), 4)


def detect_agent_language(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    matches = sum(1 for keyword in AGENT_LANGUAGE_PATTERNS if keyword in lowered)
    if matches >= 2:
        return True
    if any(phrase in lowered for phrase in AGENT_LANGUAGE_STRONG):
        return True
    return False


SPANISH_STOPWORDS = {
    "de",
    "la",
    "el",
    "en",
    "y",
    "a",
    "o",
    "que",
    "como",
    "para",
    "por",
    "con",
    "su",
    "sus",
    "tu",
    "te",
    "lo",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "es",
    "son",
    "se",
    "ya",
    "no",
    "si",
    "sí",
    "mais",
    "mas",
    "pero",
    "porque",
    "porqué",
    "porque",
    "del",
    "al",
    "sobre",
    "muy",
    "muito",
    "esta",
    "este",
    "esto",
    "ese",
    "esa",
    "eso",
    "me",
    "mi",
    "mis",
    "nos",
    "nuestro",
    "nuestra",
    "usted",
    "ustedes",
    "ella",
    "ellas",
    "ellos",
    "tambien",
    "también",
    "ademas",
    "además",
    "solo",
    "sólo",
    "pois",
    "entao",
    "então",
    "do",
    "da",
    "dos",
    "das",
    "lo",
    "la",
    "que",
    "hay",
    "tiene",
    "tenemos",
    "tan",
    "esto",
    "esta",
    "estas",
    "estar",
    "hola",
    "momento",
    "gracias",
    "buenas",
    "buenos",
    "tardes",
    "tarde",
    "dias",
    "días",
    "favor",
    "gusto",
    "espera",
    "mom",
    "pues",
    "ok",
}

SCRIPT_KEYWORD_HINTS = [
    "oferta",
    "promocion",
    "promoción",
    "asesor",
    "asesora",
    "exclusiva",
    "servicio",
    "plan",
    "paquete",
    "internet",
    "telefonia",
    "telefonía",
    "video",
    "beneficio",
    "descuento",
    "gratis",
    "contratar",
    "contratacion",
    "contratación",
    "portabilidad",
    "megas",
]

OFFER_CORE_KEYWORDS = [
    "internet",
    "television",
    "televisión",
    "tv",
    "telefonia",
    "telefonía",
    "wifi",
    "paquete",
    "residencial",
    "oferta",
    "promocion",
    "promoción",
    "instalacion",
    "instalación",
    "velocidad",
    "megas",
    "canales",
    "vix",
    "premium",
    "350",
    "pesos",
    "fibra",
]

SOURCE_AWARENESS_PATTERNS = [
    "porque dejaste tus datos",
    "porque dejaste tus datos",
    "dejaste tus datos",
    "te registraste",
    "registraste tus datos",
    "te interesaste",
    "mostraste interés",
    "mostraste interes",
    "solicitaste información",
    "solicitaste informacion",
    "solicitud",
    "seguimiento a tu solicitud",
    "por la oferta residencial",
    "de la oferta residencial",
    "derivado de tu registro",
    "derivado del registro",
    "campaña digital",
    "campana digital",
    "interesado en la oferta",
    "interesada en la oferta",
    "contacto porque pediste",
    "porque pediste información",
    "porque pediste informacion",
    "porque pediste datos",
    "gracias por dejarnos tus datos",
]

SOURCE_AWARENESS_STRONG = [
    "como te comentó el bot",
    "como te comento el bot",
    "como te comentó nuestro bot",
    "te transfirió el bot",
    "te transfirio el bot",
    "sigues con nosotros desde el bot",
    "vienes del bot",
    "te marcamos del bot",
    "porque interactuaste con el bot",
    "porque pasaste por el bot",
    "esta llamada viene del bot",
]

SALES_KEYWORDS = {
    "price": [
        "$",
        "pesos",
        "mensual",
        "mensuales",
        "por mes",
        "por mes",
        "precio",
        "costo",
        "cuesta",
        "pagarias",
        "pagarías",
        "pagarias",
        "pago mensual",
        "promoción de",
        "promocion de",
        "promo de",
    ],
    "benefits": [
        "beneficio",
        "beneficios",
        "instalacion",
        "instalación",
        "velocidad",
        "megas",
        "television",
        "televisión",
        "canales",
        "wifi",
        "modem",
        "router",
        "telefonia",
        "telefonía",
        "servicio",
        "streaming",
        "premium",
        "paquete",
        "fibra",
        "ilimitado",
        "vix",
        "contenido",
    ],
    "loyalty": [
        "fidelidad",
        "plazo",
        "plazo forzoso",
        "permanencia",
        "contrato",
        "meses",
        "12 meses",
        "doce meses",
        "sin costo de instalación",
        "sin costo de instalacion",
        "sin permanencia",
        "sin plazo forzoso",
        "plazo mínimo",
        "plazo minimo",
    ],
    "differentials": [
        "mejor que",
        "comparado con",
        "contra la competencia",
        "versus",
        "a diferencia de",
        "diferencial",
        "ventaja",
        "único",
        "unico",
        "exclusivo",
        "ranking",
        "premio",
        "reconocida",
        "estudio",
        "investigacion",
        "investigación",
        "mejor red",
        "mejor cobertura",
        "estamos certificados",
    ],
}

FOLLOW_UP_PATTERNS_AGENT = [
    "te puedo llamar de nuevo",
    "te puedo marcar más tarde",
    "te puedo marcar mas tarde",
    "te llamamos de nuevo",
    "te marcamos de nuevo",
    "te vuelvo a llamar",
    "te vuelvo a marcar",
    "le vuelvo a llamar",
    "le vuelvo a marcar",
    "agendamos una llamada",
    "agendamos una cita",
    "agendamos visita",
    "agendar una llamada",
    "agendar una cita",
    "agendar visita",
    "programo una llamada",
    "programo una visita",
    "coordino que te llamen",
    "coordino otra llamada",
    "te contacto más tarde",
    "te contacto mas tarde",
    "te contacto mañana",
    "te marcamos mañana",
    "te marcamos más tarde",
    "te marcamos mas tarde",
]

FOLLOW_UP_PATTERNS_CUSTOMER = [
    "llamame despues",
    "llámame después",
    "llamame luego",
    "llámame luego",
    "llamame mañana",
    "llámame mañana",
    "marquenme mañana",
    "marquenme mas tarde",
    "marquenme más tarde",
    "marquen después",
    "me vuelve a llamar",
    "me vuelve a marcar",
    "vuelvan a llamarme",
    "vuelvan a marcarme",
    "cuando puedan llamarme",
    "necesito pensarlo",
    "tengo que compararlo",
    "llamen más tarde",
    "llamen mas tarde",
    "llamen otro dia",
    "llamen otro día",
]

OBJECTION_KEYWORDS = [
    "muy caro",
    "caro",
    "no me interesa",
    "no quiero",
    "no necesito",
    "ya tengo",
    "ya contamos",
    "tengo servicio",
    "tengo un plan",
    "el servicio es malo",
    "se cae",
    "falla",
    "no funciona",
    "muchas llamadas",
    "muchas veces",
    "no confio",
    "no confío",
    "no me convence",
    "su internet es malo",
    "su servicio es malo",
]

COUNTER_ARGUMENT_KEYWORDS = [
    "pero",
    "sin embargo",
    "de hecho",
    "contamos con",
    "ofrecemos",
    "lo que pasa",
    "lo que podemos",
    "tenemos",
    "garantizamos",
    "para que no te preocupes",
    "para que esté tranquilo",
    "para que este tranquilo",
    "para que no se preocupe",
    "premiada",
    "reconocida",
    "mejor calificada",
    "mejor red",
    "mejor cobertura",
    "investigación",
    "investigacion",
]

ASSURANCE_KEYWORDS = [
    "no te preocupes",
    "no se preocupe",
    "te garantizamos",
    "le garantizamos",
    "estamos certificados",
    "tenemos garantía",
    "tenemos garantia",
    "cubrimos",
    "respaldamos",
    "te aseguro",
]

CUSTOMER_ANGER_PATTERNS = [
    "deja de llamarme",
    "dejen de llamarme",
    "no me vuelvan a llamar",
    "no me vuelvan a marcar",
    "quiten mi numero",
    "quiten mi número",
    "quita mi numero",
    "quita mi número",
    "borren mi numero",
    "borren mi número",
    "ya basta de llamadas",
    "estoy harto",
    "estoy harta",
    "estoy molesto",
    "estoy molesta",
    "me tienen cansado",
    "me tienen cansada",
    "ya no quiero llamadas",
    "no quiero mas llamadas",
    "no quiero más llamadas",
    "ya no marquen",
    "ya no me marquen",
    "bloqueen mi numero",
    "bloqueen mi número",
    "saquen mi numero",
    "saquen mi número",
    "quiten mi telefono",
    "insistan mas",
    "insistan más",
]


def extract_keywords(text: str) -> List[str]:
    if not text:
        return []
    tokens = tokenize_words(text.lower())
    return [token for token in tokens if len(token) > 2 and token not in SPANISH_STOPWORDS]


def extract_numbers(text: str) -> Set[str]:
    if not text:
        return set()
    return {
        match.replace(",", ".")
        for match in re.findall(r"\b\d+(?:[.,]\d+)?\b", text.lower())
    }


def assemble_script_reference(
    segments: List[dict],
    script_meta: str | None,
    product_meta: str | None,
    first_agent_start: float,
    *,
    contact_type: str | None = None,
) -> str:
    parts: List[str] = []
    inbound = False
    if contact_type:
        lowered = contact_type.lower()
        inbound = any(keyword in lowered for keyword in ("recept", "inbound", "entrante"))

    if script_meta:
        cleaned_script = script_meta.strip()
        if cleaned_script and (not inbound or len(cleaned_script.split()) > 3):
            parts.append(cleaned_script)
    if product_meta and not inbound:
        parts.append(product_meta)

    pre_agent_texts: List[str] = []
    limit_segments = 0
    if not inbound:
        for seg in segments:
            text = seg.get("text", "")
            if not text:
                continue
            start = float(seg.get("start", 0.0))
            if first_agent_start >= 0 and start >= first_agent_start - 0.01:
                break
            pre_agent_texts.append(text)
            limit_segments += 1
            if limit_segments >= 20:
                break
    if pre_agent_texts:
        parts.append(" ".join(pre_agent_texts))
    return " ".join(parts).strip()


def compute_script_alignment(
    follow_text: str,
    script_text: str,
    *,
    product_meta: str | None = None,
    contact_type: str | None = None,
) -> Dict[str, object]:
    follow_tokens = set(extract_keywords(follow_text))
    script_tokens = set(extract_keywords(script_text))

    script_offer_tokens = {token for token in script_tokens if token in OFFER_CORE_KEYWORDS}
    script_hint_tokens = {token for token in script_tokens if token in SCRIPT_KEYWORD_HINTS}
    script_numbers = extract_numbers(script_text)

    follow_offer_tokens = {token for token in follow_tokens if token in OFFER_CORE_KEYWORDS}
    follow_hint_tokens = {token for token in follow_tokens if token in SCRIPT_KEYWORD_HINTS}
    follow_numbers = extract_numbers(follow_text)

    core_match = script_offer_tokens & follow_offer_tokens
    hint_match = script_hint_tokens & follow_hint_tokens
    number_match = script_numbers & follow_numbers
    direct_match = script_tokens & follow_tokens

    core_ratio = safe_div(len(core_match), len(script_offer_tokens)) if script_offer_tokens else 0.0
    hint_ratio = safe_div(len(hint_match), len(script_hint_tokens)) if script_hint_tokens else 0.0

    follow_lower = follow_text.lower()
    script_lower = script_text.lower()
    oferta_flag = "oferta" in follow_lower
    promoc_flag = any(token in follow_lower for token in ("promocion", "promoción", "promocion", "promoc"))
    beneficio_flag = "beneficio" in follow_lower or "beneficios" in follow_lower

    number_pattern = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mega|megas|mbps|gig|gbps|gigas?)?\b")
    speed_pattern = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mega|megas|mbps|gigabits?|gbps)\b")
    price_terms = ("pesos", "$", "mensual", "mensuales", "mes", "cuota", "pago", "cost", "tarifa")
    product_terms = (
        "internet",
        "telefonia",
        "telefonía",
        "linea",
        "línea",
        "telefono",
        "teléfono",
        "tv",
        "television",
        "video",
        "paquete",
        "servicio",
        "triple play",
        "doble play",
        "portabilidad",
        "fibra",
    )
    addon_terms = ("vix", "premium", "app", "apple tv", "vixt", "disney", "hbo", "netflix")
    install_terms = ("instalacion", "instalación", "sin costo", "sin costo de instalacion", "gratis la instalacion")

    contact_type_lower = (contact_type or "").lower()
    is_inbound = any(keyword in contact_type_lower for keyword in ("recept", "inbound", "entrante"))

    price_mentions = bool(number_match) or any(term in follow_lower for term in price_terms)
    speed_mentions = bool(speed_pattern.search(follow_lower))
    product_mentions = any(term in follow_lower for term in product_terms)
    promo_mentions = promoc_flag or oferta_flag or beneficio_flag or "gratis" in follow_lower or "descuento" in follow_lower or "bono" in follow_lower
    addon_mentions = any(term in follow_lower for term in addon_terms)
    install_mentions = any(term in follow_lower for term in install_terms)
    portability_mentions = "portabilidad" in follow_lower or "portacion" in follow_lower or "portación" in follow_lower

    agent_offer_strength = sum(
        1
        for flag in (
            product_mentions,
            promo_mentions,
            price_mentions,
            speed_mentions,
            addon_mentions,
            install_mentions,
            portability_mentions,
        )
        if flag
    )

    numeric_boost = 1.0 if number_match else 0.0
    score = min(
        1.0,
        0.5 * core_ratio
        + 0.3 * hint_ratio
        + 0.15 * numeric_boost
        + 0.05 * safe_div(len(follow_offer_tokens), max(1, len(script_offer_tokens))),
    )
    if agent_offer_strength:
        score = min(1.0, score + 0.2 * agent_offer_strength / 4.0)

    if not follow_tokens or (not script_tokens and not (script_offer_tokens or script_hint_tokens or script_numbers)):
        label = "unknown"
    else:
        if (
            core_ratio >= 0.6
            or (len(core_match) >= 2 and (len(hint_match) >= 1 or number_match))
            or (len(core_match) >= 1 and numeric_boost and (promoc_flag or oferta_flag or beneficio_flag))
        ):
            label = "aligned"
        elif (
            core_ratio >= 0.2
            or len(core_match) >= 1
            or len(hint_match) >= 1
            or number_match
            or promoc_flag
            or oferta_flag
        ):
            label = "partial"
        else:
            label = "off_script"

    script_expectation = bool(
        script_offer_tokens
        or script_hint_tokens
        or "oferta" in script_lower
        or "promoc" in script_lower
        or (product_meta and product_meta.strip())
    )
    if is_inbound:
        script_expectation = bool(product_meta and product_meta.strip() and len(product_meta.strip().split()) > 2)

    if script_expectation:
        if product_mentions and (price_mentions or promo_mentions) and (speed_mentions or addon_mentions or portability_mentions):
            label = "aligned"
        elif product_mentions and (price_mentions or promo_mentions or speed_mentions or addon_mentions):
            label = "partial" if label != "aligned" else label
        elif product_mentions and label == "off_script":
            label = "partial"
        elif agent_offer_strength >= 3 and label != "aligned":
            label = "aligned"
        elif agent_offer_strength >= 2 and label == "off_script":
            label = "partial"
    else:
        if is_inbound and agent_offer_strength >= 2:
            label = "aligned"
        elif is_inbound and agent_offer_strength == 1 and label != "aligned":
            label = "partial"
        elif label != "aligned" and agent_offer_strength >= 3:
            label = "aligned"
        elif label == "off_script" and agent_offer_strength >= 2:
            label = "partial"
        elif agent_offer_strength == 0:
            label = "unknown"

    matched_keywords: List[str] = []
    for token in sorted(core_match):
        matched_keywords.append(token)
    for token in sorted(hint_match):
        if token not in matched_keywords:
            matched_keywords.append(token)
    for token in sorted(number_match):
        if token not in matched_keywords:
            matched_keywords.append(token)
    if len(matched_keywords) < 6:
        for token in sorted(direct_match):
            if token not in matched_keywords:
                matched_keywords.append(token)
            if len(matched_keywords) >= 6:
                break
    matched_keywords = matched_keywords[:6]

    total_reference = len(script_offer_tokens | script_hint_tokens | script_numbers)
    if total_reference == 0 and script_tokens:
        total_reference = len(script_tokens)

    hits_total = len(core_match) + len(hint_match) + len(number_match)

    topic_labels = [
        ("producto", product_mentions),
        ("promocion", promo_mentions),
        ("precio", price_mentions),
        ("velocidad", speed_mentions),
        ("addon", addon_mentions),
        ("instalacion", install_mentions),
        ("portabilidad", portability_mentions),
    ]

    if hits_total == 0 and agent_offer_strength > 0:
        hits_total = agent_offer_strength
        total_reference = max(total_reference, agent_offer_strength, len(topic_labels), 1)
        for label_name, flag in topic_labels:
            if flag and label_name not in matched_keywords:
                matched_keywords.append(label_name)
                if len(matched_keywords) >= 6:
                    break
    else:
        for label_name, flag in topic_labels:
            if flag and label_name not in matched_keywords and len(matched_keywords) < 6:
                matched_keywords.append(label_name)

    if agent_offer_strength > hits_total:
        hits_total = agent_offer_strength

    if label == "unknown":
        total_reference = hits_total
    else:
        total_reference = max(total_reference, hits_total, 1)

    return {
        "label": label,
        "score": round(score, 4),
        "hits": hits_total,
        "total": total_reference,
        "matched": matched_keywords,
    }


def detect_source_awareness(segments: List[dict], agent_text: str) -> Dict[str, object]:
    lowered = agent_text.lower()
    matches = [pattern for pattern in SOURCE_AWARENESS_PATTERNS if pattern in lowered]
    strong_matches = [pattern for pattern in SOURCE_AWARENESS_STRONG if pattern in lowered]
    level = 0
    if strong_matches:
        level = 2
    elif matches:
        level = 1
    if level == 0:
        # check earliest agent segments for explicit acknowledgment words
        agent_segments = [
            seg.get("text", "").lower()
            for seg in segments
            if seg.get("role") == "agent"
        ][:3]
        if any("bot" in text or "automat" in text for text in agent_segments):
            level = 1
            matches.append("bot")
    return {
        "detected": level > 0,
        "level": level,
        "matches": (strong_matches or matches)[:5],
    }


def evaluate_sales_pitch(agent_text: str) -> Dict[str, object]:
    lowered = agent_text.lower()
    detail = {}
    for key, patterns in SALES_KEYWORDS.items():
        hits = [pattern for pattern in patterns if pattern in lowered]
        detail[key] = hits
    topics = [key for key, hits in detail.items() if hits]
    score = len(topics)
    label = "weak"
    if "price" in topics and score >= 3:
        label = "satisfactory"
    elif "price" in topics and score >= 2:
        label = "nominal"
    elif score >= 2:
        label = "nominal"
    return {
        "score": score,
        "label": label,
        "topics": topics[:4],
    }


def detect_follow_up_commitment(segments: List[dict]) -> Dict[str, object]:
    conversational = [
        {"role": seg.get("role"), "text": (seg.get("text") or "").lower()}
        for seg in segments
        if seg.get("role") in {"agent", "customer"}
    ]
    if not conversational:
        return {"detected": False, "actor": None, "matches": []}
    tail = conversational[-6:]
    for seg in reversed(tail):
        patterns = (
            FOLLOW_UP_PATTERNS_AGENT if seg["role"] == "agent" else FOLLOW_UP_PATTERNS_CUSTOMER
        )
        hits = [pattern for pattern in patterns if pattern in seg["text"]]
        if hits:
            return {"detected": True, "actor": seg["role"], "matches": hits[:3]}
    return {"detected": False, "actor": None, "matches": []}


def detect_objection_handling(segments: List[dict]) -> Dict[str, object]:
    count = 0
    for index, segment in enumerate(segments):
        if segment.get("role") != "customer":
            continue
        customer_text = (segment.get("text") or "").lower()
        if not any(keyword in customer_text for keyword in OBJECTION_KEYWORDS):
            continue
        for follow_index in range(index + 1, min(len(segments), index + 4)):
            follow_segment = segments[follow_index]
            if follow_segment.get("role") != "agent":
                continue
            agent_text = (follow_segment.get("text") or "").lower()
            if any(keyword in agent_text for keyword in COUNTER_ARGUMENT_KEYWORDS) or any(
                keyword in agent_text for keyword in ASSURANCE_KEYWORDS
            ):
                count += 1
                break
    return {"detected": count > 0, "count": count}


def detect_customer_anger(customer_text: str, customer_sentiment: SentimentResult) -> Dict[str, object]:
    lowered = customer_text.lower()
    matches = [pattern for pattern in CUSTOMER_ANGER_PATTERNS if pattern in lowered]
    strong_negative = customer_sentiment.label == "negative" and customer_sentiment.score <= -0.4
    detected = bool(matches) or strong_negative and "llam" in lowered
    return {"detected": detected, "matches": matches[:4]}


def detect_agent_language(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    matches = sum(1 for keyword in AGENT_LANGUAGE_PATTERNS if keyword in lowered)
    if matches >= 2:
        return True
    if any(phrase in lowered for phrase in AGENT_LANGUAGE_STRONG):
        return True
    return False


def normalize_izzi_status(status: str) -> str:
    mapping = {
        "No Contesto": "no_contesto",
        "Buzon": "buzon",
        "Sin Audio": "sin_audio",
        "Fax/Contestadora": "fax_contestadora",
        "Telefono No Existe": "numero_inexistente",
        "Telefono Suspendido": "telefone_suspendido",
        "Clientes Con Ordenes Abiertas": "orden_aberta",
    }
    return mapping.get(status, "desconhecido")


def expected_actual_statuses(normalized_status: str) -> Tuple[str, ...]:
    mapping = {
        "no_contesto": (
            "ivr_sem_interacao",
            "conectado_sem_cliente",
            "cliente_interagiu_sem_agente",
            "buzon",
        ),
        "buzon": ("buzon", "fax_ou_contestadora"),
        "sin_audio": ("sem_audio",),
        "fax_contestadora": ("fax_ou_contestadora", "buzon"),
        "numero_inexistente": ("numero_inexistente",),
        "telefone_suspendido": ("telefone_suspendido",),
        "orden_aberta": ("dialogo_conectado", "conectado_sem_cliente"),
        "desconhecido": (
            "dialogo_conectado",
            "cliente_interagiu_sem_agente",
            "conectado_sem_cliente",
            "ivr_sem_interacao",
            "buzon",
            "fax_ou_contestadora",
            "sem_audio",
        ),
    }
    return mapping.get(normalized_status, tuple())


def classify_actual_status(
    word_count_total: int,
    talk_by_role: Dict[str, float],
    words_by_role: Dict[str, int],
    role_segments: Dict[str, int],
    duration_reference: float,
    transcript_text: str,
    keyword_flags: Dict[str, bool] | None = None,
    *,
    turn_count: int = 0,
    customer_after_agent: bool = False,
) -> str:
    flags = keyword_flags or {}
    voicemail_flag = flags.get("voicemail")
    invalid_number_flag = flags.get("invalid_number")
    suspended_flag = flags.get("suspended")
    fax_flag = flags.get("fax")
    order_flag = flags.get("order")
    agent_language_hint = flags.get("agent_language", False)
    hold_flag = flags.get("hold", False)

    if voicemail_flag is None:
        voicemail_flag = detect_keywords(transcript_text, VOICEMAIL_KEYWORDS)
    if invalid_number_flag is None:
        invalid_number_flag = detect_keywords(transcript_text, INVALID_NUMBER_KEYWORDS)
    if suspended_flag is None:
        suspended_flag = detect_keywords(transcript_text, SUSPENDED_KEYWORDS)
    if fax_flag is None:
        fax_flag = detect_keywords(transcript_text, FAX_KEYWORDS)
    if order_flag is None:
        order_flag = detect_keywords(transcript_text, ORDER_KEYWORDS)

    agent_talk = talk_by_role["agent"]
    customer_talk = talk_by_role["customer"]
    agent_words = words_by_role["agent"]
    customer_words = words_by_role["customer"]
    agent_segments = role_segments.get("agent", 0)

    agent_active = agent_talk >= AGENT_TALK_THRESHOLD or agent_words >= AGENT_WORD_THRESHOLD
    customer_active = customer_talk >= CUSTOMER_TALK_THRESHOLD or customer_words >= CUSTOMER_WORD_THRESHOLD
    duration_base = duration_reference if duration_reference > 0 else (
        agent_talk + customer_talk + talk_by_role.get("ivr", 0.0)
    )
    talk_share = safe_div(agent_talk + customer_talk, duration_base)
    agent_ratio = safe_div(agent_talk, duration_reference)
    hold_dominant = (
        hold_flag
        and (not agent_language_hint)
        and agent_ratio < 0.05
        and agent_segments <= 3
        and customer_words >= max(10, 5 * max(agent_words, 1))
    )
    agent_ratio = safe_div(agent_talk, duration_reference)

    if word_count_total < 5 and not agent_active and not customer_active:
        return "sem_audio"
    if invalid_number_flag:
        return "numero_inexistente"
    if suspended_flag:
        return "telefone_suspendido"
    if fax_flag:
        return "fax_ou_contestadora"
    if voicemail_flag and not agent_active:
        return "buzon"
    if order_flag:
        return "orden_aberta"
    if agent_active and customer_active:
        if hold_dominant:
            return "conectado_sem_cliente"

        hold_heu = (
            not customer_after_agent
            and (
                hold_flag
                or (
                    agent_segments <= 1
                    and agent_talk < 20
                    and customer_words >= CUSTOMER_WORD_THRESHOLD * 2
                    and customer_talk > agent_talk * 3
                )
            )
        )
        if hold_heu:
            return "conectado_sem_cliente"
        minimal_dialog = agent_language_hint or (
            customer_after_agent
            and (
                agent_segments >= 2
                or (
                    words_by_role["agent"] >= AGENT_WORD_THRESHOLD
                    and customer_words >= CUSTOMER_WORD_THRESHOLD * 2
                    and talk_share >= 0.4
                )
                or (
                    turn_count >= 4
                    and customer_words >= CUSTOMER_WORD_THRESHOLD * 2
                    and talk_share >= 0.4
                )
            )
        )
        if minimal_dialog:
            return "dialogo_conectado"
        return "conectado_sem_cliente"
    if agent_active:
        return "conectado_sem_cliente"
    if customer_active:
        if agent_language_hint and (customer_words >= 20 or word_count_total >= 30):
            return "dialogo_conectado"
        if (hold_flag and not customer_after_agent) or hold_dominant:
            return "conectado_sem_cliente"
        if talk_by_role["agent"] > 0 or words_by_role["agent"] > 0:
            return "conectado_sem_cliente"
        return "cliente_interagiu_sem_agente"
    return "ivr_sem_interacao"


def divergence_reason(normalized: str, actual: str, expected: Tuple[str, ...]) -> str:
    if not expected:
        return "Status IZZI não mapeado para comparação."
    if actual in expected:
        return ""

    specific = {
        ("no_contesto", "dialogo_conectado"): "Há diálogo agente-cliente apesar de IZZI marcar 'No Contesto'.",
        ("no_contesto", "cliente_interagiu_sem_agente"): "Cliente fala sozinho; registro 'No Contesto' deveria refletir interação parcial.",
        ("no_contesto", "conectado_sem_cliente"): "Agente respondeu, mas IZZI marcou como sem contato.",
        ("buzon", "dialogo_conectado"): "Chamada atendida por pessoas, não por caixa postal.",
        ("buzon", "cliente_interagiu_sem_agente"): "Ouvimos fala humana em vez de caixa postal.",
        ("sin_audio", "dialogo_conectado"): "Existe áudio com diálogo, diferente de 'Sin Audio'.",
        ("sin_audio", "cliente_interagiu_sem_agente"): "Há fala humana mesmo com marcação 'Sin Audio'.",
        ("fax_contestadora", "dialogo_conectado"): "Atendimento humano detectado, não sinal de fax.",
        ("fax_contestadora", "cliente_interagiu_sem_agente"): "Fala humana presente; não é contestadora.",
        ("numero_inexistente", "dialogo_conectado"): "Chamada conectou com pessoas; número não é inexistente.",
        ("numero_inexistente", "cliente_interagiu_sem_agente"): "Há resposta humana; número existe.",
        ("telefone_suspendido", "dialogo_conectado"): "Chamada ativa mesmo com status de linha suspensa.",
        ("telefone_suspendido", "cliente_interagiu_sem_agente"): "Cliente fala apesar da marcação de suspensão.",
    }

    if (normalized, actual) in specific:
        return specific[(normalized, actual)]

    generic_reasons = {
        "dialogo_conectado": "Chamada contém diálogo entre agente e cliente.",
        "cliente_interagiu_sem_agente": "Cliente fala sem retorno de agente.",
        "conectado_sem_cliente": "Agente fala sem resposta do cliente.",
        "buzon": "Mensagem típica de caixa postal detectada.",
        "fax_ou_contestadora": "Som de fax/contestadora identificado.",
        "ivr_sem_interacao": "Somente IVR sem interação humana.",
        "sem_audio": "Transcrição quase vazia, indica ausência de áudio útil.",
        "orden_aberta": "Script menciona ordens abertas em andamento.",
        "numero_inexistente": "Mensagem automática aponta número inexistente.",
        "telefone_suspendido": "Mensagem automática aponta linha suspensa.",
    }
    return generic_reasons.get(actual, "Comportamento da chamada não corresponde à marcação IZZI.")


def main() -> None:
    metadata = load_metadata(METADATA_FILE)
    files = list_transcription_files(TRANSCRIPTION_DIR)
    sentiment = SentimentAnalyzer()

    per_call_details = []
    duration_meta_list = []
    duration_transcript_list = []
    duration_transcript_raw_list = []
    word_counts = []
    unique_words_counts = []
    segment_counts = []
    turn_counts = []
    customer_talk_times = []
    agent_talk_times = []
    ivr_talk_times = []
    silence_times = []
    silence_ratios = []
    customer_ratios = []
    agent_ratios = []
    ivr_ratios = []
    customer_rates = []
    agent_rates = []
    engagement_scores = []
    customer_sentiment_scores = []
    agent_sentiment_scores = []

    izzi_status_counter = Counter()
    actual_status_counter = Counter()
    divergence_counter = Counter()
    divergence_reasons = Counter()
    confusion_matrix = Counter()
    hour_counter = Counter()
    product_counter = Counter()
    operator_counter = Counter()
    queue_counter = Counter()

    calls_with_agent = 0
    calls_with_customer_after_agent = 0
    ivr_only_calls = 0
    voicemail_calls = 0
    invalid_number_calls = 0
    suspended_calls = 0
    fax_calls = 0
    order_calls = 0
    customer_only_calls = 0
    low_audio_calls = 0
    connected_calls = 0

    total_words_customer = 0
    total_words_agent = 0
    total_words_ivr = 0
    customer_sentiment_labels = Counter()
    agent_sentiment_labels = Counter()
    script_alignment_counts = Counter()
    script_alignment_scores: List[float] = []
    script_alignment_applicable = 0
    source_awareness_levels = Counter()
    source_awareness_calls = 0
    sales_pitch_counts = Counter()
    sales_pitch_scores: List[float] = []
    follow_up_calls = 0
    follow_up_by_agent = 0
    follow_up_by_customer = 0
    objection_handled_calls = 0
    objection_sequences_total = 0
    customer_anger_calls = 0
    customer_anger_negative_sentiment = 0

    for fname in files:
        fpath = os.path.join(TRANSCRIPTION_DIR, fname)
        with open(fpath) as jsonfile:
            data = json.load(jsonfile)

        base_id = data.get("base_id") or data.get("file_name", "").replace(".WAV", "")
        meta = metadata.get(base_id, {})

        segments = data.get("segments", [])
        talk_by_role = Counter({"agent": 0.0, "customer": 0.0, "ivr": 0.0})
        words_by_role = Counter({"agent": 0, "customer": 0, "ivr": 0})
        texts_by_role = defaultdict(list)
        unique_words = set()
        role_segments = Counter()
        first_role_time = {}
        prev_role = None
        turn_count = 0

        for seg in segments:
            role = seg.get("role", "unknown") or "unknown"
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start))
            duration = max(0.0, end - start)
            text = seg.get("text", "")

            talk_by_role[role] += duration
            words = tokenize_words(text)
            words_by_role[role] += len(words)
            unique_words.update(words)
            texts_by_role[role].append(text)
            role_segments[role] += 1
            if role not in first_role_time:
                first_role_time[role] = start
            if prev_role is not None and role != prev_role:
                turn_count += 1
            prev_role = role

        total_segments = len(segments)
        duration_transcript_raw = max((float(seg.get("end", 0.0)) for seg in segments), default=0.0)
        duration_meta = parse_float(meta.get("duration_seconds_paneas"))
        effective_duration = duration_meta if duration_meta > 0 else duration_transcript_raw
        duration_transcript = (
            min(duration_transcript_raw, effective_duration)
            if effective_duration > 0
            else duration_transcript_raw
        )
        if duration_transcript == 0 and duration_transcript_raw > 0:
            duration_transcript = duration_transcript_raw
        total_duration_reference = effective_duration if effective_duration > 0 else duration_transcript
        if total_duration_reference == 0:
            total_duration_reference = duration_transcript_raw
        if total_duration_reference == 0:
            total_duration_reference = sum(talk_by_role.values())

        talk_time_adjusted = dict(talk_by_role)
        talk_total = sum(talk_time_adjusted.values())
        if total_duration_reference > 0 and talk_total > total_duration_reference:
            scale = total_duration_reference / talk_total
            for role in talk_time_adjusted:
                talk_time_adjusted[role] *= scale
            talk_total = total_duration_reference
        else:
            talk_total = sum(talk_time_adjusted.values())

        silence_time = max(0.0, total_duration_reference - talk_total)
        silence_ratio = safe_div(silence_time, total_duration_reference)

        word_count_total = sum(words_by_role.values())
        avg_words_per_seg = safe_div(word_count_total, total_segments)
        avg_segment_duration = safe_div(total_duration_reference, max(1, total_segments))

        customer_after_agent = False
        first_agent_time = first_role_time.get("agent", -1.0)
        first_customer_time = first_role_time.get("customer", -1.0)
        if first_agent_time >= 0:
            for seg in segments:
                if seg.get("role") == "customer" and float(seg.get("start", 0.0)) > first_agent_time:
                    customer_after_agent = True
                    break

        transcript_text = data.get("transcription", "")
        customer_text = " ".join(texts_by_role.get("customer", []))
        agent_text = " ".join(texts_by_role.get("agent", []))

        agent_language_hint = detect_agent_language(transcript_text)
        hold_flag = detect_keywords(transcript_text, HOLD_KEYWORDS)

        voicemail_flag = detect_keywords(transcript_text, VOICEMAIL_KEYWORDS)
        invalid_number_flag = detect_keywords(transcript_text, INVALID_NUMBER_KEYWORDS)
        suspended_flag = detect_keywords(transcript_text, SUSPENDED_KEYWORDS)
        fax_flag = detect_keywords(transcript_text, FAX_KEYWORDS)
        order_flag = detect_keywords(transcript_text, ORDER_KEYWORDS)

        source_awareness = detect_source_awareness(segments, agent_text)
        sales_pitch = evaluate_sales_pitch(agent_text)
        follow_up = detect_follow_up_commitment(segments)
        objection = detect_objection_handling(segments)
        customer_sentiment_raw = sentiment.run(customer_text)
        agent_sentiment_raw = sentiment.run(agent_text)
        customer_anger = detect_customer_anger(customer_text, customer_sentiment_raw)
        customer_sentiment = customer_sentiment_raw
        agent_sentiment = agent_sentiment_raw

        engagement_raw = (
            0.4 * safe_div(words_by_role["customer"], max(1, word_count_total))
            + 0.4 * safe_div(
                talk_time_adjusted["customer"],
                total_duration_reference if total_duration_reference else 1.0,
            )
            + 0.2 * safe_div(turn_count, max(1, total_segments))
        )
        customer_engagement = round(min(1.0, max(0.0, engagement_raw)), 4)

        izzi_reported = clean_text_value(meta.get("status_contato_izzi"))
        normalized_izzi = normalize_izzi_status(izzi_reported or "")
        actual_status = classify_actual_status(
            word_count_total,
            talk_by_role,
            words_by_role,
            role_segments,
            total_duration_reference,
            transcript_text,
            {
                "voicemail": voicemail_flag,
                "invalid_number": invalid_number_flag,
                "suspended": suspended_flag,
                "fax": fax_flag,
                "order": order_flag,
                "agent_language": agent_language_hint,
                "hold": hold_flag,
            },
            turn_count=turn_count,
            customer_after_agent=customer_after_agent,
        )
        expected_statuses = expected_actual_statuses(normalized_izzi)
        if expected_statuses:
            divergence = actual_status not in expected_statuses
        else:
            divergence = False
        reason = divergence_reason(normalized_izzi, actual_status, expected_statuses) if divergence else None

        if divergence:
            divergence_counter[(normalized_izzi, actual_status)] += 1
            if reason:
                divergence_reasons[reason] += 1

        izzi_status_counter[normalized_izzi] += 1
        actual_status_counter[actual_status] += 1
        confusion_matrix[(normalized_izzi, actual_status)] += 1

        script_value = clean_text_value(meta.get("script_paneas"))
        product_value = clean_text_value(meta.get("produto_oferta"))
        queue_value = clean_text_value(meta.get("fila_atendimento_izzi"))
        contact_type_value = clean_text_value(meta.get("tipo_contato_paneas"))
        call_datetime_str = clean_text_value(meta.get("data_chamada_paneas"))
        operator_value = clean_text_value(meta.get("operadora_telefone_paneas"))

        try:
            call_datetime = datetime.strptime(call_datetime_str, "%d/%m/%Y %H:%M:%S") if call_datetime_str else None
        except ValueError:
            call_datetime = None
        if call_datetime:
            hour_counter[call_datetime.hour] += 1

        product_counter[product_value or "desconhecido"] += 1
        operator_counter[operator_value or "desconhecido"] += 1
        queue_counter[queue_value or "desconhecido"] += 1

        script_reference_text = assemble_script_reference(
            segments,
            script_value,
            product_value,
            first_agent_time,
            contact_type=contact_type_value,
        )
        if first_agent_time >= 0:
            follow_text_parts = []
            for seg in segments:
                text_seg = seg.get("text", "")
                if not text_seg:
                    continue
                start_seg = float(seg.get("start", 0.0))
                if start_seg < first_agent_time - 0.01:
                    continue
                role_seg = (seg.get("role") or "").lower()
                if role_seg == "ivr":
                    continue
                follow_text_parts.append(text_seg)
                if len(follow_text_parts) >= 120:
                    break
            follow_text = " ".join(follow_text_parts).strip()
        else:
            follow_text = agent_text
        if not follow_text:
            follow_text = agent_text or transcript_text
        script_alignment = compute_script_alignment(
            follow_text,
            script_reference_text,
            product_meta=product_value,
            contact_type=contact_type_value,
        )
        script_alignment_counts[script_alignment["label"]] += 1
        if script_alignment["total"] > 0 or script_reference_text:
            script_alignment_applicable += 1
            script_alignment_scores.append(float(script_alignment["score"]))
        source_awareness_levels[source_awareness["level"]] += 1
        if source_awareness["detected"]:
            source_awareness_calls += 1
        sales_pitch_counts[sales_pitch["label"]] += 1
        sales_pitch_scores.append(float(sales_pitch["score"]))
        if follow_up["detected"]:
            follow_up_calls += 1
            if follow_up["actor"] == "agent":
                follow_up_by_agent += 1
            elif follow_up["actor"] == "customer":
                follow_up_by_customer += 1
        if objection["detected"]:
            objection_handled_calls += 1
            objection_sequences_total += objection["count"]
        if customer_anger["detected"]:
            customer_anger_calls += 1
            if customer_sentiment_raw.label == "negative":
                customer_anger_negative_sentiment += 1

        if (
            words_by_role["customer"] < SENTIMENT_WORD_THRESHOLD
            or actual_status in {"conectado_sem_cliente", "ivr_sem_interacao", "fax_ou_contestadora", "buzon"}
        ):
            customer_sentiment = SentimentResult(0.0, "ausente")

        if (
            words_by_role["agent"] < SENTIMENT_WORD_THRESHOLD
            or actual_status in {"cliente_interagiu_sem_agente", "ivr_sem_interacao", "buzon", "fax_ou_contestadora"}
        ):
            agent_sentiment = SentimentResult(0.0, "ausente")

        agent_active_flag = (
            talk_by_role["agent"] >= AGENT_TALK_THRESHOLD or words_by_role["agent"] >= AGENT_WORD_THRESHOLD
        )
        customer_active_flag = (
            talk_by_role["customer"] >= CUSTOMER_TALK_THRESHOLD or words_by_role["customer"] >= CUSTOMER_WORD_THRESHOLD
        )

        calls_with_agent += 1 if agent_active_flag else 0
        calls_with_customer_after_agent += 1 if customer_after_agent else 0
        ivr_only_calls += 1 if actual_status == "ivr_sem_interacao" else 0
        voicemail_calls += 1 if actual_status == "buzon" else 0
        invalid_number_calls += 1 if actual_status == "numero_inexistente" else 0
        suspended_calls += 1 if actual_status == "telefone_suspendido" else 0
        fax_calls += 1 if actual_status == "fax_ou_contestadora" else 0
        order_calls += 1 if actual_status == "orden_aberta" else 0
        customer_only_calls += 1 if actual_status == "cliente_interagiu_sem_agente" else 0
        low_audio_calls += 1 if actual_status == "sem_audio" else 0
        connected_calls += 1 if actual_status == "dialogo_conectado" else 0

        total_words_customer += words_by_role["customer"]
        total_words_agent += words_by_role["agent"]
        total_words_ivr += words_by_role["ivr"]

        speech_rate_agent = compute_speech_rate(words_by_role["agent"], talk_time_adjusted["agent"])
        speech_rate_customer = compute_speech_rate(words_by_role["customer"], talk_time_adjusted["customer"])

        customer_sentiment_labels[customer_sentiment.label] += 1
        agent_sentiment_labels[agent_sentiment.label] += 1

        per_call_details.append({
            "call_id": base_id,
            "script": script_value,
            "product_offer": product_value,
            "queue": queue_value,
            "contact_type": contact_type_value,
            "call_datetime": call_datetime_str,
            "duration_seconds_metadata": round(duration_meta, 4),
            "duration_seconds_transcript": round(duration_transcript, 4),
            "duration_seconds_transcript_raw": round(duration_transcript_raw, 4),
            "duration_reference_seconds": round(total_duration_reference, 4),
            "word_count_total": word_count_total,
            "unique_word_count": len(unique_words),
            "segment_count": total_segments,
            "turn_count": turn_count,
            "avg_words_per_segment": round(avg_words_per_seg, 4),
            "avg_segment_duration": round(avg_segment_duration, 4),
            "words_agent": words_by_role["agent"],
            "words_customer": words_by_role["customer"],
            "words_ivr": words_by_role["ivr"],
            "talk_time_agent": round(talk_time_adjusted["agent"], 4),
            "talk_time_customer": round(talk_time_adjusted["customer"], 4),
            "talk_time_ivr": round(talk_time_adjusted["ivr"], 4),
            "silence_time_estimate": round(silence_time, 4),
            "silence_ratio": round(silence_ratio, 4),
            "talk_ratio_agent": round(safe_div(talk_time_adjusted["agent"], total_duration_reference), 4),
            "talk_ratio_customer": round(safe_div(talk_time_adjusted["customer"], total_duration_reference), 4),
            "talk_ratio_ivr": round(safe_div(talk_time_adjusted["ivr"], total_duration_reference), 4),
            "speech_rate_agent_wpm": speech_rate_agent,
            "speech_rate_customer_wpm": speech_rate_customer,
            "customer_sentiment_score": customer_sentiment.score,
            "customer_sentiment_label": customer_sentiment.label,
            "agent_sentiment_score": agent_sentiment.score,
            "agent_sentiment_label": agent_sentiment.label,
            "customer_engagement_score": customer_engagement,
            "customer_after_agent": 1 if customer_after_agent else 0,
            "first_agent_start": round(first_agent_time, 4),
            "first_customer_start": round(first_customer_time, 4),
            "contains_voicemail_keywords": 1 if voicemail_flag else 0,
            "contains_invalid_number_keywords": 1 if invalid_number_flag else 0,
            "contains_suspension_keywords": 1 if suspended_flag else 0,
            "contains_fax_keywords": 1 if fax_flag else 0,
            "contains_order_keywords": 1 if order_flag else 0,
            "agent_language_detected": 1 if agent_language_hint else 0,
            "script_alignment_label": script_alignment["label"],
            "script_alignment_score": script_alignment["score"],
            "script_keyword_hits": script_alignment["hits"],
            "script_keyword_total": script_alignment["total"],
            "script_keywords_matched": script_alignment["matched"],
            "operator_source_awareness": 1 if source_awareness["detected"] else 0,
            "operator_source_awareness_level": source_awareness["level"],
            "operator_source_awareness_matches": source_awareness["matches"],
            "sales_pitch_score": sales_pitch["score"],
            "sales_pitch_label": sales_pitch["label"],
            "sales_pitch_topics": sales_pitch["topics"],
            "follow_up_commitment": 1 if follow_up["detected"] else 0,
            "follow_up_actor": follow_up["actor"],
            "follow_up_matches": follow_up["matches"],
            "objection_handled": 1 if objection["detected"] else 0,
            "objection_handled_count": objection["count"],
            "customer_anger_detected": 1 if customer_anger["detected"] else 0,
            "customer_anger_matches": customer_anger["matches"],
            "izzi_status_reportado": izzi_reported,
            "izzi_status_normalizado": normalized_izzi,
            "status_real_detectado": actual_status,
            "divergente": 1 if divergence else 0,
            "divergencia_motivo": reason,
        })

        duration_meta_list.append(duration_meta)
        duration_transcript_list.append(duration_transcript)
        duration_transcript_raw_list.append(duration_transcript_raw)
        word_counts.append(word_count_total)
        unique_words_counts.append(len(unique_words))
        segment_counts.append(total_segments)
        turn_counts.append(turn_count)
        customer_talk_times.append(talk_time_adjusted["customer"])
        agent_talk_times.append(talk_time_adjusted["agent"])
        ivr_talk_times.append(talk_time_adjusted["ivr"])
        silence_times.append(silence_time)
        silence_ratios.append(silence_ratio)
        customer_ratios.append(safe_div(talk_time_adjusted["customer"], total_duration_reference))
        agent_ratios.append(safe_div(talk_time_adjusted["agent"], total_duration_reference))
        ivr_ratios.append(safe_div(talk_time_adjusted["ivr"], total_duration_reference))
        customer_rates.append(per_call_details[-1]["speech_rate_customer_wpm"])
        agent_rates.append(per_call_details[-1]["speech_rate_agent_wpm"])
        engagement_scores.append(customer_engagement)
        customer_sentiment_scores.append(customer_sentiment.score)
        agent_sentiment_scores.append(agent_sentiment.score)

    total_calls = len(per_call_details)
    divergence_total = sum(item["divergente"] for item in per_call_details)

    duration_meta_stats = compute_statistics(duration_meta_list)
    duration_transcript_stats = compute_statistics(duration_transcript_list)
    duration_transcript_raw_stats = compute_statistics(duration_transcript_raw_list)
    word_stats = compute_statistics(word_counts)
    unique_word_stats = compute_statistics(unique_words_counts)
    segment_stats = compute_statistics(segment_counts)
    turn_stats = compute_statistics(turn_counts)
    customer_talk_stats = compute_statistics(customer_talk_times)
    agent_talk_stats = compute_statistics(agent_talk_times)
    ivr_talk_stats = compute_statistics(ivr_talk_times)
    silence_time_stats = compute_statistics(silence_times)
    silence_ratio_stats = compute_statistics(silence_ratios)
    customer_ratio_stats = compute_statistics(customer_ratios)
    agent_ratio_stats = compute_statistics(agent_ratios)
    ivr_ratio_stats = compute_statistics(ivr_ratios)
    customer_rate_stats = compute_statistics(customer_rates)
    agent_rate_stats = compute_statistics(agent_rates)
    engagement_stats = compute_statistics(engagement_scores)
    customer_sentiment_stats = compute_statistics(customer_sentiment_scores)
    agent_sentiment_stats = compute_statistics(agent_sentiment_scores)
    script_alignment_score_avg = round(statistics.mean(script_alignment_scores), 4) if script_alignment_scores else 0.0
    sales_pitch_score_avg = round(statistics.mean(sales_pitch_scores), 4) if sales_pitch_scores else 0.0
    source_awareness_distribution = {
        str(level): count for level, count in source_awareness_levels.items()
    }

    unique_days = {
        detail["call_datetime"].split()[0]
        for detail in per_call_details
        if detail["call_datetime"]
    }
    calls_per_day_count = len(unique_days)
    avg_calls_per_day = round(safe_div(total_calls, calls_per_day_count), 4) if calls_per_day_count else 0.0

    dataset_summary = {
        "total_calls": total_calls,
        "calls_with_agent": calls_with_agent,
        "calls_with_customer_after_agent": calls_with_customer_after_agent,
        "ivr_only_calls": ivr_only_calls,
        "voicemail_detected_calls": voicemail_calls,
        "invalid_number_detected_calls": invalid_number_calls,
        "suspended_number_calls": suspended_calls,
        "fax_detected_calls": fax_calls,
        "orders_referenced_calls": order_calls,
        "customer_only_calls": customer_only_calls,
        "low_audio_transcription_calls": low_audio_calls,
        "divergent_calls": divergence_total,
        "divergence_rate": round(safe_div(divergence_total, total_calls), 4),
        "izzi_status_accuracy": round(1.0 - safe_div(divergence_total, total_calls), 4),
        "duration_metadata": duration_meta_stats,
        "duration_transcription": duration_transcript_stats,
        "duration_transcription_raw": duration_transcript_raw_stats,
        "word_count": word_stats,
        "unique_word_count": unique_word_stats,
        "segment_count": segment_stats,
        "turn_count": turn_stats,
        "customer_talk_time": customer_talk_stats,
        "agent_talk_time": agent_talk_stats,
        "ivr_talk_time": ivr_talk_stats,
        "silence_time": silence_time_stats,
        "silence_ratio": silence_ratio_stats,
        "talk_ratio_customer": customer_ratio_stats,
        "talk_ratio_agent": agent_ratio_stats,
        "talk_ratio_ivr": ivr_ratio_stats,
        "customer_speech_rate_wpm": customer_rate_stats,
        "agent_speech_rate_wpm": agent_rate_stats,
        "customer_engagement_score": engagement_stats,
        "customer_sentiment_score": customer_sentiment_stats,
        "agent_sentiment_score": agent_sentiment_stats,
        "total_duration_metadata_seconds": round(sum(duration_meta_list), 4),
        "total_duration_transcript_seconds": round(sum(duration_transcript_list), 4),
        "total_words_customer": total_words_customer,
        "total_words_agent": total_words_agent,
        "total_words_ivr": total_words_ivr,
        "customer_sentiment_label_distribution": dict(customer_sentiment_labels),
        "agent_sentiment_label_distribution": dict(agent_sentiment_labels),
        "customer_positive_rate": round(safe_div(customer_sentiment_labels.get("positive", 0), total_calls), 4),
        "customer_negative_rate": round(safe_div(customer_sentiment_labels.get("negative", 0), total_calls), 4),
        "agent_positive_rate": round(safe_div(agent_sentiment_labels.get("positive", 0), total_calls), 4),
        "agent_negative_rate": round(safe_div(agent_sentiment_labels.get("negative", 0), total_calls), 4),
        "connected_calls": connected_calls,
        "connected_call_ratio": round(safe_div(connected_calls, total_calls), 4),
        "total_turns": int(sum(turn_counts)),
        "total_silence_time_seconds": round(sum(silence_times), 4),
        "top_call_hours": sorted(hour_counter.items(), key=lambda x: (-x[1], x[0]))[:5],
        "product_offer_distribution": product_counter.most_common(10),
        "operator_distribution": operator_counter.most_common(10),
        "queue_distribution": queue_counter.most_common(10),
        "calls_per_day": calls_per_day_count,
        "avg_calls_per_day": avg_calls_per_day,
        "script_alignment_counts": dict(script_alignment_counts),
        "script_alignment_applicable": script_alignment_applicable,
        "script_alignment_aligned_rate": round(
            safe_div(script_alignment_counts.get("aligned", 0), script_alignment_applicable), 4
        )
        if script_alignment_applicable
        else 0.0,
        "script_alignment_off_script_rate": round(
            safe_div(script_alignment_counts.get("off_script", 0), script_alignment_applicable), 4
        )
        if script_alignment_applicable
        else 0.0,
        "script_alignment_score_avg": script_alignment_score_avg,
        "operator_source_awareness_calls": source_awareness_calls,
        "operator_source_awareness_rate": round(safe_div(source_awareness_calls, total_calls), 4),
        "operator_source_awareness_level_distribution": source_awareness_distribution,
        "sales_pitch_distribution": dict(sales_pitch_counts),
        "sales_pitch_score_avg": sales_pitch_score_avg,
        "sales_pitch_satisfactory_rate": round(
            safe_div(sales_pitch_counts.get("satisfactory", 0), total_calls), 4
        ),
        "follow_up_commitment_calls": follow_up_calls,
        "follow_up_commitment_rate": round(safe_div(follow_up_calls, total_calls), 4),
        "follow_up_by_agent": follow_up_by_agent,
        "follow_up_by_customer": follow_up_by_customer,
        "objection_handled_calls": objection_handled_calls,
        "objection_handled_rate": round(safe_div(objection_handled_calls, total_calls), 4),
        "objection_sequences_total": objection_sequences_total,
        "customer_anger_calls": customer_anger_calls,
        "customer_anger_rate": round(safe_div(customer_anger_calls, total_calls), 4),
        "customer_anger_negative_sentiment_overlap": round(
            safe_div(customer_anger_negative_sentiment, customer_anger_calls), 4
        )
        if customer_anger_calls
        else 0.0,
    }

    by_izzi_status = {}
    for status, count in izzi_status_counter.items():
        matches = sum(
            1 for detail in per_call_details
            if detail["izzi_status_normalizado"] == status and detail["divergente"] == 0
        )
        divergences = count - matches
        by_izzi_status[status or "desconhecido"] = {
            "reported_count": count,
            "matched_count": matches,
            "divergent_count": divergences,
            "match_rate": round(safe_div(matches, count), 4) if count else 0.0,
        }

    by_actual_status = {}
    for status, count in actual_status_counter.items():
        by_actual_status[status] = {
            "detected_count": count,
            "share": round(safe_div(count, total_calls), 4),
        }

    confusion_list = [
        {
            "izzi_status": pair[0],
            "actual_status": pair[1],
            "count": count,
        }
        for pair, count in sorted(confusion_matrix.items(), key=lambda item: (-item[1], item[0]))
    ]

    divergence_details = [
        {
            "reason": reason,
            "count": count,
        }
        for reason, count in sorted(divergence_reasons.items(), key=lambda item: (-item[1], item[0]))
    ]

    output = {
        "dataset_summary": dataset_summary,
        "status_analysis": {
            "by_izzi_status": by_izzi_status,
            "by_actual_status": by_actual_status,
            "confusion_matrix": confusion_list,
        },
        "divergence_summary": {
            "total_divergent_calls": divergence_total,
            "divergence_rate": round(safe_div(divergence_total, total_calls), 4),
            "divergence_breakdown": divergence_details,
        },
        "per_call_details": per_call_details,
        "metric_notes": {
            "sentiment_model": "nlptown/bert-base-multilingual-uncased-sentiment (média de até 3 blocos de 180 palavras)",
            "silence_time_estimate": "Estimado como diferença entre duração transcrita e soma de fala por papel.",
            "customer_engagement_score": "Pontuação normalizada combinando proporção de palavras do cliente, tempo de fala e alternância de turnos.",
            "script_alignment": "Comparação de palavras-chave do script/produto com a fala do agente.",
            "sales_pitch_score": "Score 0-4 avaliando citações de preço, benefícios, fidelização e diferenciais.",
            "follow_up_commitment": "Heurística sobre promessas de retorno/agendamento nos últimos turnos da chamada.",
            "objection_handled": "Detecção de pares cliente (objeção) × agente (contra-argumento) em até 3 turnos.",
            "customer_anger_detected": "Palavras-chave de interrupção + sentimento negativo intenso sobre parar as ligações.",
        },
    }

    with open(OUTPUT_FILE, "w") as outfile:
        json.dump(output, outfile, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
