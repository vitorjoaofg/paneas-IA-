import asyncio
import contextlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

import structlog

from services.llm_client import MODEL_REGISTRY, chat_completion
from services.llm_router import LLMTarget

LOGGER = structlog.get_logger(__name__)


@dataclass
class InsightConfig:
    min_tokens: int = 30
    min_interval_sec: float = 20.0
    retain_tokens: int = 50
    max_context_tokens: int = 180
    model: str = "qwen2.5-14b-instruct-awq"
    temperature: float = 0.3
    max_tokens: int = 180


SendCallable = Callable[[Dict[str, Any]], Awaitable[None]]
LLMCallable = Callable[[Dict[str, Any], LLMTarget], Awaitable[Dict[str, Any]]]


class InsightSession:
    def __init__(
        self,
        session_id: str,
        send_callback: SendCallable,
        config: InsightConfig,
        llm_callable: LLMCallable,
    ) -> None:
        self.session_id = session_id
        self._send_callback = send_callback
        self._config = config
        self._llm_callable = llm_callable
        self._last_text: str = ""
        self._segments: List[str] = []
        self._last_insight_ts: float = 0.0
        self._pending_task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

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
        if self._pending_task and not self._pending_task.done():
            return
        if self._token_count() < self._config.min_tokens:
            return
        now = time.time()
        if (now - self._last_insight_ts) < self._config.min_interval_sec:
            return
        async with self._lock:
            if self._pending_task and not self._pending_task.done():
                return
            LOGGER.info(
                "insight_schedule", session_id=self.session_id, tokens=self._token_count()
            )
            self._pending_task = asyncio.create_task(self._generate_insight())

    async def _generate_insight(self) -> None:
        try:
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

            response = await self._llm_callable(payload, target)
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
        finally:
            self._pending_task = None

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
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pending_task
        self._segments.clear()
        self._last_text = ""


class InsightManager:
    def __init__(self, config: Optional[InsightConfig] = None, llm_callable: Optional[LLMCallable] = None) -> None:
        self._sessions: Dict[str, InsightSession] = {}
        self._config = config or InsightConfig()
        self._llm_callable = llm_callable or self._default_llm_call

    async def register_session(self, session_id: str, send_callback: SendCallable) -> None:
        await self.close_session(session_id)
        self._sessions[session_id] = InsightSession(
            session_id=session_id,
            send_callback=send_callback,
            config=self._config,
            llm_callable=self._llm_callable,
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

    async def _default_llm_call(self, payload: Dict[str, Any], target: LLMTarget) -> Dict[str, Any]:
        return await chat_completion(payload, target)


insight_manager = InsightManager()
