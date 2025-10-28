import asyncio
import json
import os
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import librosa
import numpy as np
from fastapi import FastAPI
from minio import Minio
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
import torch
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from prometheus_fastapi_instrumentator import Instrumentator


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

MODEL_ROOT_DEFAULT = os.environ.get("MODEL_ROOT", "/models")
SENTIMENT_MODEL_DEFAULT = os.environ.get(
    "SENTIMENT_MODEL_PATH",
    os.path.join(MODEL_ROOT_DEFAULT, "nlp/sentiment/twitter-xlm-roberta-base-sentiment"),
)
EMOTION_MODEL_DEFAULT = os.environ.get(
    "EMOTION_MODEL_PATH",
    os.path.join(MODEL_ROOT_DEFAULT, "nlp/emotion/robertuito-emotion-analysis"),
)
ZEROSHOT_MODEL_DEFAULT = os.environ.get(
    "ZEROSHOT_MODEL_PATH",
    os.path.join(MODEL_ROOT_DEFAULT, "nlp/zeroshot/xlm-roberta-large-xnli"),
)
MAX_TEXT_CHARS_DEFAULT = int(os.environ.get("ANALYTICS_MAX_TEXT_CHARS", "4000"))
COMPLIANCE_THRESHOLD_DEFAULT = float(os.environ.get("ANALYTICS_COMPLIANCE_THRESHOLD", "0.45"))


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------


class SpeechAnalyticsRequest(BaseModel):
    call_id: uuid.UUID
    audio_uri: str
    transcript_uri: str
    analysis_types: List[str]
    keywords: List[str] = Field(default_factory=list)


class SpeechAnalyticsJob(BaseModel):
    job_id: uuid.UUID
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.environ.get("MINIO_ROOT_USER", "aistack")
    minio_secret_key: str = os.environ.get("MINIO_ROOT_PASSWORD", "changeme")
    minio_secure: bool = os.environ.get("MINIO_SECURE", "false").lower() in {"1", "true", "yes", "on"}
    redis_host: str = os.environ.get("REDIS_HOST", "redis")
    redis_port: int = int(os.environ.get("REDIS_PORT", "6379"))
    redis_db: int = int(os.environ.get("REDIS_DB_CELERY", "1"))
    llm_host: str = os.environ.get("LLM_HOST", os.environ.get("LLM_INT4_HOST", "llm-int4"))
    llm_port: int = int(os.environ.get("LLM_PORT", os.environ.get("LLM_INT4_PORT", "8002")))
    llm_model: str = os.environ.get("LLM_MODEL", "paneas-v1")
    llm_max_tokens: int = int(os.environ.get("LLM_MAX_TOKENS", "512"))
    llm_timeout: float = float(os.environ.get("LLM_TIMEOUT", "15"))
    model_root: str = MODEL_ROOT_DEFAULT
    sentiment_model_path: str = SENTIMENT_MODEL_DEFAULT
    emotion_model_path: str = EMOTION_MODEL_DEFAULT
    zeroshot_model_path: str = ZEROSHOT_MODEL_DEFAULT
    max_text_chars: int = MAX_TEXT_CHARS_DEFAULT
    compliance_threshold: float = COMPLIANCE_THRESHOLD_DEFAULT
    max_concurrent_jobs: int = int(os.environ.get("ANALYTICS_MAX_CONCURRENCY", "4"))


SETTINGS = Settings()


# ---------------------------------------------------------------------------
# Heuristics & constants (still used for evidence)
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "bom",
    "boa",
    "excelente",
    "ótimo",
    "otimo",
    "positivo",
    "certo",
    "perfeito",
    "sucesso",
    "ganho",
    "feliz",
    "satisfeito",
    "agradecido",
    "obrigado",
    "obrigada",
    "claro",
    "interessante",
    "melhor",
}

NEGATIVE_WORDS = {
    "cancelar",
    "cancelamento",
    "ruim",
    "pior",
    "problema",
    "reclamação",
    "reclamacao",
    "insatisfeito",
    "caro",
    "trava",
    "falha",
    "demora",
    "lento",
    "não",
    "nao",
    "negativo",
    "duvida",
    "dúvida",
}

