#!/usr/bin/env python3
"""
Pipeline LLM-first para gerar full_analysis.json sem rodar a heurística original.

Fluxo:
  1. Carrega metadados e transcrições.
  2. Calcula métricas determinísticas (duração, falas por canal, silêncio, etc.).
  3. Envia cada chamada ao LLM, solicitando todos os campos analíticos.
  4. Atualiza divergências e estatísticas agregadas e salva o JSON final.

Uso:
    python engine/generate_full_analysis_v3.py --all
    python engine/generate_full_analysis_v3.py --call-id 0105-... --model gpt-4o --workers 6
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from llm_enrichment import (
    ALLOWED_STATUSES,
    apply_enrichment,
    build_conversation_prompt,
    call_openai,
    load_transcript,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
METADATA_FILE = BASE_DIR / "metadata.csv"
ENGINE_FILE = BASE_DIR / "full_analysis.json"
FRONTEND_FILE = PROJECT_DIR / "public" / "data" / "full_analysis.json"
DEFAULT_MODEL = "gpt-4o"

EXPECTED_STATUS_MAP: Dict[str, Tuple[str, ...]] = {
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

VOICEMAIL_KEYWORDS = [
    "buzón",
    "buzon",
    "mensaje después del tono",
    "mensaje despues del tono",
    "deje su mensaje",
    "grabadora",
    "casilla de voz",
    "deja tu mensaje",
    "tone señal",
    "tono despues del tono",
    "grabe su mensaje",
]
FAX_KEYWORDS = [
    "fax",
    "contestadora fax",
    "tono de fax",
    "señal de fax",
    "senial de fax",
]
INVALID_NUMBER_KEYWORDS = [
    "número que marcó no existe",
    "numero que marco no existe",
    "número marcado no existe",
    "numero marcado no existe",
    "número no está en servicio",
    "numero no esta en servicio",
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
NEGATIVE_SENTIMENT_THRESHOLD = 0.3
HIGH_RISK_SENTIMENT_THRESHOLD = 0.0
RECURRENCE_WINDOW = timedelta(days=7)
FOLLOW_UP_WINDOW = timedelta(days=5)

AGENT_LANGUAGE_PATTERNS = [
    "no se preocupe",
    "permítame",
    "permitame",
    "lo canalizo",
    "la canalizo",
    "lo transfiero",
    "quedo atenta",
    "quedo atento",
    "con gusto",
    "le comento",
    "le informo",
    "le indico",
    "estoy verificando",
    "estamos verificando",
    "muchísimas gracias",
    "muchisimas gracias",
    "gracias por comunicarse",
    "gracias por su tiempo",
    "me puede apoyar",
    "me ayudas con",
    "le apoyo",
    "le puedo ayudar",
    "puede confirmarme",
    "me confirma",
    "puede indicarme",
    "permanezca en la línea",
    "permanezca en la linea",
    "quedo a sus órdenes",
    "quedo a sus ordenes",
    "quedo pendiente",
    "con gusto le apoyo",
    "en seguida",
    "será un placer",
    "sera un placer",
]

AGENT_LANGUAGE_STRONG = [
    "gracias por llamar",
    "que tenga excelente día",
    "que tenga excelente dia",
    "que tenga buen día",
    "que tenga buen dia",
    "quedo atenta a sus comentarios",
    "lo registramos en comentarios",
    "lo pondremos en los comentarios",
]

NAME_CAPTURE = r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}){0,2})"
NAME_STOPWORDS = {
    "izzi",
    "servicio",
    "servicios",
    "atención",
    "atencion",
    "cliente",
    "clientes",
    "agente",
    "asesor",
    "asesora",
    "equipo",
    "departamento",
    "soporte",
    "telefónica",
    "telefonica",
    "comercial",
    "su",
    "nombre",
    "soy",
    "yo",
    "el",
    "la",
    "los",
    "las",
    "de",
    "del",
    "lo",
    "le",
    "tu",
    "usted",
    "sr",
    "sra",
    "señor",
    "señora",
    "señorita",
    "senor",
    "senora",
    "senorita",
}
AGENT_NAME_PATTERNS = [
    (re.compile(r"\bmi nombre es\s+" + NAME_CAPTURE, re.IGNORECASE), 0.95),
    (re.compile(r"\bme llamo\s+" + NAME_CAPTURE, re.IGNORECASE), 0.9),
    (re.compile(r"\bsoy\s+" + NAME_CAPTURE, re.IGNORECASE), 0.7),
    (re.compile(r"\bhabla\s+" + NAME_CAPTURE, re.IGNORECASE), 0.7),
    (re.compile(r"\b(?:le|te)\s+atiende\s+" + NAME_CAPTURE, re.IGNORECASE), 0.85),
    (re.compile(r"\bcon\s+gusto\s+(?:le\s+)?saluda\s+" + NAME_CAPTURE, re.IGNORECASE), 0.75),
]
CUSTOMER_NAME_PATTERNS = [
    (re.compile(r"\bme llamo\s+" + NAME_CAPTURE, re.IGNORECASE), 0.9),
    (re.compile(r"\bmi nombre es\s+" + NAME_CAPTURE, re.IGNORECASE), 0.9),
    (re.compile(r"\bsoy\s+" + NAME_CAPTURE, re.IGNORECASE), 0.7),
    (re.compile(r"\bhabla\s+" + NAME_CAPTURE, re.IGNORECASE), 0.65),
    (re.compile(r"\bseñor(?:a)?\s+" + NAME_CAPTURE, re.IGNORECASE), 0.55),
    (re.compile(r"\bsra\.?\s+" + NAME_CAPTURE, re.IGNORECASE), 0.55),
    (re.compile(r"\bsr\.?\s+" + NAME_CAPTURE, re.IGNORECASE), 0.55),
]


def load_metadata(path: Path) -> Dict[str, Dict[str, str]]:
    metadata: Dict[str, Dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        for row in reader:
            file_id = (row.get("file_id") or "").replace(".WAV", "")
            if not file_id:
                continue
            metadata[file_id] = {
                key: (value.strip() if isinstance(value, str) else value)
                for key, value in row.items()
            }
    return metadata


WORD_RE = re.compile(r"\b[\wáéíóúüñ]+\b", flags=re.IGNORECASE)


def tokenize_words(text: str) -> List[str]:
    if not text:
        return []
    return WORD_RE.findall(text.lower())


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if text.lower() in {"null", "n/a", "na", "-"}:
        return None
    return text


def parse_float(value: str | None) -> float:
    if value is None:
        return 0.0
    text = value.strip()
    if not text:
        return 0.0
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return 0.0


def parse_call_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def normalize_name_candidate(raw: str) -> str | None:
    if not raw:
        return None
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", raw)
    filtered: List[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in NAME_STOPWORDS:
            continue
        if len(token) <= 1:
            continue
        filtered.append(token)
    if not filtered:
        return None
    if filtered and filtered[0].lower() in {"buenos", "buenas", "gracias"}:
        filtered = filtered[1:]
    if not filtered:
        return None
    capped = [token.capitalize() for token in filtered[:3]]
    return " ".join(capped)


def match_name_patterns(text: str, patterns: List[Tuple[re.Pattern[str], float]]) -> Tuple[str | None, float | None]:
    for regex, confidence in patterns:
        match = regex.search(text)
        if not match:
            continue
        candidate = normalize_name_candidate(match.group(1))
        if candidate:
            return candidate, confidence
    return None, None


def detect_identity_from_segments(
    segments: List[Dict[str, Any]],
    overrides: Dict[int, str],
    target_role: str,
) -> Tuple[str | None, float | None]:
    best_name: str | None = None
    best_confidence = 0.0
    patterns = AGENT_NAME_PATTERNS if target_role == "agent" else CUSTOMER_NAME_PATTERNS
    for index, seg in enumerate(segments):
        original_role = (seg.get("role") or "unknown").lower()
        role = overrides.get(index, original_role)
        if role != target_role:
            continue
        text = seg.get("text") or ""
        name, confidence = match_name_patterns(text, patterns)
        if name and confidence:
            if confidence > best_confidence:
                best_name = name
                best_confidence = confidence
            if confidence >= 0.9:
                break
    if best_name:
        return best_name, best_confidence
    return None, None


def iso_week_info(dt: datetime) -> Tuple[str, datetime]:
    iso_year, iso_week, _ = dt.isocalendar()
    label = f"{iso_year}-W{iso_week:02d}"
    week_start = dt - timedelta(days=dt.weekday())
    week_start = datetime(week_start.year, week_start.month, week_start.day)
    return label, week_start


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_statistics(values: Iterable[float]) -> Dict[str, float]:
    data = [float(v) for v in values if v is not None]
    if not data:
        return {"avg": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
    avg = statistics.mean(data)
    median = statistics.median(data)
    minimum = min(data)
    maximum = max(data)
    std = statistics.pstdev(data) if len(data) > 1 else 0.0
    return {
        "avg": round(avg, 4),
        "median": round(median, 4),
        "min": round(minimum, 4),
        "max": round(maximum, 4),
        "std": round(std, 4),
    }


def detect_keywords(text: str, patterns: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in patterns)


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
        ("buzon", "cliente_interagiu_sem_agente"): "Fala humana detectada; não é caixa postal.",
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

    generic = {
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
    return generic.get(actual, "Comportamento da chamada não corresponde à marcação IZZI.")


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


SPECIAL_STATUSES = {
    "buzon",
    "fax_ou_contestadora",
    "numero_inexistente",
    "telefone_suspendido",
    "sem_audio",
    "ivr_sem_interacao",
    "orden_aberta",
}


def resolve_status(entry: Dict[str, Any], heuristic_status: str, llm_status: str | None) -> str:
    candidate = heuristic_status
    normalized_llm = None
    if isinstance(llm_status, str):
        normalized_llm = (
            llm_status.strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if normalized_llm in ALLOWED_STATUSES:
            candidate = normalized_llm

    flags_priority = [
        ("contains_invalid_number_keywords", "numero_inexistente"),
        ("contains_suspension_keywords", "telefone_suspendido"),
        ("contains_fax_keywords", "fax_ou_contestadora"),
        ("contains_voicemail_keywords", "buzon"),
        ("contains_order_keywords", "orden_aberta"),
    ]
    for flag, status in flags_priority:
        if entry.get(flag):
            return status

    silence_ratio = float(entry.get("silence_ratio") or 0.0)
    word_count = int(entry.get("word_count_total") or 0)
    talk_agent = float(entry.get("talk_time_agent") or 0.0)
    talk_customer = float(entry.get("talk_time_customer") or 0.0)
    talk_ivr = float(entry.get("talk_time_ivr") or 0.0)
    words_agent = int(entry.get("words_agent") or 0)
    words_customer = int(entry.get("words_customer") or 0)
    agent_language = bool(entry.get("agent_language_detected"))
    customer_after_agent = bool(entry.get("customer_after_agent"))

    if word_count <= 3 and talk_agent < 0.5 and talk_customer < 0.5 and silence_ratio > 0.92:
        return "sem_audio"

    if talk_ivr >= max(talk_agent + talk_customer, 10.0) and word_count < 20 and talk_agent < 1.0 and talk_customer < 1.0:
        return "ivr_sem_interacao"

    if candidate in SPECIAL_STATUSES:
        return candidate

    agent_present = agent_language or words_agent >= 14 or talk_agent >= 5.0
    customer_present = customer_after_agent or words_customer >= 14 or talk_customer >= 5.0

    if agent_present and customer_present:
        return "dialogo_conectado"
    if agent_present and not customer_present:
        return "conectado_sem_cliente"
    if customer_present and not agent_present:
        return "cliente_interagiu_sem_agente"

    if normalized_llm and normalized_llm in ALLOWED_STATUSES:
        return normalized_llm
    if heuristic_status in ALLOWED_STATUSES:
        return heuristic_status
    return "ivr_sem_interacao"


VALID_ROLES = {"agent", "customer", "ivr"}
LLM_PRESERVE_FIELDS = {
    "status_real_detectado",
    "customer_sentiment_score",
    "customer_sentiment_label",
    "agent_sentiment_score",
    "agent_sentiment_label",
    "script_alignment_label",
    "script_alignment_score",
    "script_keyword_hits",
    "script_keyword_total",
    "script_keywords_matched",
    "operator_source_awareness",
    "operator_source_awareness_level",
    "operator_source_awareness_matches",
    "sales_pitch_score",
    "sales_pitch_label",
    "sales_pitch_topics",
    "follow_up_commitment",
    "follow_up_actor",
    "follow_up_matches",
    "objection_handled",
    "objection_handled_count",
    "customer_anger_detected",
    "customer_anger_matches",
    "agent_name_detected",
    "agent_name_confidence",
    "agent_name_source",
    "customer_name_detected",
    "customer_name_confidence",
    "llm_enrichment_source",
    "llm_notes",
    "llm_status_raw",
    "llm_segment_corrections",
}


def compute_base_entry(
    call_id: str,
    transcript: Dict[str, Any],
    metadata_row: Dict[str, Any],
    role_overrides: Dict[int, str] | None = None,
) -> Dict[str, Any]:
    segments = transcript.get("segments") or []
    talk_by_role: Counter[str] = Counter()
    words_by_role: Counter[str] = Counter()
    unique_words: set[str] = set()
    role_segments: Counter[str] = Counter()
    first_role_time: Dict[str, float] = {}
    prev_role: str | None = None
    turn_count = 0

    overrides = role_overrides or {}

    for index, seg in enumerate(segments):
        original_role = (seg.get("role") or "unknown").lower()
        role = overrides.get(index, original_role)
        if role not in VALID_ROLES:
            role = original_role
        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", start) or start)
        duration = max(0.0, end - start)
        text = seg.get("text") or ""

        talk_by_role[role] += duration
        words = tokenize_words(text)
        words_by_role[role] += len(words)
        unique_words.update(words)
        role_segments[role] += 1
        if role not in first_role_time:
            first_role_time[role] = start
        if prev_role is not None and role != prev_role:
            turn_count += 1
        prev_role = role

    total_segments = len(segments)
    duration_transcript_raw = max((float(seg.get("end", 0.0) or 0.0) for seg in segments), default=0.0)
    duration_meta = parse_float(metadata_row.get("duration_seconds_paneas"))
    effective_duration = duration_meta if duration_meta > 0 else duration_transcript_raw
    duration_transcript = (
        min(duration_transcript_raw, effective_duration)
        if effective_duration > 0
        else duration_transcript_raw
    )
    if duration_transcript == 0 and duration_transcript_raw > 0:
        duration_transcript = duration_transcript_raw
    total_reference = effective_duration if effective_duration > 0 else duration_transcript
    if total_reference == 0:
        total_reference = duration_transcript_raw
    if total_reference == 0:
        total_reference = sum(talk_by_role.values())

    talk_time_adjusted = {role: float(value) for role, value in talk_by_role.items()}
    talk_total = sum(talk_time_adjusted.values())
    if total_reference > 0 and talk_total > total_reference and talk_total > 0:
        scale = total_reference / talk_total
        talk_time_adjusted = {role: value * scale for role, value in talk_time_adjusted.items()}
        talk_total = sum(talk_time_adjusted.values())

    silence_time = max(0.0, total_reference - talk_total)
    silence_ratio = round(safe_div(silence_time, total_reference), 4)

    words_agent = words_by_role.get("agent", 0)
    words_customer = words_by_role.get("customer", 0)
    words_ivr = words_by_role.get("ivr", 0)
    talk_agent = talk_time_adjusted.get("agent", 0.0)
    talk_customer = talk_time_adjusted.get("customer", 0.0)
    talk_ivr = talk_time_adjusted.get("ivr", 0.0)

    word_count_total = words_agent + words_customer + words_ivr + sum(
        value for role, value in words_by_role.items() if role not in {"agent", "customer", "ivr"}
    )
    avg_words_per_segment = round(safe_div(word_count_total, total_segments), 4)
    avg_segment_duration = round(safe_div(total_reference, total_segments), 4)

    first_agent_time = first_role_time.get("agent", -1.0)
    first_customer_time = first_role_time.get("customer", -1.0)
    customer_after_agent = False
    if first_agent_time >= 0:
        for index, seg in enumerate(segments):
            role = overrides.get(index, (seg.get("role") or "").lower())
            if role not in VALID_ROLES:
                role = (seg.get("role") or "").lower()
            start = float(seg.get("start", 0.0) or 0.0)
            if role == "customer" and start > first_agent_time:
                customer_after_agent = True
                break

    transcript_text = transcript.get("transcription") or " ".join(
        seg.get("text") or "" for seg in segments
    )
    voicemail_flag = detect_keywords(transcript_text, VOICEMAIL_KEYWORDS)
    invalid_number_flag = detect_keywords(transcript_text, INVALID_NUMBER_KEYWORDS)
    suspended_flag = detect_keywords(transcript_text, SUSPENDED_KEYWORDS)
    fax_flag = detect_keywords(transcript_text, FAX_KEYWORDS)
    order_flag = detect_keywords(transcript_text, ORDER_KEYWORDS)
    hold_flag = detect_keywords(transcript_text, HOLD_KEYWORDS)
    agent_language_flag = detect_agent_language(transcript_text)

    script_value = clean_text(metadata_row.get("script_paneas"))
    product_value = clean_text(metadata_row.get("produto_oferta"))
    queue_value = clean_text(metadata_row.get("fila_atendimento_izzi"))
    island_value = clean_text(metadata_row.get("ilha_atendimento_izzi")) or queue_value
    contact_type_value = clean_text(metadata_row.get("tipo_contato_paneas"))
    call_datetime_value = clean_text(metadata_row.get("data_chamada_paneas"))
    operator_value = clean_text(metadata_row.get("operadora_telefone_paneas"))
    phone_value = clean_text(metadata_row.get("telefone_paneas"))
    exec_value = clean_text(metadata_row.get("id_exec_paneas"))
    agent_reported = clean_text(metadata_row.get("operador_izzi"))
    izzi_status_reportado = clean_text(metadata_row.get("status_contato_izzi"))
    izzi_status_normalizado = normalize_izzi_status(izzi_status_reportado or "")

    engagement_raw = (
        0.4 * safe_div(words_customer, word_count_total or 1)
        + 0.4 * safe_div(talk_customer, total_reference or 1.0)
        + 0.2 * safe_div(turn_count, total_segments or 1)
    )
    customer_engagement = round(min(1.0, max(0.0, engagement_raw)), 4)

    keyword_flags = {
        "voicemail": voicemail_flag,
        "invalid_number": invalid_number_flag,
        "suspended": suspended_flag,
        "fax": fax_flag,
        "order": order_flag,
        "agent_language": agent_language_flag,
        "hold": hold_flag,
    }
    actual_status = classify_actual_status(
        word_count_total,
        talk_by_role,
        words_by_role,
        role_segments,
        total_reference,
        transcript_text,
        keyword_flags,
        turn_count=turn_count,
        customer_after_agent=customer_after_agent,
    )
    expected_statuses = EXPECTED_STATUS_MAP.get(izzi_status_normalizado, tuple())
    divergent = 0 if not expected_statuses else int(actual_status not in expected_statuses)
    divergence_text = divergence_reason(izzi_status_normalizado, actual_status, expected_statuses) if divergent else None

    entry: Dict[str, Any] = {
        "call_id": call_id,
        "script": script_value,
        "product_offer": product_value,
        "queue": queue_value,
        "contact_type": contact_type_value,
        "call_datetime": call_datetime_value,
        "duration_seconds_metadata": round(duration_meta, 4),
        "duration_seconds_transcript": round(duration_transcript, 4),
        "duration_seconds_transcript_raw": round(duration_transcript_raw, 4),
        "duration_reference_seconds": round(total_reference, 4),
        "word_count_total": int(word_count_total),
        "unique_word_count": len(unique_words),
        "segment_count": total_segments,
        "turn_count": turn_count,
        "avg_words_per_segment": avg_words_per_segment,
        "avg_segment_duration": avg_segment_duration,
        "words_agent": words_agent,
        "words_customer": words_customer,
        "words_ivr": words_ivr,
        "talk_time_agent": round(talk_agent, 4),
        "talk_time_customer": round(talk_customer, 4),
        "talk_time_ivr": round(talk_ivr, 4),
        "silence_time_estimate": round(silence_time, 4),
        "silence_ratio": round(silence_ratio, 4),
        "talk_ratio_agent": round(safe_div(talk_agent, total_reference), 4),
        "talk_ratio_customer": round(safe_div(talk_customer, total_reference), 4),
        "talk_ratio_ivr": round(safe_div(talk_ivr, total_reference), 4),
        "speech_rate_agent_wpm": compute_speech_rate(words_agent, talk_agent),
        "speech_rate_customer_wpm": compute_speech_rate(words_customer, talk_customer),
        "customer_sentiment_score": 0.0,
        "customer_sentiment_label": "ausente",
        "agent_sentiment_score": 0.0,
        "agent_sentiment_label": "ausente",
        "customer_engagement_score": customer_engagement,
        "customer_after_agent": 1 if customer_after_agent else 0,
        "first_agent_start": round(first_agent_time, 4),
        "first_customer_start": round(first_customer_time, 4),
        "contains_voicemail_keywords": 1 if voicemail_flag else 0,
        "contains_invalid_number_keywords": 1 if invalid_number_flag else 0,
        "contains_suspension_keywords": 1 if suspended_flag else 0,
        "contains_fax_keywords": 1 if fax_flag else 0,
        "contains_order_keywords": 1 if order_flag else 0,
        "contains_hold_keywords": 1 if hold_flag else 0,
        "agent_language_detected": 1 if agent_language_flag else 0,
        "script_alignment_label": "unknown",
        "script_alignment_score": 0.0,
        "script_keyword_hits": 0,
        "script_keyword_total": 0,
        "script_keywords_matched": [],
        "operator_source_awareness": 0,
        "operator_source_awareness_level": 0,
        "operator_source_awareness_matches": [],
        "sales_pitch_score": 0.0,
        "sales_pitch_label": "unknown",
        "sales_pitch_topics": [],
        "follow_up_commitment": 0,
        "follow_up_actor": None,
        "follow_up_matches": [],
        "objection_handled": 0,
        "objection_handled_count": 0,
        "customer_anger_detected": 0,
        "customer_anger_matches": [],
        "izzi_status_reportado": izzi_status_reportado,
        "izzi_status_normalizado": izzi_status_normalizado,
        "status_real_detectado": actual_status,
        "divergente": divergent,
        "divergencia_motivo": divergence_text,
        "agent_name_detected": None,
        "agent_name_confidence": None,
        "customer_name_detected": None,
        "customer_name_confidence": None,
        "llm_enrichment_source": None,
        "operator": operator_value,
        "phone_number": phone_value,
        "exec_id": exec_value,
        "island": island_value,
    }
    # Prioridade: usar operador_izzi do CSV (dados oficiais e confiáveis)
    if agent_reported:
        entry["agent_name_detected"] = agent_reported
        entry["agent_name_confidence"] = 1.0
        entry["agent_name_source"] = "metadata"
    else:
        # Fallback: tentar detectar via LLM se CSV não tiver
        agent_name, agent_confidence = detect_identity_from_segments(segments, overrides, "agent")
        if agent_name:
            entry["agent_name_detected"] = agent_name
            entry["agent_name_confidence"] = round(agent_confidence, 3) if agent_confidence is not None else None
            entry["agent_name_source"] = "llm_detected"
    customer_name, customer_confidence = detect_identity_from_segments(segments, overrides, "customer")
    if customer_name:
        entry["customer_name_detected"] = customer_name
        entry["customer_name_confidence"] = round(customer_confidence, 3) if customer_confidence is not None else None
    return entry


def build_llm_prompt(
    call_id: str,
    transcript: Dict[str, Any],
    base_entry: Dict[str, Any],
) -> str:
    segments = transcript.get("segments") or []
    conversation = build_conversation_prompt(segments)
    metadata_context = {
        "call_id": call_id,
        "script": base_entry.get("script"),
        "product_offer": base_entry.get("product_offer"),
        "queue": base_entry.get("queue"),
        "contact_type": base_entry.get("contact_type"),
        "call_datetime": base_entry.get("call_datetime"),
        "izzi_status_reportado": base_entry.get("izzi_status_reportado"),
        "izzi_status_normalizado": base_entry.get("izzi_status_normalizado"),
    }
    metrics_context = {
        "baseline_status_real": base_entry.get("status_real_detectado"),
        "duration_seconds_metadata": base_entry.get("duration_seconds_metadata"),
        "duration_seconds_transcript": base_entry.get("duration_seconds_transcript"),
        "duration_seconds_transcript_raw": base_entry.get("duration_seconds_transcript_raw"),
        "talk_time_agent": base_entry.get("talk_time_agent"),
        "talk_time_customer": base_entry.get("talk_time_customer"),
        "talk_time_ivr": base_entry.get("talk_time_ivr"),
        "silence_time_estimate": base_entry.get("silence_time_estimate"),
        "silence_ratio": base_entry.get("silence_ratio"),
        "words_agent": base_entry.get("words_agent"),
        "words_customer": base_entry.get("words_customer"),
        "words_ivr": base_entry.get("words_ivr"),
        "customer_engagement_score": base_entry.get("customer_engagement_score"),
        "customer_after_agent": base_entry.get("customer_after_agent"),
        "contains_voicemail_keywords": base_entry.get("contains_voicemail_keywords"),
        "contains_invalid_number_keywords": base_entry.get("contains_invalid_number_keywords"),
        "contains_suspension_keywords": base_entry.get("contains_suspension_keywords"),
        "contains_fax_keywords": base_entry.get("contains_fax_keywords"),
        "contains_order_keywords": base_entry.get("contains_order_keywords"),
        "contains_hold_keywords": base_entry.get("contains_hold_keywords"),
        "agent_language_detected": base_entry.get("agent_language_detected"),
    }
    metadata_json = json.dumps(metadata_context, ensure_ascii=False, indent=2)
    metrics_json = json.dumps(metrics_context, ensure_ascii=False, indent=2)
    allowed_statuses = ", ".join(sorted(ALLOWED_STATUSES))
    return (
        "Você é um analista de qualidade. Combine os metadados, as métricas calculadas "
        "e a transcrição completa para gerar o registro final da chamada. "
        "Os valores numéricos fornecidos já estão corretos e devem ser mantidos; "
        "identifique apenas os campos analíticos (status real, sentimentos, script, follow-up etc.). "
        "Retorne **somente** um JSON com a estrutura abaixo:\n"
        "{\n"
        f'  "status_real_detectado": <string - use apenas: {allowed_statuses}>,\n'
        '  "customer_sentiment": {"label": "positive|neutral|negative|ausente", "score": <float -1..1>},\n'
        '  "agent_sentiment": {"label": "positive|neutral|negative|ausente", "score": <float -1..1>},\n'
        '  "script_followed": {"label": "aligned|partial|off_script|unknown", "confidence": <0..1>, "evidence": [strings]},\n'
        '  "source_awareness": {"detected": <bool>, "level": <0..2>, "evidence": [strings]},\n'
        '  "follow_up": {"detected": <bool>, "actor": "agent|customer|null", "summary": <string>},\n'
        '  "objection_handling": {"handled": <bool>, "count": <int>, "notes": <string>},\n'
        '  "customer_anger": {"detected": <bool>, "quotes": [strings]},\n'
        '  "sales_pitch": {"label": "weak|nominal|satisfactory|unknown", "score": <float>, "topics": [strings]},\n'
        '  "agent_identity": {"name": <string|null>, "confidence": <0..1>},\n'
        '  "customer_identity": {"name": <string|null>, "confidence": <0..1>},\n'
        '  "notes": <string>\n'
        "}\n"
        "Considere o campo 'baseline_status_real' como uma sugestão heurística; corrija para o valor mais adequado com base no diálogo.\n"
        "Para os campos de identidade, só informe o nome quando for citado explicitamente ou puder ser inferido com alta confiança; caso contrário retorne null.\n"
        "Regras de status:\n"
        " - Use 'dialogo_conectado' sempre que houver troca de falas agente ↔ cliente, mesmo que breve ou para recusa.\n"
        " - Use 'conectado_sem_cliente' somente quando o agente fala e não recebe resposta humana.\n"
        " - Use 'cliente_interagiu_sem_agente' quando apenas o cliente fala após o IVR.\n"
        " - Mantenha os demais status ('buzon', 'ivr_sem_interacao', etc.) conforme o comportamento dominante descrito na transcrição.\n"
        "Metadados principais da chamada:\n"
        f"{metadata_json}\n\n"
        "Métricas calculadas automaticamente (não altere os valores numéricos):\n"
        f"{metrics_json}\n\n"
        "Transcrição completa (um turno por linha):\n"
        f"{conversation}\n"
    )


def prepare_calls(
    call_ids: Iterable[str],
    metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    prepared: Dict[str, Dict[str, Any]] = {}
    for call_id in call_ids:
        if call_id not in metadata:
            raise KeyError(f"Metadados não encontrados para {call_id}")
        transcript = load_transcript(call_id)
        metadata_row = metadata[call_id]
        annotated_path = BASE_DIR / "diarization" / "output" / f"{call_id}.annotated.json"
        role_overrides: Dict[int, str] | None = None
        if annotated_path.exists():
            annotated = json.loads(annotated_path.read_text())
            segments = annotated.get("segments") or []
            role_overrides = {
                int(item.get("segment_index")): item.get("role")
                for item in segments
                if isinstance(item, dict) and item.get("role") in VALID_ROLES
            } or None
        base_entry = compute_base_entry(call_id, transcript, metadata_row, role_overrides=role_overrides)
        if role_overrides:
            base_entry["llm_segment_corrections"] = [
                {"index": idx, "role": role} for idx, role in role_overrides.items()
            ]
        prepared[call_id] = {
            "entry": base_entry,
            "transcript": transcript,
            "metadata": metadata_row,
            "role_overrides": role_overrides,
        }
    return prepared


def recompute_divergence(entry: Dict[str, Any]) -> None:
    normalized = entry.get("izzi_status_normalizado") or "desconhecido"
    actual = entry.get("status_real_detectado") or "desconhecido"
    expected = EXPECTED_STATUS_MAP.get(normalized, tuple())
    divergent = 0 if not expected else int(actual not in expected)
    entry["divergente"] = divergent
    entry["divergencia_motivo"] = divergence_reason(normalized, actual, expected) if divergent else None


def run_llm_pipeline(
    prepared: Dict[str, Dict[str, Any]],
    model: str,
    workers: int | None = None,
    quiet: bool = False,
) -> Tuple[List[Dict[str, Any]], int, List[Tuple[str, str]]]:
    if not prepared:
        return [], 0, []
    max_workers = max(1, workers or (os.cpu_count() or 4))
    total_targets = len(prepared)
    if not quiet:
        print(
            f"==> Executando {total_targets} chamadas com até {max_workers} worker(s) no modelo {model}...",
            flush=True,
        )
    successes = 0
    failures: List[Tuple[str, str]] = []
    results: Dict[str, Dict[str, Any]] = {}

    def task(call_id: str) -> Tuple[str, Dict[str, Any]]:
        data = prepared[call_id]
        prompt = build_llm_prompt(call_id, data["transcript"], data["entry"])
        entry = deepcopy(data["entry"])
        heuristic_status = entry.get("status_real_detectado") or "desconhecido"
        enrichment = call_openai(model, prompt)
        segment_corrections = apply_enrichment(entry, enrichment)
        final_status = resolve_status(entry, heuristic_status, enrichment.get("status_real_detectado"))
        entry["status_real_detectado"] = final_status
        if segment_corrections:
            overrides: Dict[int, str] = {}
            for item in segment_corrections:
                if not isinstance(item, dict):
                    continue
                idx = item.get("index")
                role = item.get("role")
                if isinstance(idx, int) and isinstance(role, str):
                    role_norm = role.strip().lower()
                    if role_norm in VALID_ROLES:
                        overrides[idx] = role_norm
            if overrides:
                recomputed = compute_base_entry(
                    call_id,
                    data["transcript"],
                    data["metadata"],
                    role_overrides=overrides,
                )
                for key, value in recomputed.items():
                    if key in LLM_PRESERVE_FIELDS:
                        continue
                    entry[key] = value
                entry["llm_segment_corrections"] = [
                    {"index": idx, "role": role} for idx, role in overrides.items()
                ]
        entry["llm_enrichment_source"] = "openai"
        if "status_real_detectado" not in entry or not entry["status_real_detectado"]:
            entry["status_real_detectado"] = "desconhecido"
        recompute_divergence(entry)
        return call_id, entry

    processed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(task, cid): cid for cid in prepared}
        for future in as_completed(futures):
            cid = futures[future]
            try:
                _, entry = future.result()
                results[cid] = entry
                successes += 1
                processed += 1
                if not quiet:
                    status = entry.get("status_real_detectado") or "desconhecido"
                    divergence_flag = "Divergente" if entry.get("divergente") else "OK"
                    print(
                        f"[{processed}/{total_targets}] ✅ {cid} → {status} ({divergence_flag})",
                        flush=True,
                    )
            except Exception as exc:  # pragma: no cover - falhas externas
                failures.append((cid, str(exc)))
                fallback = deepcopy(prepared[cid]["entry"])
                fallback["llm_enrichment_source"] = "llm_failed"
                recompute_divergence(fallback)
                results[cid] = fallback
                processed += 1
                if not quiet:
                    print(
                        f"[{processed}/{total_targets}] ⚠️ {cid} falhou: {exc}",
                        flush=True,
                    )

    per_call_details = [results[cid] for cid in sorted(results)]
    return per_call_details, successes, failures


def compute_dataset_summary(per_call_details: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_calls = len(per_call_details)
    if total_calls == 0:
        return {
            "total_calls": 0,
            "calls_with_agent": 0,
            "calls_with_customer_after_agent": 0,
            "ivr_only_calls": 0,
            "voicemail_detected_calls": 0,
            "customer_only_calls": 0,
            "connected_calls": 0,
            "connected_call_ratio": 0.0,
            "low_audio_transcription_calls": 0,
            "divergent_calls": 0,
            "divergence_rate": 0.0,
            "izzi_status_accuracy": 0.0,
            "total_duration_transcript_seconds": 0.0,
            "total_words_customer": 0,
            "total_words_agent": 0,
            "talk_ratio_customer": compute_statistics([]),
            "talk_ratio_agent": compute_statistics([]),
            "talk_ratio_ivr": compute_statistics([]),
            "silence_ratio": compute_statistics([]),
            "duration_transcription": compute_statistics([]),
            "customer_sentiment_score": compute_statistics([]),
            "agent_sentiment_score": compute_statistics([]),
            "customer_engagement_score": compute_statistics([]),
            "customer_sentiment_label_distribution": {},
            "agent_sentiment_label_distribution": {},
        }

    duration_meta = [float(entry.get("duration_seconds_metadata") or 0.0) for entry in per_call_details]
    duration_transcript = [float(entry.get("duration_seconds_transcript") or 0.0) for entry in per_call_details]
    duration_transcript_raw = [
        float(entry.get("duration_seconds_transcript_raw") or 0.0) for entry in per_call_details
    ]
    word_counts = [int(entry.get("word_count_total") or 0) for entry in per_call_details]
    unique_words = [int(entry.get("unique_word_count") or 0) for entry in per_call_details]
    segment_counts = [int(entry.get("segment_count") or 0) for entry in per_call_details]
    turn_counts = [int(entry.get("turn_count") or 0) for entry in per_call_details]
    customer_talk_times = [float(entry.get("talk_time_customer") or 0.0) for entry in per_call_details]
    agent_talk_times = [float(entry.get("talk_time_agent") or 0.0) for entry in per_call_details]
    ivr_talk_times = [float(entry.get("talk_time_ivr") or 0.0) for entry in per_call_details]
    silence_times = [float(entry.get("silence_time_estimate") or 0.0) for entry in per_call_details]
    silence_ratios = [float(entry.get("silence_ratio") or 0.0) for entry in per_call_details]
    customer_ratios = [float(entry.get("talk_ratio_customer") or 0.0) for entry in per_call_details]
    agent_ratios = [float(entry.get("talk_ratio_agent") or 0.0) for entry in per_call_details]
    ivr_ratios = [float(entry.get("talk_ratio_ivr") or 0.0) for entry in per_call_details]
    customer_rates = [float(entry.get("speech_rate_customer_wpm") or 0.0) for entry in per_call_details]
    agent_rates = [float(entry.get("speech_rate_agent_wpm") or 0.0) for entry in per_call_details]
    engagement_scores = [float(entry.get("customer_engagement_score") or 0.0) for entry in per_call_details]
    customer_sentiment_scores = [float(entry.get("customer_sentiment_score") or 0.0) for entry in per_call_details]
    agent_sentiment_scores = [float(entry.get("agent_sentiment_score") or 0.0) for entry in per_call_details]

    customer_labels = Counter(
        (entry.get("customer_sentiment_label") or "desconhecido") for entry in per_call_details
    )
    agent_labels = Counter(
        (entry.get("agent_sentiment_label") or "desconhecido") for entry in per_call_details
    )

    script_alignment_counts = Counter(
        (entry.get("script_alignment_label") or "unknown") for entry in per_call_details
    )
    applicable_script = total_calls - script_alignment_counts.get("unknown", 0)
    script_scores = [
        float(entry.get("script_alignment_score") or 0.0)
        for entry in per_call_details
        if (entry.get("script_alignment_label") or "unknown") != "unknown"
    ]
    script_alignment_score_avg = round(statistics.mean(script_scores), 4) if script_scores else 0.0

    sales_pitch_counts = Counter((entry.get("sales_pitch_label") or "unknown") for entry in per_call_details)
    sales_pitch_scores = [
        float(entry.get("sales_pitch_score") or 0.0)
        for entry in per_call_details
        if (entry.get("sales_pitch_label") or "unknown") != "unknown"
    ]
    sales_pitch_score_avg = round(statistics.mean(sales_pitch_scores), 4) if sales_pitch_scores else 0.0

    follow_up_commitment_calls = sum(1 for entry in per_call_details if entry.get("follow_up_commitment"))
    follow_up_by_agent = sum(1 for entry in per_call_details if entry.get("follow_up_actor") == "agent")
    follow_up_by_customer = sum(1 for entry in per_call_details if entry.get("follow_up_actor") == "customer")
    objection_handled_calls = sum(int(entry.get("objection_handled") or 0) for entry in per_call_details)
    objection_sequences_total = sum(int(entry.get("objection_handled_count") or 0) for entry in per_call_details)
    customer_anger_calls = sum(int(entry.get("customer_anger_detected") or 0) for entry in per_call_details)
    customer_anger_negative_overlap = sum(
        1
        for entry in per_call_details
        if entry.get("customer_anger_detected") and entry.get("customer_sentiment_label") == "negative"
    )

    calls_with_agent = sum(
        1
        for entry in per_call_details
        if float(entry.get("talk_time_agent") or 0.0) >= AGENT_TALK_THRESHOLD
        or int(entry.get("words_agent") or 0) >= AGENT_WORD_THRESHOLD
    )
    calls_with_customer_after_agent = sum(int(entry.get("customer_after_agent") or 0) for entry in per_call_details)

    status_counts = Counter((entry.get("status_real_detectado") or "desconhecido") for entry in per_call_details)
    ivr_only_calls = status_counts.get("ivr_sem_interacao", 0)
    voicemail_calls = status_counts.get("buzon", 0)
    invalid_number_calls = status_counts.get("numero_inexistente", 0)
    suspended_calls = status_counts.get("telefone_suspendido", 0)
    fax_calls = status_counts.get("fax_ou_contestadora", 0)
    order_calls = status_counts.get("orden_aberta", 0)
    customer_only_calls = status_counts.get("cliente_interagiu_sem_agente", 0)
    low_audio_calls = status_counts.get("sem_audio", 0)
    connected_calls = status_counts.get("dialogo_conectado", 0)

    divergent_calls = sum(int(entry.get("divergente") or 0) for entry in per_call_details)
    divergence_rate = safe_div(divergent_calls, total_calls)

    total_duration_transcript_seconds = round(sum(duration_transcript), 4)
    total_duration_metadata_seconds = round(sum(duration_meta), 4)
    total_words_customer = sum(int(entry.get("words_customer") or 0) for entry in per_call_details)
    total_words_agent = sum(int(entry.get("words_agent") or 0) for entry in per_call_details)
    total_words_ivr = sum(int(entry.get("words_ivr") or 0) for entry in per_call_details)
    total_silence_time_seconds = round(sum(silence_times), 4)
    total_turns = int(sum(turn_counts))

    product_distribution = Counter((entry.get("product_offer") or "desconhecido") for entry in per_call_details)
    operator_distribution = Counter((entry.get("operator") or "desconhecido") for entry in per_call_details)
    queue_distribution = Counter((entry.get("queue") or "desconhecido") for entry in per_call_details)

    hour_counter: Counter[int] = Counter()
    day_counter: Counter[str] = Counter()
    for entry in per_call_details:
        dt_str = entry.get("call_datetime")
        if not dt_str:
            continue
        try:
            dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            continue
        hour_counter[dt.hour] += 1
        day_counter[dt.strftime("%Y-%m-%d")] += 1

    unique_days = len(day_counter)
    avg_calls_per_day = round(safe_div(total_calls, unique_days or 1), 4) if unique_days else 0.0

    operator_source_awareness_calls = sum(int(entry.get("operator_source_awareness") or 0) for entry in per_call_details)
    operator_source_awareness_levels = Counter(
        int(entry.get("operator_source_awareness_level") or 0) for entry in per_call_details
    )

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
        "divergent_calls": divergent_calls,
        "divergence_rate": round(divergence_rate, 4),
        "izzi_status_accuracy": round(1.0 - divergence_rate, 4),
        "duration_metadata": compute_statistics(duration_meta),
        "duration_transcription": compute_statistics(duration_transcript),
        "duration_transcription_raw": compute_statistics(duration_transcript_raw),
        "word_count": compute_statistics(word_counts),
        "unique_word_count": compute_statistics(unique_words),
        "segment_count": compute_statistics(segment_counts),
        "turn_count": compute_statistics(turn_counts),
        "customer_talk_time": compute_statistics(customer_talk_times),
        "agent_talk_time": compute_statistics(agent_talk_times),
        "ivr_talk_time": compute_statistics(ivr_talk_times),
        "silence_time": compute_statistics(silence_times),
        "silence_ratio": compute_statistics(silence_ratios),
        "talk_ratio_customer": compute_statistics(customer_ratios),
        "talk_ratio_agent": compute_statistics(agent_ratios),
        "talk_ratio_ivr": compute_statistics(ivr_ratios),
        "customer_speech_rate_wpm": compute_statistics(customer_rates),
        "agent_speech_rate_wpm": compute_statistics(agent_rates),
        "customer_engagement_score": compute_statistics(engagement_scores),
        "customer_sentiment_score": compute_statistics(customer_sentiment_scores),
        "agent_sentiment_score": compute_statistics(agent_sentiment_scores),
        "total_duration_metadata_seconds": total_duration_metadata_seconds,
        "total_duration_transcript_seconds": total_duration_transcript_seconds,
        "total_words_customer": total_words_customer,
        "total_words_agent": total_words_agent,
        "total_words_ivr": total_words_ivr,
        "customer_sentiment_label_distribution": dict(customer_labels),
        "agent_sentiment_label_distribution": dict(agent_labels),
        "customer_positive_rate": round(safe_div(customer_labels.get("positive", 0), total_calls), 4),
        "customer_negative_rate": round(safe_div(customer_labels.get("negative", 0), total_calls), 4),
        "agent_positive_rate": round(safe_div(agent_labels.get("positive", 0), total_calls), 4),
        "agent_negative_rate": round(safe_div(agent_labels.get("negative", 0), total_calls), 4),
        "connected_calls": connected_calls,
        "connected_call_ratio": round(safe_div(connected_calls, total_calls), 4),
        "total_turns": total_turns,
        "total_silence_time_seconds": total_silence_time_seconds,
        "top_call_hours": sorted(hour_counter.items(), key=lambda x: (-x[1], x[0]))[:5],
        "product_offer_distribution": product_distribution.most_common(10),
        "operator_distribution": operator_distribution.most_common(10),
        "queue_distribution": queue_distribution.most_common(10),
        "calls_per_day": unique_days,
        "avg_calls_per_day": avg_calls_per_day,
        "script_alignment_counts": dict(script_alignment_counts),
        "script_alignment_applicable": applicable_script,
        "script_alignment_aligned_rate": round(
            safe_div(script_alignment_counts.get("aligned", 0), applicable_script or 1), 4
        )
        if applicable_script
        else 0.0,
        "script_alignment_off_script_rate": round(
            safe_div(script_alignment_counts.get("off_script", 0), applicable_script or 1), 4
        )
        if applicable_script
        else 0.0,
        "script_alignment_score_avg": script_alignment_score_avg,
        "operator_source_awareness_calls": operator_source_awareness_calls,
        "operator_source_awareness_rate": round(safe_div(operator_source_awareness_calls, total_calls), 4),
        "operator_source_awareness_level_distribution": {
            str(level): count for level, count in operator_source_awareness_levels.items()
        },
        "sales_pitch_distribution": dict(sales_pitch_counts),
        "sales_pitch_score_avg": sales_pitch_score_avg,
        "sales_pitch_satisfactory_rate": round(
            safe_div(sales_pitch_counts.get("satisfactory", 0), total_calls), 4
        ),
        "follow_up_commitment_calls": follow_up_commitment_calls,
        "follow_up_commitment_rate": round(safe_div(follow_up_commitment_calls, total_calls), 4),
        "follow_up_by_agent": follow_up_by_agent,
        "follow_up_by_customer": follow_up_by_customer,
        "objection_handled_calls": objection_handled_calls,
        "objection_handled_rate": round(safe_div(objection_handled_calls, total_calls), 4),
        "objection_sequences_total": objection_sequences_total,
        "customer_anger_calls": customer_anger_calls,
        "customer_anger_rate": round(safe_div(customer_anger_calls, total_calls), 4),
        "customer_anger_negative_sentiment_overlap": round(
            safe_div(customer_anger_negative_overlap, customer_anger_calls or 1), 4
        )
        if customer_anger_calls
        else 0.0,
    }
    return dataset_summary


def find_recurrence_window(calls: List[Dict[str, Any]]) -> Tuple[bool, datetime | None]:
    n_calls = len(calls)
    if n_calls < 3:
        return False, None
    for index in range(n_calls):
        start_date = calls[index]["date"]
        count = 1
        end_date = start_date
        for cursor in range(index + 1, n_calls):
            current_date = calls[cursor]["date"]
            if current_date - start_date <= RECURRENCE_WINDOW:
                count += 1
                end_date = current_date
            else:
                break
        if count >= 3:
            return True, end_date
    return False, None


def compute_primary_island(calls: List[Dict[str, Any]]) -> str:
    counter: Counter[str] = Counter()
    for call in calls:
        entry = call["entry"]
        island = (entry.get("island") or entry.get("queue") or "").strip()
        if not island:
            island = "Indefinido"
        counter[island] += 1
    if not counter:
        return "Indefinido"
    return counter.most_common(1)[0][0]


def compute_recurrence_summary(per_call_details: List[Dict[str, Any]]) -> Dict[str, Any]:
    timelines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for entry in per_call_details:
        phone = (entry.get("phone_number") or "").strip()
        if not phone:
            continue
        call_datetime = parse_call_datetime(entry.get("call_datetime"))
        if not call_datetime:
            continue
        timelines[phone].append({"date": call_datetime, "entry": entry})

    for phone, calls in timelines.items():
        calls.sort(key=lambda item: item["date"])

    total_followups = 0
    pending_followups = 0
    improductive_followups = 0
    pending_phones: set[str] = set()
    angry_clients: set[str] = set()
    angry_weekly: Dict[str, set[str]] = defaultdict(set)
    island_totals: Dict[str, set[str]] = defaultdict(set)
    island_recurrent: Dict[str, set[str]] = defaultdict(set)
    weekly_recurrence: Dict[str, Dict[str, Any]] = {}
    weekly_followups: Dict[str, Dict[str, Any]] = {}
    unresolved_complaints: set[str] = set()
    persistent_complaints: set[str] = set()
    dialogo_phones: set[str] = set()
    pitch_inconsistent: set[str] = set()
    script_never_aligned: set[str] = set()
    high_risk_clients: List[Dict[str, Any]] = []
    high_risk_set: set[str] = set()
    resolution_diffs: List[float] = []
    table_rows: List[Dict[str, Any]] = []

    for phone, calls in timelines.items():
        if not calls:
            continue
        primary_island = compute_primary_island(calls)
        island_totals[primary_island].add(phone)

        has_negative_sentiment = False
        anger_count = 0
        pitch_labels: set[str] = set()
        script_aligned_once = False
        dialogo_present = False
        divergent_all = True
        sentiments: List[float] = []

        for item in calls:
            entry = item["entry"]
            sentiment = entry.get("customer_sentiment_score")
            if isinstance(sentiment, (int, float)):
                sentiments.append(float(sentiment))
                if sentiment < NEGATIVE_SENTIMENT_THRESHOLD:
                    has_negative_sentiment = True
                if sentiment < HIGH_RISK_SENTIMENT_THRESHOLD:
                    pass
            if entry.get("customer_anger_detected"):
                anger_count += 1
                week_label, week_start = iso_week_info(item["date"])
                angry_weekly.setdefault(week_label, set()).add(phone)
            status_real = (entry.get("status_real_detectado") or "").strip().lower()
            if status_real == "dialogo_conectado":
                dialogo_present = True
                dialogo_phones.add(phone)
            if int(entry.get("divergente") or 0) != 1:
                divergent_all = False
            pitch_label = (entry.get("sales_pitch_label") or "").strip().lower()
            if pitch_label and pitch_label != "unknown":
                pitch_labels.add(pitch_label)
            if (entry.get("script_alignment_label") or "").strip().lower() == "aligned":
                script_aligned_once = True

        if anger_count >= 2:
            angry_clients.add(phone)

        if len(pitch_labels) > 1:
            pitch_inconsistent.add(phone)

        if not script_aligned_once:
            script_never_aligned.add(phone)

        recurrence_flag, recurrence_end = find_recurrence_window(calls)
        if recurrence_flag and recurrence_end:
            week_label, week_start = iso_week_info(recurrence_end)
            bucket = weekly_recurrence.setdefault(week_label, {"count": 0, "start": week_start})
            bucket["count"] += 1
            island_recurrent[primary_island].add(phone)

        last_call = calls[-1]
        last_entry = last_call["entry"]
        last_divergent = int(last_entry.get("divergente") or 0) == 1
        if last_divergent and has_negative_sentiment:
            unresolved_complaints.add(phone)
        if dialogo_present and has_negative_sentiment and divergent_all:
            persistent_complaints.add(phone)

        # Follow-up tracking
        client_follow_up_pending = False
        for index, call in enumerate(calls):
            entry = call["entry"]
            if int(entry.get("follow_up_commitment") or 0) != 1:
                continue
            total_followups += 1
            week_label, week_start = iso_week_info(call["date"])
            bucket = weekly_followups.setdefault(
                week_label,
                {"followups": 0, "pending": 0, "improductive": 0, "start": week_start},
            )
            bucket["followups"] += 1
            resolved = False
            improductive = False
            for next_call in calls[index + 1:]:
                diff = next_call["date"] - call["date"]
                if diff <= FOLLOW_UP_WINDOW:
                    improductive = True
                if int(next_call["entry"].get("divergente") or 0) == 0:
                    resolved = True
                    break
            if not resolved:
                pending_followups += 1
                client_follow_up_pending = True
                pending_phones.add(phone)
                bucket["pending"] += 1
            if improductive:
                improductive_followups += 1
                bucket["improductive"] += 1

        # Churn risk streak
        streak = 0
        best_streak = 0
        streak_start: datetime | None = None
        best_start: datetime | None = None
        best_end: datetime | None = None
        for call in calls:
            sentiment = call["entry"].get("customer_sentiment_score")
            if isinstance(sentiment, (int, float)) and sentiment < HIGH_RISK_SENTIMENT_THRESHOLD:
                if streak == 0:
                    streak_start = call["date"]
                streak += 1
                if streak > best_streak:
                    best_streak = streak
                    best_start = streak_start
                best_end = call["date"]
            else:
                streak = 0
        if best_streak >= 3 and best_start and best_end:
            high_risk_set.add(phone)
            high_risk_clients.append(
                {
                    "phone": phone,
                    "streak_length": best_streak,
                    "streak_start": best_start.isoformat(),
                    "streak_end": best_end.isoformat(),
                    "primary_island": primary_island,
                    "last_sentiment": last_entry.get("customer_sentiment_score"),
                }
            )

        # Resolution timing
        first_divergent_date: datetime | None = None
        for call in calls:
            if int(call["entry"].get("divergente") or 0) == 1 and not first_divergent_date:
                first_divergent_date = call["date"]
            if first_divergent_date and int(call["entry"].get("divergente") or 0) == 0:
                diff_days = (call["date"] - first_divergent_date).total_seconds() / 86400.0
                if diff_days >= 0:
                    resolution_diffs.append(diff_days)
                break

        if recurrence_flag:
            avg_sentiment = statistics.mean(sentiments) if sentiments else None
            table_rows.append(
                {
                    "phone": phone,
                    "total_calls": len(calls),
                    "first_call": calls[0]["date"].isoformat(),
                    "last_call": last_call["date"].isoformat(),
                    "average_sentiment": round(avg_sentiment, 4) if avg_sentiment is not None else None,
                    "current_divergence": int(last_entry.get("divergente") or 0),
                    "current_status": last_entry.get("status_real_detectado"),
                    "follow_up_pending": client_follow_up_pending,
                    "persistent_complaint": phone in persistent_complaints,
                    "unresolved_complaint": phone in unresolved_complaints,
                    "primary_island": primary_island,
                    "last_sentiment": last_entry.get("customer_sentiment_score"),
                    "customer_name": last_entry.get("customer_name_detected"),
                    "agent_name": last_entry.get("agent_name_detected"),
                    "churn_risk": phone in high_risk_set,
                }
            )

    total_phones = len(timelines)
    recurrent_count = len(table_rows)

    island_stats = []
    for island, phones in island_totals.items():
        total = len(phones)
        recurrent = len(island_recurrent.get(island, set()))
        percent = (recurrent / total) if total else 0.0
        island_stats.append(
            {
                "island": island,
                "recurrent_count": recurrent,
                "total_count": total,
                "percent": round(percent, 4),
            }
        )
    island_stats.sort(key=lambda item: (-item["recurrent_count"], item["island"]))

    weekly_trend_keys = set(weekly_recurrence.keys()) | set(weekly_followups.keys())
    weekly_trend = []
    for key in weekly_trend_keys:
        start = None
        if key in weekly_recurrence:
            start = weekly_recurrence[key]["start"]
        if key in weekly_followups:
            start = weekly_followups[key]["start"]
        weekly_trend.append(
            {
                "week": key,
                "week_start": (start.isoformat() if isinstance(start, datetime) else None),
                "reincidentes": weekly_recurrence.get(key, {}).get("count", 0),
                "followups_pendentes": weekly_followups.get(key, {}).get("pending", 0),
                "followups_improductivos": weekly_followups.get(key, {}).get("improductive", 0),
                "followups_totais": weekly_followups.get(key, {}).get("followups", 0),
            }
        )
    weekly_trend.sort(key=lambda item: item["week_start"] or "")

    angry_variation = 0
    if angry_weekly:
        ordered = sorted(
            ((key, len(value)) for key, value in angry_weekly.items()),
            key=lambda item: item[0],
        )
        if len(ordered) == 1:
            angry_variation = ordered[0][1]
        else:
            angry_variation = ordered[-1][1] - ordered[-2][1]

    avg_resolution_days = statistics.mean(resolution_diffs) if resolution_diffs else None

    table_rows.sort(key=lambda item: item["last_call"], reverse=True)
    top_clients = table_rows[:200]

    return {
        "total_phones": total_phones,
        "recurrent_clients": recurrent_count,
        "unresolved_complaints": len(unresolved_complaints),
        "persistent_complaints": len(persistent_complaints),
        "persistent_percent": round(
            (len(persistent_complaints) / len(dialogo_phones)) if dialogo_phones else 0.0, 4
        ),
        "followups_total": total_followups,
        "followups_pending": pending_followups,
        "followups_pending_percent": round(
            (pending_followups / total_followups) if total_followups else 0.0, 4
        ),
        "followups_improductive": improductive_followups,
        "followups_improductive_percent": round(
            (improductive_followups / total_followups) if total_followups else 0.0, 4
        ),
        "pending_followup_phones": sorted(pending_phones),
        "high_churn_clients": len(high_risk_set),
        "high_churn_details": high_risk_clients[:200],
        "avg_resolution_days": round(avg_resolution_days, 4) if avg_resolution_days is not None else None,
        "angry_recurring_clients": len(angry_clients),
        "angry_weekly_variation": angry_variation,
        "pitch_inconsistent_clients": len(pitch_inconsistent),
        "script_never_aligned_clients": len(script_never_aligned),
        "island_breakdown": island_stats,
        "weekly_trend": weekly_trend,
        "top_clients": top_clients,
    }


def compute_status_analysis(per_call_details: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_izzi: Dict[str, Dict[str, Any]] = {}
    actual_counter: Counter[str] = Counter()
    confusion: Counter[Tuple[str, str]] = Counter()

    for entry in per_call_details:
        izzi = entry.get("izzi_status_normalizado") or "desconhecido"
        actual = entry.get("status_real_detectado") or "desconhecido"
        divergence = 1 if entry.get("divergente") else 0

        record = by_izzi.setdefault(
            izzi,
            {"reported_count": 0, "matched_count": 0, "divergent_count": 0},
        )
        record["reported_count"] += 1
        if divergence:
            record["divergent_count"] += 1
        else:
            record["matched_count"] += 1

        actual_counter[actual] += 1
        confusion[(izzi, actual)] += 1

    for record in by_izzi.values():
        total = record["reported_count"] or 1
        record["match_rate"] = round(safe_div(record["matched_count"], total), 4)

    by_actual = {
        status: {
            "detected_count": count,
            "share": round(safe_div(count, len(per_call_details)), 4),
        }
        for status, count in actual_counter.items()
    }

    confusion_matrix = [
        {"izzi_status": izzi, "actual_status": actual, "count": count}
        for (izzi, actual), count in sorted(confusion.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]

    return {
        "by_izzi_status": by_izzi,
        "by_actual_status": by_actual,
        "confusion_matrix": confusion_matrix,
    }


def compute_divergence_summary(
    per_call_details: List[Dict[str, Any]],
    dataset_summary: Dict[str, Any],
) -> Dict[str, Any]:
    divergence_counter = Counter(
        entry.get("divergencia_motivo")
        for entry in per_call_details
        if entry.get("divergente") and entry.get("divergencia_motivo")
    )
    return {
        "total_divergent_calls": dataset_summary.get("divergent_calls", 0),
        "divergence_rate": dataset_summary.get("divergence_rate", 0.0),
        "divergence_breakdown": [
            {"reason": reason, "count": count}
            for reason, count in divergence_counter.most_common()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline LLM-first para full_analysis.json")
    parser.add_argument("--call-id", action="append", help="ID da chamada (pode ser usado várias vezes).")
    parser.add_argument("--all", action="store_true", help="Processa todas as chamadas disponíveis.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo OpenAI a utilizar.")
    parser.add_argument("--workers", type=int, default=None, help="Número de threads (default = núcleos da máquina).")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Pula o envio ao LLM e reaproveita o per_call_details existente apenas para recalcular métricas.",
    )
    args = parser.parse_args()

    if args.skip_llm:
        if not ENGINE_FILE.exists():
            raise FileNotFoundError("Arquivo engine/full_analysis.json não encontrado para reaproveitamento.")
        existing = json.loads(ENGINE_FILE.read_text())
        per_call_details = existing.get("per_call_details") or []
        if not per_call_details:
            raise ValueError("Arquivo existente não possui per_call_details para reaproveitar.")
        print(f"==> Reaproveitando {len(per_call_details)} chamadas existentes (skip LLM).")
    else:
        if not args.all and not args.call_id:
            parser.error("Informe --all ou pelo menos um --call-id.")

        metadata = load_metadata(METADATA_FILE)

        target_ids: List[str] = []
        if args.all:
            target_ids.extend(metadata.keys())
        if args.call_id:
            target_ids.extend(args.call_id)
        target_ids = sorted(set(target_ids))
        if not target_ids:
            raise ValueError("Nenhum call_id encontrado para processamento.")

        print(f"==> Preparando {len(target_ids)} chamada(s)...")
        prepared = prepare_calls(target_ids, metadata)

        print(f"==> Enviando chamadas ao LLM ({args.model})...")
        per_call_details, successes, failures = run_llm_pipeline(prepared, args.model, args.workers)
        print(f"==> LLM concluído. Sucesso: {successes} | Falhas: {len(failures)}")
        for cid, message in failures:
            print(f"   - {cid}: {message}")

    print("==> Calculando agregações...")
    dataset_summary = compute_dataset_summary(per_call_details)
    dataset_summary["recurrence_summary"] = compute_recurrence_summary(per_call_details)
    status_analysis = compute_status_analysis(per_call_details)
    divergence_summary = compute_divergence_summary(per_call_details, dataset_summary)

    data = {
        "dataset_summary": dataset_summary,
        "status_analysis": status_analysis,
        "divergence_summary": divergence_summary,
        "per_call_details": per_call_details,
    }

    ENGINE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    FRONTEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"==> Arquivo salvo em {ENGINE_FILE.relative_to(PROJECT_DIR)} e copiado para {FRONTEND_FILE.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    main()
