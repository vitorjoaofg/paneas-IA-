import json
from functools import lru_cache
from typing import List

from pydantic import AliasChoices, AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="development", alias="ENV")
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
    llm_timeout: float = Field(default=30.0, alias="LLM_TIMEOUT")

    asr_host: str = Field(default="asr", alias="ASR_HOST")
    asr_port: int = Field(default=9000, alias="ASR_PORT")
    asr_default_model: str = Field(
        default="whisper/medium",
        validation_alias=AliasChoices("DEFAULT_MODEL_NAME", "ASR_DEFAULT_MODEL"),
    )
    asr_compute_type: str = Field(
        default="int8_float16",
        validation_alias=AliasChoices("DEFAULT_COMPUTE_TYPE", "ASR_COMPUTE_TYPE"),
    )
    asr_model_pool_specs: str = Field(
        default="",
        validation_alias=AliasChoices("MODEL_POOL_SPECS", "ASR_MODEL_POOL_SPECS"),
    )
    asr_batch_window_sec: float = Field(
        default=5.0,
        validation_alias=AliasChoices("ASR_BATCH_WINDOW_SEC", "BATCH_WINDOW_SEC"),
    )
    asr_max_batch_window_sec: float = Field(
        default=10.0,
        validation_alias=AliasChoices("ASR_MAX_BATCH_WINDOW_SEC", "MAX_BATCH_WINDOW_SEC"),
    )
    asr_max_buffer_sec: float = Field(
        default=60.0,
        validation_alias=AliasChoices("ASR_MAX_BUFFER_SEC", "MAX_BUFFER_SEC"),
    )

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

    scrapper_host: str = Field(default="scrapper", alias="SCRAPPER_HOST")
    scrapper_port: int = Field(default=8080, alias="SCRAPPER_PORT")

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
    insight_min_tokens: int = Field(default=30, alias="INSIGHT_MIN_TOKENS")
    insight_min_interval_sec: float = Field(default=20.0, alias="INSIGHT_MIN_INTERVAL_SEC")
    insight_retain_tokens: int = Field(default=50, alias="INSIGHT_RETAIN_TOKENS")
    insight_max_context_tokens: int = Field(default=180, alias="INSIGHT_MAX_CONTEXT_TOKENS")
    insight_context_segments: int = Field(default=6, alias="INSIGHT_CONTEXT_SEGMENTS")
    insight_novelty_threshold: float = Field(default=0.85, alias="INSIGHT_NOVELTY_THRESHOLD")
    insight_model_name: str = Field(default="paneas-q32b", alias="INSIGHT_MODEL")
    insight_temperature: float = Field(default=0.3, alias="INSIGHT_TEMPERATURE")
    insight_max_tokens: int = Field(default=180, alias="INSIGHT_MAX_TOKENS")
    insight_flush_timeout: float = Field(default=5.0, alias="INSIGHT_FLUSH_TIMEOUT")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_api_base: AnyHttpUrl = Field(default="https://api.openai.com/v1", alias="OPENAI_API_BASE")
    openai_timeout: float = Field(default=45.0, alias="OPENAI_TIMEOUT")
    openai_asr_model: str = Field(default="whisper-1", alias="OPENAI_ASR_MODEL")
    openai_insights_model: str = Field(default="gpt-4o-mini", alias="OPENAI_INSIGHTS_MODEL")

    # Google OAuth Configuration
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="https://jota.ngrok.app/auth/google/callback", alias="GOOGLE_REDIRECT_URI")

    # JWT Configuration
    jwt_secret_key: str = Field(default="your-secret-key-change-in-production", alias="JWT_SECRET_KEY")

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
