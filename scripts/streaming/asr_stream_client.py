#!/usr/bin/env python3
"""
Exemplo de cliente WebSocket para o endpoint /api/v1/asr/stream.

Uso:
    python scripts/streaming/asr_stream_client.py \
        --url ws://localhost:8000/api/v1/asr/stream \
        --token token_abc123 \
        --file test-data/audio/sample_10s.wav
"""

import argparse
import asyncio
import base64
import inspect
import json
from pathlib import Path
from typing import AsyncGenerator, Optional, Tuple

import numpy as np
import soundfile as sf
import websockets
from websockets.exceptions import ConnectionClosedOK


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


async def chunk_audio(
    audio: np.ndarray, sample_rate: int, chunk_ms: int
) -> AsyncGenerator[np.ndarray, None]:
    samples_per_chunk = int(sample_rate * chunk_ms / 1000)
    for offset in range(0, len(audio), samples_per_chunk):
        yield audio[offset : offset + samples_per_chunk]
        await asyncio.sleep(chunk_ms / 1000.0)


async def stream_audio(
    url: str,
    token: Optional[str],
    audio_path: Path,
    language: str,
    chunk_ms: int,
) -> None:
    pcm16, sample_rate = load_audio(audio_path)
    ws_url = url
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        if "token=" not in ws_url:
            ws_url = f"{ws_url}{'&' if '?' in ws_url else '?'}token={token}"

    connect_kwargs = {}
    if headers:
        param = "additional_headers" if "additional_headers" in inspect.signature(websockets.connect).parameters else "extra_headers"
        connect_kwargs[param] = headers

    async with websockets.connect(ws_url, **connect_kwargs) as ws:
        await ws.send(
            json.dumps(
                {
                    "event": "start",
                    "language": language,
                    "sample_rate": sample_rate,
                    "encoding": "pcm16",
                    "emit_interval_sec": chunk_ms / 1000.0,
                }
            )
        )

        async def reader() -> None:
            try:
                async for message in ws:
                    print("<<", message)
            except ConnectionClosedOK:
                pass

        reader_task = asyncio.create_task(reader())

        async for chunk in chunk_audio(pcm16, sample_rate, chunk_ms):
            if chunk.size == 0:
                continue
            payload = base64.b64encode(chunk.tobytes()).decode("ascii")
            await ws.send(json.dumps({"event": "audio", "chunk": payload}))

        await ws.send(json.dumps({"event": "stop"}))
        await reader_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente WebSocket de streaming ASR.")
    parser.add_argument("--url", default="ws://localhost:8000/api/v1/asr/stream", help="URL do websocket.")
    parser.add_argument("--token", help="Bearer token de autenticação.")
    parser.add_argument("--file", default="test-data/audio/sample_10s.wav", help="Arquivo de áudio de entrada.")
    parser.add_argument("--language", default="pt", help="Idioma esperado.")
    parser.add_argument("--chunk-ms", type=int, default=800, help="Tamanho do chunk em milissegundos.")
    args = parser.parse_args()

    audio_path = Path(args.file)
    if not audio_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {audio_path}")

    asyncio.run(stream_audio(args.url, args.token, audio_path, args.language, args.chunk_ms))


if __name__ == "__main__":
    main()
