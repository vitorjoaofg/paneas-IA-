import asyncio
import contextlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

import structlog
from prometheus_client import Counter, Gauge, Histogram

from config import get_settings
from services.llm_client import MODEL_REGISTRY, chat_completion
from services.llm_router import LLMTarget

LOGGER = structlog.get_logger(__name__)

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
    model: str = "qwen2.5-14b-instruct-awq"
    temperature: float = 0.3
    max_tokens: int = 180
    queue_maxsize: int = 200
    worker_concurrency: int = 2
    use_celery: bool = False
    celery_task_timeout_sec: float = 15.0
    celery_queue: str = "insights"


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
        self._last_text: str = ""
        self._segments: List[str] = []
        self._last_insight_ts: float = 0.0
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
        if len(self._segments) > 50:
            self._segments = self._segments[-50:]
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
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Você está acompanhando uma chamada de call center em tempo real. "
                        "Crie insights práticos para o operador, mantendo confidencialidade e sem inventar dados."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Contexto da conversa até agora:\n"
                        f"{context}\n\n"
                        "Produza um insight curto (2 frases):\n"
                        "1) Resuma a situação atual do cliente.\n"
                        "2) Recomende a próxima ação do operador (ex.: sondar necessidade, confirmar dados, oferecer solução).\n"
                        "Use o mesmo idioma detectado no contexto. Se não houver informação suficiente, responda 'Sem dados suficientes até o momento.'."
                    ),
                },
            ]

            payload = {
                "model": self._config.model,
                "messages": messages,
                "max_tokens": self._config.max_tokens,
                "temperature": self._config.temperature,
            }
            target = MODEL_REGISTRY.get(self._config.model, MODEL_REGISTRY["qwen2.5-14b-instruct"])["target"]

            response = await self._call_llm(payload, target)
            choices = response.get("choices") or []
            if not choices:
                LOGGER.warning("insight_llm_no_choices", session_id=self.session_id)
                return
            message = choices[0].get("message") or {}
            content = (message.get("content") or "").strip()
            if not content:
                LOGGER.warning("insight_llm_empty_content", session_id=self.session_id)
                return

            insight_payload = {
                "event": "insight",
                "type": "live_summary",
                "request_id": self.session_id,
                "text": content,
                "confidence": 0.7,
                "model": self._config.model,
                "generated_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            }
            await self._send_callback(insight_payload)
            LOGGER.info("insight_emitted", session_id=self.session_id)
            self._last_insight_ts = time.time()
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
        words = self._last_text.split()
        if len(words) > self._config.max_context_tokens:
            words = words[-self._config.max_context_tokens :]
        return " ".join(words)

    def _trim_cache(self) -> None:
        words = self._last_text.split()
        if len(words) > self._config.retain_tokens:
            words = words[-self._config.retain_tokens :]
            self._last_text = " ".join(words)
            self._segments = [" ".join(words)]

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

    async def register_session(self, session_id: str, send_callback: SendCallable) -> None:
        await self.startup()
        await self.close_session(session_id)
        self._sessions[session_id] = InsightSession(
            session_id=session_id,
            send_callback=send_callback,
            config=self._config,
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
        model=_settings.insight_model_name,
        temperature=_settings.insight_temperature,
        max_tokens=_settings.insight_max_tokens,
    )
)