INTENT_KEYWORDS = {
    "cancelamento": {"cancelar", "cancelamento", "encerrar", "rescindir"},
    "upgrade": {"upgrade", "melhorar", "aumentar", "mudar plano", "plano melhor"},
    "downgrade": {"reduzir", "diminuir", "baixar plano", "baratear"},
    "suporte": {"problema", "suporte", "técnico", "falha", "reclamação"},
    "venda": {"promoção", "promo", "oferta", "contratar", "assinar", "plano novo"},
}

COMPLIANCE_CHECKS = [
    {
        "name": "greeting",
        "description": "o operador cumprimentou o cliente no início da chamada",
        "negative_description": "o operador não cumprimentou o cliente no início da chamada",
        "patterns": ["bom dia", "boa tarde", "boa noite", "olá", "ola"],
    },
    {
        "name": "operator_identification",
        "description": "o operador se identificou com nome e empresa",
        "negative_description": "o operador não se identificou com nome e empresa",
        "patterns": ["falo da claro", "sou da claro", "meu nome é", "meu nome e"],
    },
    {
        "name": "offer_presented",
        "description": "o operador apresentou uma oferta ou serviço",
        "negative_description": "o operador não apresentou nenhuma oferta ou serviço",
        "patterns": ["plano", "oferta", "promoção", "pacote", "fibra", "globoplay"],
    },
    {
        "name": "call_closure",
        "description": "o operador encerrou a chamada com despedida/pedido adicional",
        "negative_description": "o operador não encerrou a chamada com despedida ou pedido adicional",
        "patterns": ["mais alguma coisa", "posso ajudar", "obrigado pela ligação", "obrigada pela ligação", "boa noite", "bom dia"],
    },
]

INTENT_HYPOTHESES = {
    "cancelamento": (
        "o cliente deseja cancelar o serviço",
        "o cliente não deseja cancelar o serviço",
    ),
    "upgrade": (
        "o cliente quer fazer upgrade do plano",
        "o cliente não quer fazer upgrade do plano",
    ),
    "downgrade": (
        "o cliente quer reduzir o plano",
        "o cliente não quer reduzir o plano",
    ),
    "suporte": (
        "o cliente busca suporte técnico para resolver um problema",
        "o cliente não precisa de suporte técnico",
    ),
    "venda": (
        "o cliente está interessado em contratar ou comprar um serviço",
        "o cliente não está interessado em contratar ou comprar um serviço",
    ),
}

