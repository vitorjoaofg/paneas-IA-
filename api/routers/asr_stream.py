import asyncio
import contextlib
import inspect
import json
import uuid
from typing import Optional

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from prometheus_client import Counter, Gauge
from starlette.websockets import WebSocketState
from websockets.exceptions import ConnectionClosed

from config import get_settings
from utils.pii_masking import PIIMasker

router = APIRouter(prefix="/api/v1", tags=["asr-stream"])
settings = get_settings()

ACTIVE_SESSIONS = Gauge("asr_stream_active_sessions", "Active ASR streaming sessions")
STREAM_MESSAGES = Counter(
    "asr_stream_messages_total",
    "Total WebSocket messages relayed",
    ["direction"],
)
STREAM_BYTES = Counter(
    "asr_stream_message_bytes_total",
    "Total WebSocket payload bytes relayed",
    ["direction"],
)

def _extract_token(websocket: WebSocket) -> Optional[str]:
    auth_header = websocket.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return websocket.query_params.get("token")


async def _relay_client_to_asr(client_ws: WebSocket, upstream_ws: websockets.WebSocketClientProtocol) -> None:
    try:
        while True:
            message = await client_ws.receive()
            if message["type"] == "websocket.receive":
                data = message.get("text")
                if data is not None:
                    await upstream_ws.send(data)
                    STREAM_MESSAGES.labels(direction="to_asr").inc()
                    STREAM_BYTES.labels(direction="to_asr").inc(len(data))
                else:
                    binary = message.get("bytes")
                    if binary is not None:
                        await upstream_ws.send(binary)
                        STREAM_MESSAGES.labels(direction="to_asr").inc()
                        STREAM_BYTES.labels(direction="to_asr").inc(len(binary))
            elif message["type"] == "websocket.disconnect":
                await upstream_ws.close()
                break
    except WebSocketDisconnect:
        await upstream_ws.close()


async def _relay_asr_to_client(client_ws: WebSocket, upstream_ws: websockets.WebSocketClientProtocol) -> None:
    try:
        async for message in upstream_ws:
            if isinstance(message, bytes):
                await client_ws.send_bytes(message)
                STREAM_MESSAGES.labels(direction="to_client").inc()
                STREAM_BYTES.labels(direction="to_client").inc(len(message))
            else:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    await client_ws.send_text(message)
                    STREAM_MESSAGES.labels(direction="to_client").inc()
                    STREAM_BYTES.labels(direction="to_client").inc(len(message))
                    continue

                if payload.get("event") in {"partial", "final"}:
                    payload["text"] = PIIMasker.mask_text(payload.get("text", ""))
                    for segment in payload.get("segments", []):
                        if "text" in segment:
                            segment["text"] = PIIMasker.mask_text(segment["text"])
                encoded = json.dumps(payload)
                await client_ws.send_text(encoded)
                STREAM_MESSAGES.labels(direction="to_client").inc()
                STREAM_BYTES.labels(direction="to_client").inc(len(encoded))
    except ConnectionClosed:
        if client_ws.client_state != WebSocketState.DISCONNECTED:
            await client_ws.close(code=status.WS_1011_INTERNAL_ERROR)


@router.websocket("/asr/stream")
async def websocket_asr_stream(websocket: WebSocket) -> None:
    tokens = settings.api_tokens
    token = _extract_token(websocket)
    if tokens and token not in tokens:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept()
    ACTIVE_SESSIONS.inc()

    upstream_uri = f"ws://{settings.asr_host}:{settings.asr_port}/stream"
    upstream_headers = {"X-Request-Relay": "api-gateway", "X-Relay-Session": str(uuid.uuid4())}
    try:
        connect_kwargs = {}
        param = "additional_headers" if "additional_headers" in inspect.signature(websockets.connect).parameters else "extra_headers"
        connect_kwargs[param] = upstream_headers
        async with websockets.connect(upstream_uri, **connect_kwargs) as upstream_ws:
            relay_to_upstream = asyncio.create_task(_relay_client_to_asr(websocket, upstream_ws))
            relay_to_client = asyncio.create_task(_relay_asr_to_client(websocket, upstream_ws))
            done, pending = await asyncio.wait(
                [relay_to_upstream, relay_to_client],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            for task in done:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
    except ConnectionClosed:
        pass
    except Exception as exc:  # noqa: BLE001
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.send_json({"event": "error", "message": str(exc)})
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        ACTIVE_SESSIONS.dec()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
