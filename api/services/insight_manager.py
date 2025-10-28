import asyncio
import contextlib
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from difflib import SequenceMatcher

import structlog
from prometheus_client import Counter, Gauge, Histogram

from config import get_settings
from services.llm_client import MODEL_REGISTRY, chat_completion
from services.llm_router import LLMTarget

LOGGER = structlog.get_logger(__name__)
PROVIDER_PANEAS = "paneas"
PROVIDER_OPENAI = "openai"

INSIGHT_QUEUE_SIZE = Gauge(
    "insight_queue_size",
    "Number of insight jobs waiting to be processed",
)
INSIGHT_WORKERS_ACTIVE = Gauge(
    "insight_workers_active",
    "Number of insight jobs currently in progress",
)
INSIGHT_JOB_WAIT_SECONDS = Histogram(
    "insight_job_wait_seconds",
    "Time the insight job spent queued before execution",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40),
)
INSIGHT_JOB_DURATION_SECONDS = Histogram(
    "insight_job_duration_seconds",
    "Time taken to generate a single insight",
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32),
)
INSIGHT_JOB_FAILURES = Counter(
    "insight_job_failures_total",
    "Number of insight jobs that failed",
    ["reason"],
)


@dataclass
class InsightConfig:
    min_tokens: int = 30
    min_interval_sec: float = 20.0
    retain_tokens: int = 50
    max_context_tokens: int = 180
    context_segment_window: int = 6
    novelty_overlap_threshold: float = 0.85
    model: str = "qwen2.5-14b-instruct-awq"
    temperature: float = 0.3
    max_tokens: int = 180
    queue_maxsize: int = 200
    worker_concurrency: int = 2
    use_celery: bool = False
    celery_task_timeout_sec: float = 15.0
    celery_queue: str = "insights"
    provider: str = PROVIDER_PANEAS
    openai_model: Optional[str] = None


SendCallable = Callable[[Dict[str, Any]], Awaitable[None]]
LLMCallable = Callable[[Dict[str, Any], LLMTarget], Awaitable[Dict[str, Any]]]
EnqueueCallable = Callable[[str], Awaitable[None]]


@dataclass
class InsightJob:
    session_id: str
    enqueued_at: float