OUTCOME_HYPOTHESES = {
    "accepted": (
        "o cliente aceitou a proposta ou oferta",
        "o cliente não aceitou a proposta ou oferta",
    ),
    "rejected": (
        "o cliente recusou a proposta ou oferta",
        "o cliente não recusou a proposta ou oferta",
    ),
    "pending": (
        "o cliente ainda não decidiu sobre a proposta",
        "o cliente já decidiu sobre a proposta",
    ),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def safe_lower(text: str) -> str:
    return text.lower() if text else ""


def normalize_text(text: str) -> str:
    lowered = safe_lower(text)
    return (
        lowered.replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("ú", "u")
    )


def tokenize(text: str) -> List[str]:
    return [token for token in normalize_text(text).replace("\n", " ").split() if token]


def select_agent_speaker(segments: List[Dict[str, Any]]) -> Optional[str]:
    if not segments:
        return None
    speaker_durations: Dict[str, float] = defaultdict(float)
    for seg in segments:
        speaker = seg.get("speaker")
        if not speaker:
            continue
        start = float(seg.get("start") or 0.0)
        end = float(seg.get("end") or start)
        speaker_durations[speaker] += max(end - start, 0.0)
    if not speaker_durations:
        return None
    return max(speaker_durations.items(), key=lambda item: item[1])[0]


# ---------------------------------------------------------------------------
# NLP Model Hub
# ---------------------------------------------------------------------------


class NLPModelHub:
    def __init__(self, settings: Settings) -> None:
        self.device = 0 if torch.cuda.is_available() else -1
        self.sentiment_model, self.sentiment_tokenizer = self._load_sequence_model(settings.sentiment_model_path)
        self.emotion_model, self.emotion_tokenizer = self._load_sequence_model(settings.emotion_model_path)
        self.zeroshot_model, self.zeroshot_tokenizer = self._load_sequence_model(settings.zeroshot_model_path)

        self.sentiment_pipeline = pipeline(
            "text-classification",
            model=self.sentiment_model,
            tokenizer=self.sentiment_tokenizer,
            device=self.device,
        )
        self.emotion_pipeline = pipeline(
            "text-classification",
            model=self.emotion_model,
            tokenizer=self.emotion_tokenizer,
            device=self.device,
        )
        self.zeroshot_pipeline = pipeline(
            "zero-shot-classification",
            model=self.zeroshot_model,
            tokenizer=self.zeroshot_tokenizer,
            device=self.device,
        )

        self.sentiment_label_lookup = self._build_label_lookup(self.sentiment_model)
        self.emotion_label_lookup = self._build_label_lookup(self.emotion_model)

    @staticmethod
    def _load_sequence_model(path: str):
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        model = AutoModelForSequenceClassification.from_pretrained(
            path,
            local_files_only=True,
            torch_dtype=torch_dtype,
        )
        if torch.cuda.is_available():
            model = model.to("cuda")
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        model.eval()
        return model, tokenizer

    @staticmethod
    def _build_label_lookup(model: AutoModelForSequenceClassification) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for idx, label in model.config.id2label.items():
            canonical = label.lower()
            lookup[label.lower()] = canonical
            lookup[label.upper()] = canonical
            lookup[f"label_{idx}"] = canonical
            lookup[f"LABEL_{idx}"] = canonical
        return lookup

    def sentiment_scores(self, text: str) -> Dict[str, float]:
        if not text.strip():
            return {}
        outputs = self.sentiment_pipeline(text, top_k=None, truncation=True)
        if outputs and isinstance(outputs[0], list):
            outputs = outputs[0]
        scores: Dict[str, float] = {}
        for item in outputs:
            label = item["label"]
            canonical = self.sentiment_label_lookup.get(label, label.lower())
            scores[canonical] = float(item["score"])
        return scores

    def emotion_scores(self, text: str) -> Dict[str, float]:
        if not text.strip():
            return {}
        outputs = self.emotion_pipeline(text, top_k=None, truncation=True)
        if outputs and isinstance(outputs[0], list):
            outputs = outputs[0]
        scores: Dict[str, float] = {}
        for item in outputs:
            label = item["label"]
            canonical = self.emotion_label_lookup.get(label, label.lower())
            scores[canonical] = float(item["score"])
        return scores

    def zero_shot_scores(
        self,
        text: str,
        candidate_map: Dict[str, str],
        *,
        multi_label: bool,
        template: str,
    ) -> Dict[str, float]:
        if not text.strip():
            return {key: 0.0 for key in candidate_map}
        result = self.zeroshot_pipeline(
            text,
            candidate_labels=list(candidate_map.values()),
            multi_label=multi_label,
            hypothesis_template=template,
        )
        labels = result["labels"]
        scores = result["scores"]
        mapped: Dict[str, float] = {}
        for key, description in candidate_map.items():
            if description in labels:
                idx = labels.index(description)
                mapped[key] = float(scores[idx])
            else:
                mapped[key] = 0.0
        return mapped

    def zero_shot_probability(self, text: str, positive: str, negative: str, template: str) -> float:
        if not text.strip():
            return 0.0
        result = self.zeroshot_pipeline(
            text,
            candidate_labels=[positive, negative],
            multi_label=False,
            hypothesis_template=template,
        )
        labels = result["labels"]
        scores = result["scores"]
        if positive in labels:
            return float(scores[labels.index(positive)])
        return 0.0


# ---------------------------------------------------------------------------
# Analytics Engine
# ---------------------------------------------------------------------------


class AnalyticsEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.redis: Optional[Redis] = None
        self.llm = AsyncLLMClient(
            host=settings.llm_host,
            port=settings.llm_port,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
        )
        self.nlp = NLPModelHub(settings)
        self._job_semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_jobs))
        self._inflight_tasks: set[asyncio.Task[Any]] = set()

    async def connect(self) -> None:
        self.redis = Redis(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
            db=self.settings.redis_db,
            decode_responses=True,
        )

    async def close(self) -> None:
        if self._inflight_tasks:
            await asyncio.gather(*self._inflight_tasks, return_exceptions=True)
        if self.redis:
            await self.redis.close()
        await self.llm.aclose()

    async def submit_job(self, payload: SpeechAnalyticsRequest) -> uuid.UUID:
        job_id = uuid.uuid4()
        await self._set_status(job_id, {"status": "processing"})
        task = asyncio.create_task(self._run_job(job_id, payload))
        task.add_done_callback(self._inflight_tasks.discard)
        self._inflight_tasks.add(task)
        return job_id

    async def get_job(self, job_id: uuid.UUID) -> SpeechAnalyticsJob:
        if not self.redis:
            raise RuntimeError("Redis client not initialized")
        raw = await self.redis.get(f"analytics:{job_id}")
        if not raw:
            return SpeechAnalyticsJob(job_id=job_id, status="not_found")
        data = json.loads(raw)
        return SpeechAnalyticsJob(job_id=job_id, status=data.get("status", "unknown"), results=data.get("results"), error=data.get("error"))

    async def _set_status(self, job_id: uuid.UUID, payload: Dict[str, Any]) -> None:
        if not self.redis:
            raise RuntimeError("Redis client not initialized")
        await self.redis.set(f"analytics:{job_id}", json.dumps(payload))

    async def _store_result(self, job_id: uuid.UUID, payload: Dict[str, Any]) -> None:
        await self._set_status(job_id, payload)

    async def _run_job(self, job_id: uuid.UUID, payload: SpeechAnalyticsRequest) -> None:
        async with self._job_semaphore:
            await self._process_job(job_id, payload)

    async def _process_job(self, job_id: uuid.UUID, payload: SpeechAnalyticsRequest) -> None:
        temp_audio: Optional[Path] = None
        try:
            audio_path, temp_audio = await asyncio.to_thread(self._download_audio, payload.audio_uri)
            transcript = await asyncio.to_thread(self._load_transcript, payload.transcript_uri)
            segments = transcript.get("segments") or []
            raw_text = (transcript.get("text") or " ".join(seg.get("text", "") for seg in segments)).strip()
            raw_text = self._truncate_text(raw_text, max_chars=self.settings.max_text_chars)

            feature_context = {
                "call_id": str(payload.call_id),
                "segments": segments,
                "text": raw_text,
                "keywords": payload.keywords,
                "analysis_types": set(payload.analysis_types),
            }

            results: Dict[str, Any] = {}

            if "keywords" in payload.analysis_types:
                results["keywords"] = self._compute_keywords(feature_context)

            if "vad_advanced" in payload.analysis_types:
                results["acoustic"] = self._compute_acoustic_metrics(audio_path, segments, raw_text)

            sentiment_payload = None
            if "sentiment" in payload.analysis_types:
                sentiment_payload = self._compute_sentiment(feature_context)
                results["sentiment"] = sentiment_payload

            if "emotion" in payload.analysis_types:
                results["emotion"] = self._compute_emotion(feature_context)

            if "intent" in payload.analysis_types or "outcome" in payload.analysis_types:
                intent_payload = self._compute_intents(feature_context)
                results["intent"] = intent_payload

            if "compliance" in payload.analysis_types:
                results["compliance"] = self._check_compliance(feature_context)

            if "summary" in payload.analysis_types:
                results["summary"] = await self._generate_summary(feature_context, sentiment_payload)

            results["timeline"] = self._build_timeline(feature_context, results)

            await self._store_result(job_id, {"status": "completed", "results": results})
        except Exception as exc:  # noqa: BLE001
            await self._store_result(job_id, {"status": "failed", "error": str(exc)})
        finally:
            if temp_audio and temp_audio.exists():
                temp_audio.unlink(missing_ok=True)

    # ----------------------------------------------------------------------
    # Data loading helpers
    # ----------------------------------------------------------------------

    def _download_audio(self, uri: str) -> Tuple[Path, Optional[Path]]:
        if uri.startswith("s3://"):
            bucket, _, object_name = uri[5:].partition("/")
            tmp = Path(tempfile.mkstemp(prefix="analytics_audio_", suffix=Path(object_name).suffix or ".wav")[1])
            self.minio.fget_object(bucket, object_name, str(tmp))
            return tmp, tmp
        path = Path(uri)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {uri}")
        return path, None

    def _load_transcript(self, uri: str) -> Dict[str, Any]:
        data: Optional[bytes] = None
        if uri.startswith("s3://"):
            bucket, _, object_name = uri[5:].partition("/")
            response = self.minio.get_object(bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
        else:
            path = Path(uri)
            if not path.exists():
                raise FileNotFoundError(f"Transcript not found: {uri}")
            data = path.read_bytes()

        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {"text": data.decode("utf-8", errors="ignore")}

        text = payload.get("text", "")
        segments = payload.get("segments") or []
        return {"text": text, "segments": segments}

    # ----------------------------------------------------------------------
    # Feature extraction
    # ----------------------------------------------------------------------

    def _truncate_text(self, text: str, max_chars: Optional[int] = None) -> str:
        limit = max_chars or self.settings.max_text_chars
        if len(text) <= limit:
            return text
        return text[:limit]

    def _collect_speaker_texts(self, segments: List[Dict[str, Any]], fallback: str) -> Dict[str, str]:
        if not segments:
            return {"unknown": fallback}
        speaker_texts: Dict[str, str] = defaultdict(str)
        for seg in segments:
            speaker = seg.get("speaker") or "unknown"
            speaker_texts[speaker] += " " + seg.get("text", "")
        return {speaker: text.strip() for speaker, text in speaker_texts.items()}

    def _compute_keywords(self, context: Dict[str, Any]) -> Dict[str, Any]:
        text = normalize_text(context["text"])
        segments = context["segments"]
        keywords = [normalize_text(k) for k in context.get("keywords", [])]
        keyword_hits: Dict[str, int] = {}
        keyword_positions: Dict[str, Optional[float]] = {}
        for keyword in keywords:
            if not keyword:
                continue
            occurrences = text.count(keyword)
            if occurrences:
                keyword_hits[keyword] = occurrences
                keyword_positions[keyword] = self._find_keyword_timestamp(keyword, segments)
        return {
            "searched": keywords,
            "occurrences": keyword_hits,
            "positions": keyword_positions,
        }

    def _compute_acoustic_metrics(self, audio_path: Path, segments: List[Dict[str, Any]], raw_text: str) -> Dict[str, Any]:
        data, sr = librosa.load(audio_path, sr=16000)
        duration = len(data) / sr if len(data) else 0.0
        non_silent = librosa.effects.split(data, top_db=30)

        speaking_duration = float(sum((end - start) for start, end in non_silent)) / sr if len(non_silent) else 0.0
        speech_ratio = speaking_duration / duration if duration else 0.0

        silence_segments: List[Dict[str, float]] = []
        prev_end = 0
        for start, end in non_silent:
            if start > prev_end:
                silence_segments.append(
                    {"start": round(prev_end / sr, 3), "end": round(start / sr, 3), "duration": round((start - prev_end) / sr, 3)}
                )
            prev_end = end
        if prev_end < len(data):
            silence_segments.append(
                {"start": round(prev_end / sr, 3), "end": round(len(data) / sr, 3), "duration": round((len(data) - prev_end) / sr, 3)}
            )

        try:
            pitch_values = librosa.yin(data, fmin=60, fmax=400, sr=sr)
            avg_pitch = float(np.nanmean(pitch_values))
        except Exception:  # noqa: BLE001
            avg_pitch = 0.0

        words = len(raw_text.split()) or 1
        speech_rate_wpm = (words / (duration / 60.0)) if duration else 0.0

        speaker_stats = self._compute_speaker_stats(segments)

        return {
            "duration_seconds": round(duration, 3),
            "speech_ratio": round(speech_ratio, 3),
            "speech_rate_wpm": round(speech_rate_wpm, 2),
            "average_pitch_hz": round(avg_pitch, 2),
            "silence_segments": silence_segments,
            "speaker_activity": speaker_stats,
        }

    def _compute_speaker_stats(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        stats: Dict[str, Dict[str, float]] = {}
        for seg in segments:
            speaker = seg.get("speaker") or "unknown"
            start = float(seg.get("start") or 0.0)
            end = float(seg.get("end") or start)
            stats.setdefault(speaker, {"total_seconds": 0.0, "turns": 0})
            stats[speaker]["total_seconds"] += max(end - start, 0.0)
            stats[speaker]["turns"] += 1
        return {speaker: {"total_seconds": round(v["total_seconds"], 3), "turns": v["turns"]} for speaker, v in stats.items()}

    def _compute_sentiment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        segments = context["segments"]
        raw_text = context["text"]
        speaker_texts = self._collect_speaker_texts(segments, raw_text)

        per_speaker: Dict[str, Any] = {}
        aggregated_scores: Dict[str, float] = defaultdict(float)
        total_tokens = 0

        for speaker, text in speaker_texts.items():
            truncated = self._truncate_text(text)
            scores = self.nlp.sentiment_scores(truncated)
            tokens = max(len(text.split()), 1)
            positive_terms = sum(1 for token in tokenize(text) if token in POSITIVE_WORDS)
            negative_terms = sum(1 for token in tokenize(text) if token in NEGATIVE_WORDS)

            label = max(scores.items(), key=lambda x: x[1])[0] if scores else "neutral"
            score_delta = scores.get("positive", 0.0) - scores.get("negative", 0.0)
            per_speaker[speaker] = {
                "label": label,
                "scores": {k: round(v, 4) for k, v in scores.items()},
                "score": round(score_delta, 4),
                "tokens": tokens,
                "positive_terms": positive_terms,
                "negative_terms": negative_terms,
            }

            for lbl, value in scores.items():
                aggregated_scores[lbl] += value * tokens
            total_tokens += tokens

        if not aggregated_scores or total_tokens == 0:
            return {"overall": {"label": "neutral", "score": 0.0, "total_tokens": total_tokens}, "per_speaker": per_speaker}

        averaged = {lbl: value / total_tokens for lbl, value in aggregated_scores.items()}
        overall_label, _ = max(averaged.items(), key=lambda x: x[1])
        overall_probs = {k: round(v, 4) for k, v in averaged.items()}
        overall_delta = overall_probs.get("positive", 0.0) - overall_probs.get("negative", 0.0)
        return {
            "overall": {
                "label": overall_label,
                "score": round(overall_delta, 4),
                "total_tokens": total_tokens,
                "probabilities": overall_probs,
            },
            "per_speaker": per_speaker,
        }

    def _compute_emotion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        segments = context["segments"]
        raw_text = context["text"]
        speaker_texts = self._collect_speaker_texts(segments, raw_text)

        per_speaker: Dict[str, Any] = {}
        aggregate: Dict[str, float] = defaultdict(float)
        total = 0

        for speaker, text in speaker_texts.items():
            truncated = self._truncate_text(text)
            scores = self.nlp.emotion_scores(truncated)
            if not scores:
                continue
            label, value = max(scores.items(), key=lambda x: x[1])
            per_speaker[speaker] = {
                "label": label,
                "score": round(value, 4),
                "scores": {k: round(v, 4) for k, v in scores.items()},
            }
            aggregate[label] += value
            total += 1

        if not aggregate or total == 0:
            return {"overall": {"label": "unknown", "confidence": 0.0}, "per_speaker": per_speaker}

        overall_label, total_score = max(aggregate.items(), key=lambda x: x[1])
        confidence = min(1.0, total_score / total)
        return {
            "overall": {"label": overall_label, "confidence": round(confidence, 4)},
            "per_speaker": per_speaker,
        }

    def _compute_intents(self, context: Dict[str, Any]) -> Dict[str, Any]:
        text = self._truncate_text(context["text"])

        intents: Dict[str, Any] = {}
        for label, (positive, negative) in INTENT_HYPOTHESES.items():
            score = self.nlp.zero_shot_probability(text, positive, negative, "A conversa indica que {}.")
            evidence = [kw for kw in INTENT_KEYWORDS.get(label, set()) if kw in text.lower()]
            intents[label] = {"score": round(score, 4), "evidence": evidence}

        outcome_scores = {
            label: self.nlp.zero_shot_probability(text, positive, negative, "A conversa indica que {}.")
            for label, (positive, negative) in OUTCOME_HYPOTHESES.items()
        }
        outcome_label, outcome_score = max(outcome_scores.items(), key=lambda x: x[1])
        return {
            "intents": intents,
            "outcome": {
                "label": outcome_label,
                "score": round(outcome_score, 4),
                "evidence": intents.get(outcome_label, {}).get("evidence", []),
            },
        }

    def _check_compliance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        agent_speaker = select_agent_speaker(context["segments"])
        if agent_speaker:
            agent_text = " ".join(seg.get("text", "") for seg in context["segments"] if seg.get("speaker") == agent_speaker)
        else:
            agent_text = context["text"]

        agent_text = self._truncate_text(agent_text)
        if not agent_text.strip():
            details = [
                {"name": check["name"], "description": check["description"], "patterns": check["patterns"], "passed": False, "score": 0.0}
                for check in COMPLIANCE_CHECKS
            ]
            return {"passed": [], "failed": [check["name"] for check in COMPLIANCE_CHECKS], "score": 0.0, "details": details}

        passed: List[str] = []
        failed: List[str] = []
        details: List[Dict[str, Any]] = []

        for check in COMPLIANCE_CHECKS:
            score = self.nlp.zero_shot_probability(
                agent_text,
                check["description"],
                check["negative_description"],
                "Durante a ligação, {}.",
            )
            is_passed = score >= self.settings.compliance_threshold
            (passed if is_passed else failed).append(check["name"])
            evidence = [pattern for pattern in check["patterns"] if pattern in normalize_text(agent_text)]
            details.append(
                {
                    "name": check["name"],
                    "description": check["description"],
                    "patterns": check["patterns"],
                    "passed": is_passed,
                    "score": round(score, 4),
                    "evidence": evidence,
                }
            )

        compliance_score = len(passed) / max(len(COMPLIANCE_CHECKS), 1)
        return {"passed": passed, "failed": failed, "score": round(compliance_score, 4), "details": details}

    async def _generate_summary(self, context: Dict[str, Any], sentiment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        text = self._truncate_text(context["text"], max_chars=6000)
        if not text:
            return {"summary": [], "next_actions": [], "confidence": 0.0}

        sentiment_label = sentiment["overall"]["label"] if sentiment else "desconhecido"
        system_prompt = (
            "Você é um analista de qualidade que resume chamadas de call center em português/espanhol. "
            "Gere respostas objetivas, confidenciais e sem inventar dados."
        )
        user_prompt = (
            "Transcrição da chamada:\n"
            f"{text}\n\n"
            f"Sentimento geral detectado automaticamente: {sentiment_label}.\n"
            "Resuma em até 3 tópicos os principais acontecimentos da chamada e proponha até 3 próximos passos práticos para o operador ou gestor.\n"
            "Formato de resposta JSON com campos `summary` (lista de frases) e `next_actions` (lista de frases)."
        )
        try:
            response_text = await self.llm.chat(system_prompt, user_prompt, max_tokens=min(self.settings.llm_max_tokens, 256))
        except Exception:
            response_text = ""

        summary = {"summary": [], "next_actions": [], "confidence": 0.5}
        if response_text:
            try:
                parsed = json.loads(response_text)
                summary["summary"] = parsed.get("summary") or parsed.get("resumo") or []
                summary["next_actions"] = parsed.get("next_actions") or parsed.get("proximos_passos") or []
                summary["confidence"] = 0.8
            except json.JSONDecodeError:
                sentences = [sent.strip() for sent in response_text.split("\n") if sent.strip()]
                summary["summary"] = sentences[:3]
                summary["next_actions"] = sentences[3:6]
                summary["confidence"] = 0.6
        else:
            summary["summary"] = [text[:200] + ("..." if len(text) > 200 else "")]

        return summary

    def _build_timeline(self, context: Dict[str, Any], results: Dict[str, Any]) -> List[Dict[str, Any]]:
        segments = context["segments"]
        timeline: List[Dict[str, Any]] = []

        keyword_result = results.get("keywords", {})
        for keyword, ts in (keyword_result.get("positions") or {}).items():
            timeline.append(
                {
                    "timestamp": ts,
                    "type": "keyword",
                    "label": keyword,
                    "confidence": 0.6,
                    "metadata": {"keyword": keyword},
                }
            )

        intent_result = results.get("intent", {}).get("intents", {})
        for label, info in intent_result.items():
            score = info.get("score", 0.0)
            if score < 0.4:
                continue
            ts = self._find_keyword_timestamp(label, segments)
            timeline.append(
                {
                    "timestamp": ts,
                    "type": "intent",
                    "label": label,
                    "confidence": min(1.0, score),
                    "metadata": {"score": round(score, 4), "evidence": info.get("evidence", [])},
                }
            )

        compliance = results.get("compliance", {})
        for detail in compliance.get("details", []):
            if not detail.get("passed"):
                timeline.append(
                    {
                        "timestamp": None,
                        "type": "compliance_gap",
                        "label": detail["name"],
                        "confidence": detail.get("score", 0.4),
                        "metadata": {"description": detail["description"]},
                    }
                )

        outcome = results.get("intent", {}).get("outcome")
        if outcome:
            timeline.append(
                {
                    "timestamp": None,
                    "type": "outcome",
                    "label": outcome.get("label"),
                    "confidence": outcome.get("score", 0.5),
                    "metadata": {
                        "score": round(outcome.get("score", 0.0), 4),
                        "evidence": outcome.get("evidence", []),
                    },
                }
            )

        timeline.sort(key=lambda item: (float("inf") if item["timestamp"] is None else item["timestamp"]))
        return timeline

    def _find_keyword_timestamp(self, keyword: str, segments: List[Dict[str, Any]]) -> Optional[float]:
        if not keyword:
            return None
        normalized_kw = normalize_text(keyword)
        for seg in segments:
            segment_text = normalize_text(seg.get("text", ""))
            if normalized_kw in segment_text:
                start = seg.get("start")
                if start is not None:
                    return round(float(start), 3)
        return None


# ---------------------------------------------------------------------------
# Async LLM client (existing behaviour)
# ---------------------------------------------------------------------------


class AsyncLLMClient:
    """Minimal vLLM-compatible client to reuse paneas LLM endpoints."""

    def __init__(self, *, host: str, port: int, model: str, timeout: float) -> None:
        self._endpoint = f"http://{host}:{port}/v1/chat/completions"
        self._model = model
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._retry_kwargs = {
            "stop": stop_after_attempt(3),
            "wait": wait_exponential(multiplier=0.5, min=0.5, max=4),
            "retry": retry_if_exception_type((httpx.RequestError,)),
            "reraise": True,
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 256) -> str:
        client = await self._ensure_client()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        async for attempt in AsyncRetrying(**self._retry_kwargs):
            with attempt:
                try:
                    response = await client.post(
                        self._endpoint,
                        json=payload,
                        timeout=self._timeout,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if 500 <= exc.response.status_code < 600:
                        # Treat 5xx as retryable transport-level failures.
                        raise httpx.RequestError(str(exc)) from exc
                    raise

                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise httpx.RequestError("LLM response did not contain choices")
                return (choices[0].get("message") or {}).get("content", "").strip()

        return ""  # pragma: no cover

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


app = FastAPI(title="Speech Analytics Service", version="3.0.0")
Instrumentator().instrument(app).expose(app, include_in_schema=False)
engine = AnalyticsEngine(SETTINGS)


@app.on_event("startup")
async def startup() -> None:
    await engine.connect()


@app.on_event("shutdown")
async def shutdown() -> None:
    await engine.close()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "up"}


@app.post("/analytics/speech", status_code=202)
async def submit(payload: SpeechAnalyticsRequest) -> Dict[str, Any]:
    job_id = await engine.submit_job(payload)
    return {"job_id": str(job_id), "status": "processing"}


@app.get("/analytics/speech/{job_id}")
async def get_job(job_id: uuid.UUID) -> Dict[str, Any]:
    job = await engine.get_job(job_id)
    response: Dict[str, Any] = {"job_id": str(job.job_id), "status": job.status}
    if job.results is not None:
        response["results"] = job.results
    if job.error is not None:
        response["error"] = job.error
    return response
