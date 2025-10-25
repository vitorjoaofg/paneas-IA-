import json
from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="production", alias="ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    stack_version: str = Field(default="1.0.0", alias="STACK_VERSION")

    api_tokens: List[str] = Field(default_factory=list, alias="API_TOKENS")

    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="aistack", alias="POSTGRES_DB")
    postgres_user: str = Field(default="aistack", alias="POSTGRES_USER")
    postgres_password: str = Field(default="changeme", alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db_cache: int = Field(default=0, alias="REDIS_DB_CACHE")
    redis_db_celery: int = Field(default=1, alias="REDIS_DB_CELERY")

    minio_endpoint: str = Field(default="minio:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="aistack", alias="MINIO_ROOT_USER")
    minio_secret_key: str = Field(default="changeme", alias="MINIO_ROOT_PASSWORD")
    minio_bucket_audio: str = Field(default="audio", alias="MINIO_BUCKET_AUDIO")
    minio_bucket_documents: str = Field(default="documents", alias="MINIO_BUCKET_DOCUMENTS")
    minio_bucket_artifacts: str = Field(default="artifacts", alias="MINIO_BUCKET_ARTIFACTS")
    minio_secure: bool = Field(default=False)

    otel_endpoint: AnyHttpUrl | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")

    rate_limit_global: int = Field(default=1000, alias="RATE_LIMIT_GLOBAL")
    rate_limit_asr: int = Field(default=100, alias="RATE_LIMIT_ASR")
    rate_limit_ocr: int = Field(default=50, alias="RATE_LIMIT_OCR")
    rate_limit_llm: int = Field(default=200, alias="RATE_LIMIT_LLM")
    rate_limit_tts: int = Field(default=80, alias="RATE_LIMIT_TTS")

    llm_fp16_host: str = Field(default="llm-fp16", alias="LLM_FP16_HOST")
    llm_fp16_port: int = Field(default=8001, alias="LLM_FP16_PORT")
    llm_int4_host: str = Field(default="llm-int4", alias="LLM_INT4_HOST")
    llm_int4_port: int = Field(default=8002, alias="LLM_INT4_PORT")
    llm_max_tokens: int = Field(default=16384, alias="LLM_MAX_TOKENS")
    llm_routing_strategy: str = Field(default="auto", alias="LLM_ROUTING_STRATEGY")

    asr_host: str = Field(default="asr", alias="ASR_HOST")
    asr_port: int = Field(default=9000, alias="ASR_PORT")
    asr_default_model: str = Field(default="large-v3-turbo", alias="ASR_DEFAULT_MODEL")
    asr_compute_type: str = Field(default="fp16", alias="ASR_COMPUTE_TYPE")

    tts_host: str = Field(default="tts", alias="TTS_HOST")
    tts_port: int = Field(default=9001, alias="TTS_PORT")

    align_host: str = Field(default="align", alias="ALIGN_HOST")
    align_port: int = Field(default=9002, alias="ALIGN_PORT")

    diar_host: str = Field(default="diar", alias="DIAR_HOST")
    diar_port: int = Field(default=9003, alias="DIAR_PORT")

    ocr_host: str = Field(default="ocr", alias="OCR_HOST")
    ocr_port: int = Field(default=9004, alias="OCR_PORT")

    analytics_host: str = Field(default="analytics", alias="ANALYTICS_HOST")
    analytics_port: int = Field(default=9005, alias="ANALYTICS_PORT")

    celery_broker_url: str = Field(default="redis://redis:6379/0", alias="CELERY_BROKER")
    celery_backend_url: str = Field(default="redis://redis:6379/1", alias="CELERY_BACKEND")
    celery_task_time_limit: int = Field(default=600, alias="CELERY_TASK_TIME_LIMIT")
    celery_task_soft_time_limit: int = Field(default=540, alias="CELERY_TASK_SOFT_TIME_LIMIT")

    smoke_test_audio: str = Field(default="/test-data/audio/sample_10s.wav")
    smoke_test_pdf: str = Field(default="/test-data/documents/sample_5pages.pdf")

    insight_queue_maxsize: int = Field(default=200, alias="INSIGHT_QUEUE_MAXSIZE")
    insight_worker_concurrency: int = Field(default=2, alias="INSIGHT_WORKER_CONCURRENCY")
    insight_use_celery: bool = Field(default=False, alias="INSIGHT_USE_CELERY")
    insight_celery_timeout_sec: float = Field(default=15.0, alias="INSIGHT_CELERY_TIMEOUT_SEC")
    insight_celery_queue: str = Field(default="insights", alias="INSIGHT_CELERY_QUEUE")

    @field_validator("api_tokens", mode="before")
    @classmethod
    def _parse_api_tokens(cls, value):
        if value in (None, "", [], ()):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
            return [token.strip() for token in stripped.split(",") if token.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
