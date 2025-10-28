import base64
import contextlib
import json
import uuid
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from prometheus_client import Counter, Gauge
from starlette.websockets import WebSocketState

from config import get_settings
from services.asr_batch import (
    BatchASRConfig,
    batch_session_manager,
    parse_batch_config,
    shutdown_batch_asr,
)
from services.insight_manager import insight_manager

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["asr-stream"])
settings = get_settings()

ACTIVE_SESSIONS = Gauge("asr_stream_active_sessions", "Active ASR streaming sessions")
STREAM_MESSAGES = Counter(
    "asr_stream_messages_total",
    "Total WebSocket messages observed",
    ["direction"],
)
STREAM_BYTES = Counter(
    "asr_stream_message_bytes_total",
    "Total WebSocket payload bytes observed",
    ["direction"],
)
STREAM_INSIGHTS = Counter(
    "asr_stream_insights_total",
    "Total streaming insights emitted",
)


def _extract_token(websocket: WebSocket) -> Optional[str]:
    auth_header = websocket.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return websocket.query_params.get("token")


def _decode_pcm16(chunk_b64: str) -> bytes:
    try:
        return base64.b64decode(chunk_b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid base64 audio chunk: {exc}") from exc


async def _send_event(ws: WebSocket, payload: Dict[str, Any]) -> None:
    if ws.client_state != WebSocketState.CONNECTED:
        return
    encoded = json.dumps(payload)
    await ws.send_text(encoded)
    STREAM_MESSAGES.labels(direction="to_client").inc()
    STREAM_BYTES.labels(direction="to_client").inc(len(encoded))


@router.websocket("/asr/stream")
async def websocket_asr_stream(websocket: WebSocket) -> None:
    tokens = settings.api_tokens
    token = _extract_token(websocket)
    if tokens and token not in tokens:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()
    ACTIVE_SESSIONS.inc()

    session_id = str(uuid.uuid4())
    session_config: Optional[BatchASRConfig] = None
    session_state = None
    session_registered = False
    insights_enabled = True
    summary: Dict[str, Any] = {}

    async def send_insight(payload: Dict[str, Any]) -> None:
        STREAM_INSIGHTS.inc()
        payload.setdefault("event", "insight")
        payload.setdefault("session_id", session_id)
        await _send_event(websocket, payload)

    async def ingest_text(text: str) -> None:
        if session_registered:
            await insight_manager.handle_transcript(session_id, text)

    try:
        await _send_event(
            websocket,
            {"event": "ready", "session_id": session_id, "mode": "batch"},
        )

        try:
            initial = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        except json.JSONDecodeError:
            await _send_event(
                websocket,
                {"event": "error", "message": "Invalid JSON payload on start."},
            )
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        if initial.get("event") != "start":
            await _send_event(
                websocket,
                {"event": "error", "message": "Expected start event."},
            )
            await websocket.close(code=4400, reason="Expected start event.")
            return

        encoding = initial.get("encoding", "pcm16").lower()
        if encoding != "pcm16":
            await _send_event(
                websocket,
                {"event": "error", "message": f"Unsupported encoding: {encoding}"},
            )
            await websocket.close(code=4400, reason="Unsupported encoding")
            return

        sample_rate = int(initial.get("sample_rate", 16000))
        session_config = parse_batch_config(initial)
        insights_enabled = bool(initial.get("enable_insights", True))
        insight_provider = str(initial.get("insight_provider", session_config.provider)).lower()
        insight_model = initial.get("insight_model")
        insight_openai_model = initial.get("insight_openai_model")
        LOGGER.info(
            "batch_stream_start",
            session_id=session_id,
            sample_rate=sample_rate,
            model=session_config.model,
            diarization=session_config.enable_diarization,
            batch_window=session_config.batch_window_sec,
            provider=session_config.provider,
            insight_provider=insight_provider,
        )

        async def send_event(payload: Dict[str, Any]) -> None:
            payload.setdefault("session_id", session_id)
            await _send_event(websocket, payload)

        await _send_event(
            websocket,
            {
                "event": "session_started",
                "session_id": session_id,
                "mode": "batch",
                "batch_window_sec": session_config.batch_window_sec,
                "insights_enabled": insights_enabled,
            },
        )

        if insights_enabled:
            await insight_manager.register_session(
                session_id,
                send_insight,
                model=insight_model,
                provider=insight_provider,
                openai_model=insight_openai_model,
            )
            session_registered = True

        session_state = await batch_session_manager.create(
            session_id=session_id,
            config=session_config,
            sample_rate=sample_rate,
            send_event=send_event,
            insight_callback=ingest_text,
        )

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                LOGGER.info("batch_stream_disconnect", session_id=session_id)
                break
            if message["type"] != "websocket.receive":
                continue

            data = message.get("text")
            if data is None:
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await _send_event(
                    websocket,
                    {"event": "error", "message": "Invalid JSON payload."},
                )
                continue

            event = payload.get("event")
            if event == "audio":
                chunk_b64 = payload.get("chunk")
                if not chunk_b64:
                    await _send_event(
                        websocket,
                        {"event": "error", "message": "Missing chunk data."},
                    )
                    continue
                try:
                    pcm_bytes = _decode_pcm16(chunk_b64)
                except ValueError as exc:
                    await _send_event(websocket, {"event": "error", "message": str(exc)})
                    continue
                STREAM_MESSAGES.labels(direction="from_client").inc()
                STREAM_BYTES.labels(direction="from_client").inc(len(pcm_bytes))
                if session_state:
                    await session_state.append_audio(pcm_bytes)
            elif event == "stop":
                if session_state:
                    summary = await session_state.close()
                if session_registered:
                    await insight_manager.wait_for_pending(
                        session_id, settings.insight_flush_timeout
                    )
                await _send_event(
                    websocket,
                    {
                        "event": "final_summary",
                        "session_id": session_id,
                        "stats": summary,
                    },
                )
                await _send_event(
                    websocket,
                    {"event": "session_ended", "session_id": session_id},
                )
                break
            else:
                await _send_event(
                    websocket,
                    {
                        "event": "error",
                        "message": f"Unknown event: {event}",
                    },
                )
    except WebSocketDisconnect:
        LOGGER.info("batch_stream_client_closed", session_id=session_id)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("batch_stream_failure", session_id=session_id, error=str(exc))
        if websocket.client_state != WebSocketState.DISCONNECTED:
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                await _send_event(
                    websocket, {"event": "error", "message": "Internal server error."}
                )
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        if session_registered:
            await insight_manager.close_session(session_id)
        if session_state:
            if not session_state.closed:
                await session_state.close()
            await batch_session_manager.pop(session_id)
        ACTIVE_SESSIONS.dec()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@router.on_event("shutdown")
async def _shutdown_batch_client() -> None:
    await shutdown_batch_asr()