class InsightSession:
    def __init__(
        self,
        session_id: str,
        send_callback: SendCallable,
        config: InsightConfig,
        llm_callable: LLMCallable,
        enqueue_callback: EnqueueCallable,
    ) -> None:
        self.session_id = session_id
        self._send_callback = send_callback
        self._config = config
        self._llm_callable = llm_callable
        self._provider = (config.provider or PROVIDER_PANEAS).lower()
        self._openai_model = config.openai_model
        self._last_text: str = ""
        self._segments: List[str] = []
        self._last_insight_ts: float = 0.0
        self._last_insight_text: Optional[str] = None
        self._job_inflight: bool = False
        self._closed: bool = False
        self._lock = asyncio.Lock()
        self._enqueue_callback = enqueue_callback

    async def ingest(self, text: str) -> None:
        if not text:
            return
        delta = self._extract_delta(text)
        if not delta:
            return
        self._segments.append(delta)
        max_segments = max(self._config.context_segment_window * 3, self._config.context_segment_window)
        if len(self._segments) > max_segments:
            self._segments = self._segments[-max_segments:]
        LOGGER.info(
            "insight_ingest",
            session_id=self.session_id,
            tokens=self._token_count(),
            delta_words=len(delta.split()),
        )
        await self._maybe_schedule()

    def _extract_delta(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return ""
        if self._last_text and cleaned.startswith(self._last_text):
            delta = cleaned[len(self._last_text) :].strip()
        else:
            delta = cleaned
        self._last_text = cleaned
        return delta

    def _token_count(self) -> int:
        if not self._last_text:
            return 0
        return len(self._last_text.split())

    async def _maybe_schedule(self) -> None:
        if self._job_inflight or self._closed:
            return
        if self._token_count() < self._config.min_tokens:
            return
        now = time.time()
        if (now - self._last_insight_ts) < self._config.min_interval_sec:
            return
        async with self._lock:
            if self._job_inflight or self._closed:
                return
            LOGGER.info(
                "insight_schedule", session_id=self.session_id, tokens=self._token_count()
            )
            self._job_inflight = True
            await self._enqueue_callback(self.session_id)

    async def generate_insight(self) -> None:
        start_time = time.time()
        try:
            if self._closed:
                return
            context = self._build_context()
            if not context:
                return

            # Valida se o contexto tem conteúdo substancial
            if not self._has_substantial_content(context):
                LOGGER.info(
                    "insight_skipped_insufficient_content",
                    session_id=self.session_id,
                    tokens=self._token_count()
                )
                return
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Você é um assistente de call center que analisa chamadas e gera insights APENAS quando há informação concreta. "
                        "Identifique e extraia: problema específico do cliente, valores/códigos mencionados, "
                        "ações já tomadas (pagamentos, solicitações), status atual, próximo passo necessário. "
                        "Seja extremamente objetivo e use APENAS dados explícitos da conversa. "
                        "Priorize informações como: números de protocolo, valores monetários, datas, nomes de produtos/serviços."
                    ),
                },
            ]
            if self._last_insight_text:
                messages.append(
                    {
                        "role": "assistant",
                        "content": self._last_insight_text,
                    }
                )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Transcrição:\n{context}\n\n"
                        "Extraia informações concretas e forneça:\n"
                        "1) Situação: [Problema específico] + [Dados mencionados: valores, códigos, datas, produtos]\n"
                        "2) Próxima ação: [Passo específico que o atendente deve executar agora]\n\n"
                        "Exemplo: '1) Cliente reportou cobrança duplicada de R$ 150,00 na fatura 2024/10, "
                        "apresentou comprovante código 10203040. 2) Verificar código no sistema e estornar "
                        "valor duplicado.'\n\n"
                        "Seja direto, mencione números/códigos quando disponíveis, evite generalidades."
                    ),
                }
            )

            requested_model = self._config.model
            payload = {
                "model": requested_model,
                "messages": messages,
                "max_tokens": self._config.max_tokens,
                "temperature": self._config.temperature,
            }

            provider = self._provider
            if provider == PROVIDER_OPENAI:
                payload["provider"] = PROVIDER_OPENAI
                payload["model"] = self._openai_model or _settings.openai_insights_model
                target = LLMTarget.OPENAI
            else:
                payload["provider"] = provider or PROVIDER_PANEAS
                registry_entry = MODEL_REGISTRY.get(
                    requested_model,
                    MODEL_REGISTRY["qwen2.5-14b-instruct"],
                )
                target = registry_entry["target"]

            response = await self._call_llm(payload, target)
            if provider == PROVIDER_OPENAI:
                response["model"] = requested_model
            choices = response.get("choices") or []
            if not choices:
                LOGGER.warning("insight_llm_no_choices", session_id=self.session_id)
                return
            message = choices[0].get("message") or {}
            content = (message.get("content") or "").strip()
            if not content:
                LOGGER.warning("insight_llm_empty_content", session_id=self.session_id)
                return
            overlap = (
                self._similarity(content, self._last_insight_text)
                if self._last_insight_text
                else 0.0
            )
            if (
                self._last_insight_text
                and self._config.novelty_overlap_threshold < 1.0
                and overlap >= self._config.novelty_overlap_threshold
            ):
                LOGGER.info(
                    "insight_skipped_low_novelty",
                    session_id=self.session_id,
                    overlap=overlap,
                )
                self._last_insight_ts = time.time()
                self._trim_cache()
                return

            insight_payload = {
                "event": "insight",
                "type": "live_summary",
                "request_id": self.session_id,
                "text": content,
                "confidence": 0.7,
                "model": self._config.model,
                "provider": provider,
                "generated_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            }
            await self._send_callback(insight_payload)
            LOGGER.info("insight_emitted", session_id=self.session_id)
            self._last_insight_ts = time.time()
            self._last_insight_text = content
            self._trim_cache()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("insight_generation_failed", session_id=self.session_id, error=str(exc))
            INSIGHT_JOB_FAILURES.labels(reason=exc.__class__.__name__).inc()
        finally:
            INSIGHT_JOB_DURATION_SECONDS.observe(max(time.time() - start_time, 0.0))
            self._job_inflight = False
            await self._maybe_schedule()

    async def _call_llm(self, payload: Dict[str, Any], target: LLMTarget) -> Dict[str, Any]:
        if not self._config.use_celery:
            return await self._llm_callable(payload, target)
        return await self._call_llm_via_celery(payload, target)

    async def _call_llm_via_celery(self, payload: Dict[str, Any], target: LLMTarget) -> Dict[str, Any]:
        from celery.exceptions import TimeoutError as CeleryTimeoutError  # type: ignore
        from services.insight_tasks import generate_insight_task  # local import to avoid circular deps

        timeout = self._config.celery_task_timeout_sec
        payload_copy = dict(payload)

        def _run_task() -> Dict[str, Any]:
            result = generate_insight_task.apply_async(
                kwargs={"payload": payload_copy, "target": target.name},
                queue=self._config.celery_queue,
            )
            return result.get(timeout=timeout)

        try:
            return await asyncio.to_thread(_run_task)
        except CeleryTimeoutError as exc:  # pragma: no cover - requires celery runtime
            LOGGER.warning(
                "insight_celery_timeout",
                session_id=self.session_id,
                timeout_sec=timeout,
            )
            raise RuntimeError("Insight generation timed out") from exc

    def _build_context(self) -> str:
        if not self._last_text:
            return ""
        window_segments = self._segments[-self._config.context_segment_window :] if self._segments else []
        joined = " ".join(segment.strip() for segment in window_segments if segment)
        candidate = joined or self._last_text
        words = candidate.split()
        if len(words) > self._config.max_context_tokens:
            words = words[-self._config.max_context_tokens :]
        return " ".join(words)

    def _has_substantial_content(self, context: str) -> bool:
        """Verifica se o contexto tem informações substanciais para gerar insight útil."""
        if not context:
            return False

        # Palavras-chave que indicam conteúdo útil em call center
        keywords = [
            "problema", "ajuda", "cartão", "fatura", "débito", "pagamento", "valor",
            "código", "protocolo", "comprovante", "conta", "cliente", "número",
            "quero", "preciso", "gostaria", "não", "erro", "consulta",
            "reclamação", "reclamacao", "solicitação", "solicitacao",
            "quanto", "quando", "como", "porque", "por que"
        ]

        context_lower = context.lower()

        # Conta quantas palavras-chave aparecem
        keyword_count = sum(1 for kw in keywords if kw in context_lower)

        # Verifica se tem números (códigos, valores, protocolos)
        has_numbers = any(char.isdigit() for char in context)

        # Precisa ter pelo menos 2 palavras-chave OU pelo menos 1 palavra-chave + números
        return keyword_count >= 2 or (keyword_count >= 1 and has_numbers)

    def _trim_cache(self) -> None:
        words = self._last_text.split()
        if len(words) > self._config.retain_tokens:
            words = words[-self._config.retain_tokens :]
            self._last_text = " ".join(words)
        if self._last_text:
            self._segments = [self._last_text]
        else:
            self._segments.clear()

    async def close(self) -> None:
        self._closed = True
        self._segments.clear()
        self._last_text = ""
        self._job_inflight = False

    def has_pending_job(self) -> bool:
        return self._job_inflight


class InsightManager:
    def __init__(self, config: Optional[InsightConfig] = None, llm_callable: Optional[LLMCallable] = None) -> None:
        self._sessions: Dict[str, InsightSession] = {}
        self._config = config or InsightConfig()
        self._llm_callable = llm_callable or self._default_llm_call
        self._jobs: "asyncio.Queue[InsightJob | object]" = asyncio.Queue(maxsize=self._config.queue_maxsize)
        self._workers: List[asyncio.Task[None]] = []
        self._sentinel = object()
        self._started = False

    async def register_session(
        self,
        session_id: str,
        send_callback: SendCallable,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        openai_model: Optional[str] = None,
    ) -> None:
        await self.startup()
        await self.close_session(session_id)
        provider_value = (provider or self._config.provider or PROVIDER_PANEAS).lower()
        openai_value = openai_model or self._config.openai_model or _settings.openai_insights_model
        session_config = replace(
            self._config,
            model=model or self._config.model,
            provider=provider_value,
            openai_model=openai_value,
        )
        self._sessions[session_id] = InsightSession(
            session_id=session_id,
            send_callback=send_callback,
            config=session_config,
            llm_callable=self._llm_callable,
            enqueue_callback=self._enqueue_job,
        )

    async def handle_transcript(self, session_id: str, text: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        await session.ingest(text)

    async def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            await session.close()

    async def wait_for_pending(self, session_id: str, timeout: float = 5.0) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        start = time.time()
        while session.has_pending_job() and (time.time() - start) < timeout:
            await asyncio.sleep(0.05)

    async def startup(self) -> None:
        if self._started:
            return
        self._started = True
        for idx in range(self._config.worker_concurrency):
            task = asyncio.create_task(self._worker_loop(idx))
            self._workers.append(task)

    async def shutdown(self) -> None:
        if not self._started:
            return
        for _ in self._workers:
            await self._jobs.put(self._sentinel)
        for task in self._workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        self._started = False
        while not self._jobs.empty():
            try:
                self._jobs.get_nowait()
                self._jobs.task_done()
            except asyncio.QueueEmpty:
                break
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)
        INSIGHT_QUEUE_SIZE.set(0)
        INSIGHT_WORKERS_ACTIVE.set(0)

    async def _enqueue_job(self, session_id: str) -> None:
        job = InsightJob(session_id=session_id, enqueued_at=time.time())
        await self._jobs.put(job)
        INSIGHT_QUEUE_SIZE.set(self._jobs.qsize())

    async def _worker_loop(self, worker_idx: int) -> None:
        LOGGER.info("insight_worker_started", worker=worker_idx)
        try:
            while True:
                job = await self._jobs.get()
                INSIGHT_QUEUE_SIZE.set(self._jobs.qsize())
                if job is self._sentinel:
                    self._jobs.task_done()
                    break
                assert isinstance(job, InsightJob)
                session = self._sessions.get(job.session_id)
                if not session:
                    self._jobs.task_done()
                    INSIGHT_QUEUE_SIZE.set(self._jobs.qsize())
                    continue
                wait_time = max(time.time() - job.enqueued_at, 0.0)
                INSIGHT_JOB_WAIT_SECONDS.observe(wait_time)
                INSIGHT_WORKERS_ACTIVE.inc()
                try:
                    await session.generate_insight()
                finally:
                    INSIGHT_WORKERS_ACTIVE.dec()
                    self._jobs.task_done()
                    INSIGHT_QUEUE_SIZE.set(self._jobs.qsize())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("insight_worker_failed", worker=worker_idx, error=str(exc))
        finally:
            LOGGER.info("insight_worker_stopped", worker=worker_idx)

    async def _default_llm_call(self, payload: Dict[str, Any], target: LLMTarget) -> Dict[str, Any]:
        return await chat_completion(payload, target)

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()


_settings = get_settings()

insight_manager = InsightManager(
    config=InsightConfig(
        queue_maxsize=_settings.insight_queue_maxsize,
        worker_concurrency=_settings.insight_worker_concurrency,
        use_celery=_settings.insight_use_celery,
        celery_task_timeout_sec=_settings.insight_celery_timeout_sec,
        celery_queue=_settings.insight_celery_queue,
        min_tokens=_settings.insight_min_tokens,
        min_interval_sec=_settings.insight_min_interval_sec,
        retain_tokens=_settings.insight_retain_tokens,
        max_context_tokens=_settings.insight_max_context_tokens,
        context_segment_window=_settings.insight_context_segments,
        novelty_overlap_threshold=_settings.insight_novelty_threshold,
        model=_settings.insight_model_name,
        temperature=_settings.insight_temperature,
        max_tokens=_settings.insight_max_tokens,
        provider=PROVIDER_PANEAS,
        openai_model=_settings.openai_insights_model,
    )
)
