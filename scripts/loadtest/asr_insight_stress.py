#!/usr/bin/env python3
"""
Load test utility for /api/v1/asr/stream with live insight events.

Example:
    python scripts/loadtest/asr_insight_stress.py \
        --url ws://localhost:8000/api/v1/asr/stream \
        --token token_abc123 \
        --audio test-data/audio/sample4.wav \
        --sessions 100 \
        --ramp 60
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
import websockets
from websockets.exceptions import ConnectionClosed


def load_audio(path: Path, target_sr: int = 16000) -> Tuple[np.ndarray, int]:
    audio, sr = sf.read(path, always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != target_sr:
        duration = audio.shape[0] / sr
        target_len = int(duration * target_sr)
        audio = np.interp(
            np.linspace(0.0, 1.0, target_len),
            np.linspace(0.0, 1.0, audio.shape[0]),
            audio,
        )
        sr = target_sr
    audio = np.clip(audio, -1.0, 1.0)
    pcm16 = (audio * 32767.0).astype(np.int16)
    return pcm16, sr


def chunk_audio(audio: np.ndarray, sample_rate: int, chunk_ms: int) -> List[bytes]:
    samples_per_chunk = int(sample_rate * chunk_ms / 1000)
    chunks: List[bytes] = []
    for offset in range(0, len(audio), samples_per_chunk):
        chunk = audio[offset : offset + samples_per_chunk]
        if chunk.size == 0:
            continue
        chunks.append(chunk.tobytes())
    return chunks


@dataclass
class SessionResult:
    index: int
    session_id: Optional[str]
    started_at: float
    ready_at: Optional[float] = None
    ended_at: Optional[float] = None
    insight_at: Optional[float] = None
    error: Optional[str] = None
    events: List[Dict[str, str]] = field(default_factory=list)
    batches: int = 0

    @property
    def completion_latency(self) -> Optional[float]:
        if self.ready_at is None or self.ended_at is None:
            return None
        return self.ended_at - self.ready_at

    @property
    def insight_latency(self) -> Optional[float]:
        if self.ready_at is None or self.insight_at is None:
            return None
        return self.insight_at - self.ready_at


async def run_session(
    idx: int,
    ws_url: str,
    token: Optional[str],
    chunks: List[bytes],
    chunk_ms: int,
    language: str,
    model: str,
    compute_type: Optional[str],
    batch_window_sec: float,
    max_batch_window_sec: float,
    enable_diarization: bool,
    realtime: bool,
    expect_insight: bool,
    require_final: bool,
    insight_timeout: float,
    start_delay: float,
    post_audio_wait: float,
) -> SessionResult:
    await asyncio.sleep(start_delay)
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    connect_kwargs: Dict[str, Any] = {"ping_interval": None, "ping_timeout": None}
    if headers:
        connect_kwargs["extra_headers"] = headers
    result = SessionResult(index=idx, session_id=None, started_at=time.time())

    try:
        async with websockets.connect(ws_url, **connect_kwargs) as ws:
            if token and "token=" not in ws_url:
                # Maintain parity with existing client: allow either header or query param.
                pass

            start_payload: Dict[str, Any] = {
                "event": "start",
                "language": language,
                "sample_rate": 16000,
                "encoding": "pcm16",
                "model": model,
                "batch_window_sec": batch_window_sec,
                "max_batch_window_sec": max_batch_window_sec,
                "enable_diarization": enable_diarization,
            }
            if compute_type:
                start_payload["compute_type"] = compute_type

            await ws.send(json.dumps(start_payload))

            receiver = asyncio.create_task(_receiver(ws, result, expect_insight))
            sender = asyncio.create_task(
                _sender(ws, chunks, chunk_ms, realtime, post_audio_wait)
            )

            done, pending = await asyncio.wait(
                {receiver, sender},
                return_when=asyncio.ALL_COMPLETED,
                timeout=insight_timeout + 10.0,
            )
            for task in pending:
                task.cancel()
        if expect_insight and result.insight_at is None:
            result.error = result.error or "missing_insight"
    except ConnectionClosed as exc:
        if getattr(exc, "code", None) is not None:
            result.error = f"connection_closed:{exc.code}"
    except Exception as exc:  # noqa: BLE001
        result.error = f"error:{exc.__class__.__name__}:{exc}"
    finally:
        if require_final and result.ended_at is None and result.error is None:
            result.error = "missing_completion"
        success = (
            (result.ended_at is not None or not require_final)
            and (not expect_insight or result.insight_at is not None)
        )
        if success and result.error:
            result.error = None
    return result


async def _sender(
    ws: websockets.WebSocketClientProtocol,
    chunks: List[bytes],
    chunk_ms: int,
    realtime: bool,
    post_audio_wait: float,
) -> None:
    for raw in chunks:
        payload = base64.b64encode(raw).decode("ascii")
        try:
            await ws.send(json.dumps({"event": "audio", "chunk": payload}))
        except ConnectionClosed:
            return
        if realtime:
            await asyncio.sleep(chunk_ms / 1000.0)
    if post_audio_wait > 0:
        await asyncio.sleep(post_audio_wait)
    try:
        await ws.send(json.dumps({"event": "stop"}))
    except ConnectionClosed:
        pass


async def _receiver(ws: websockets.WebSocketClientProtocol, result: SessionResult, expect_insight: bool) -> None:
    try:
        async for message in ws:
            now = time.time()
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue

            event = payload.get("event")
            if event == "ready":
                result.session_id = payload.get("session_id")
                result.ready_at = now
            elif event == "batch_processed":
                result.batches += 1
            elif event in {"session_ended", "final_summary"}:
                result.ended_at = now
            elif expect_insight and event == "insight":
                result.insight_at = now
            elif event == "error":
                result.error = payload.get("message") or "error_event"
            result.events.append({"event": event or "unknown", "timestamp": str(now)})
    except ConnectionClosed as exc:
        if hasattr(exc, "code"):
            result.error = result.error or f"receiver_closed:{exc.code}"


def summarize(results: List[SessionResult]) -> Dict[str, float]:
    totals = len(results)
    successes = sum(1 for r in results if r.error is None)
    insights = sum(1 for r in results if r.insight_at is not None)
    completion_latencies = [
        r.completion_latency for r in results if r.completion_latency is not None
    ]
    insight_latencies = [r.insight_latency for r in results if r.insight_latency is not None]
    batches = [r.batches for r in results]

    def _stats(values: List[float]) -> Dict[str, float]:
        if not values:
            return {}
        return {
            "p50": statistics.median(values),
            "p95": percentile(values, 95),
            "max": max(values),
        }

    return {
        "sessions_total": totals,
        "sessions_success": successes,
        "sessions_failed": totals - successes,
        "insights_emitted": insights,
        "batches_total": sum(batches),
        **{f"completion_{k}": v for k, v in _stats(completion_latencies).items()},
        **{f"insight_{k}": v for k, v in _stats(insight_latencies).items()},
    }


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return math.nan
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * pct / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values_sorted[int(k)]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stress test for ASR streaming with insights.")
    parser.add_argument("--url", default="ws://localhost:8000/api/v1/asr/stream", help="ASR streaming WebSocket URL.")
    parser.add_argument("--token", help="Bearer token.")
    parser.add_argument("--audio", default="test-data/audio/sample_stream.wav", help="Audio file to stream.")
    parser.add_argument("--sessions", type=int, default=20, help="Number of simultaneous sessions.")
    parser.add_argument("--ramp", type=float, default=10.0, help="Seconds to ramp up all sessions.")
    parser.add_argument("--chunk-ms", type=int, default=600, help="Chunk size in milliseconds.")
    parser.add_argument("--language", default="pt", help="Language hint.")
    parser.add_argument("--model", default="whisper/medium", help="ASR model (e.g., whisper/medium, whisper/large-v3-turbo).")
    parser.add_argument("--compute-type", help="Optional compute type (e.g., fp16, int8_float16).")
    parser.add_argument("--batch-window-sec", type=float, default=5.0, help="Tempo alvo de processamento em segundos.")
    parser.add_argument("--max-batch-window-sec", type=float, default=10.0, help="Tempo máximo antes de forçar processamento.")
    parser.add_argument("--enable-diarization", action="store_true", help="Ativa diarização por lote.")
    parser.add_argument("--realtime", action="store_true", help="Stream audio in real time (default sends as fast as possible).")
    parser.add_argument("--expect-insight", action="store_true", help="Fail sessions missing insight events.")
    parser.add_argument("--require-final", action="store_true", help="Fail sessions missing session_ended event.")
    parser.add_argument("--insight-timeout", type=float, default=30.0, help="Seconds to wait before flagging missing insight.")
    parser.add_argument("--post-audio-wait", type=float, default=0.0, help="Seconds to keep the connection open after streaming audio before sending stop.")
    parser.add_argument("--summary-json", help="Optional path to dump summary JSON.")
    return parser.parse_args()


def print_summary(summary: Dict[str, float]) -> None:
    print("\n=== Load Test Summary ===")
    for key, value in sorted(summary.items()):
        if isinstance(value, float):
            print(f"{key}: {value:.3f}")
        else:
            print(f"{key}: {value}")


async def main_async(args: argparse.Namespace) -> None:
    audio_path = Path(args.audio)
    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    pcm, sr = load_audio(audio_path)
    if sr != 16000:
        raise SystemExit("Audio must be resampled to 16 kHz (internal helper should have done this).")
    chunks = chunk_audio(pcm, sr, args.chunk_ms)

    tasks = []
    for idx in range(args.sessions):
        start_delay = (args.ramp * idx / max(args.sessions - 1, 1)) if args.sessions > 1 else 0.0
        tasks.append(
            asyncio.create_task(
                run_session(
                    idx=idx,
                    ws_url=args.url,
                    token=args.token,
                    chunks=chunks,
                    chunk_ms=args.chunk_ms,
                    language=args.language,
                    model=args.model,
                    compute_type=args.compute_type,
                    batch_window_sec=args.batch_window_sec,
                    max_batch_window_sec=args.max_batch_window_sec,
                    enable_diarization=args.enable_diarization,
                    realtime=args.realtime,
                    expect_insight=args.expect_insight,
                    require_final=args.require_final,
                    insight_timeout=args.insight_timeout,
                    start_delay=start_delay,
                    post_audio_wait=args.post_audio_wait,
                )
            )
        )

    results = await asyncio.gather(*tasks)

    summary = summarize(results)
    print_summary(summary)

    failures = [r for r in results if r.error]
    if failures:
        print("\n=== Failures ===")
        for r in failures[:10]:
            print(f"[{r.index}] session={r.session_id} error={r.error}")
        if len(failures) > 10:
            print(f"... ({len(failures) - 10} more)")

    if args.summary_json:
        payload = {
            "summary": summary,
            "timestamp": time.time(),
        }
        Path(args.summary_json).write_text(json.dumps(payload, indent=2))


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
