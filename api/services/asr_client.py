from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import UploadFile

from config import get_settings
from services.http_client import get_http_client, request_with_retry
from services.assemblyai_integration import transcribe_with_assemblyai

_settings = get_settings()
_PROVIDER_PANEAS = "paneas"
_PROVIDER_OPENAI = "openai"
_PROVIDER_ASSEMBLYAI = "assemblyai"


async def transcribe(
    file: UploadFile,
    options: Dict[str, Any],
    provider: str = _PROVIDER_PANEAS,
) -> Dict[str, Any]:
    audio_bytes = await file.read()
    filename = file.filename or "audio.wav"
    content_type = file.content_type or "audio/wav"
    return await transcribe_audio_bytes(
        audio_bytes=audio_bytes,
        filename=filename,
        content_type=content_type,
        options=options,
        provider=provider,
    )


async def transcribe_audio_bytes(
    audio_bytes: bytes,
    *,
    filename: str,
    content_type: str,
    options: Dict[str, Any],
    provider: str = _PROVIDER_PANEAS,
) -> Dict[str, Any]:
    normalized_provider = (provider or _PROVIDER_PANEAS).strip().lower()
    if normalized_provider == _PROVIDER_OPENAI:
        return await _transcribe_openai(audio_bytes, filename, content_type, options)
    elif normalized_provider == _PROVIDER_ASSEMBLYAI:
        return await _transcribe_assemblyai(audio_bytes, filename, content_type, options)
    return await _transcribe_internal(audio_bytes, filename, content_type, options)


async def _transcribe_internal(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.asr_host}:{_settings.asr_port}/transcribe"

    request_id = str(options.get("request_id") or uuid.uuid4())
    form_data = {
        **{k: (None, str(v)) for k, v in options.items()},
        "request_id": (None, request_id),
    }

    files = {"file": (filename, audio_bytes, content_type)}
    # Use longer timeout when diarization is enabled
    timeout = 180.0 if options.get("enable_diarization") else 30.0
    # Don't retry on timeout for diarization requests (already takes 60+ seconds)
    retry_attempts = 1 if options.get("enable_diarization") else 3
    response = await request_with_retry(
        "POST",
        url,
        client=client,
        data=form_data,
        files=files,
        timeout=timeout,
        retry_attempts=retry_attempts,
    )
    return response.json()


async def _transcribe_openai(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    if not _settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")

    requested_model = options.get("model")
    language = options.get("language")
    resolved_model = _resolve_openai_asr_model(requested_model)

    data = {
        "model": resolved_model,
        "response_format": "verbose_json",
    }
    if language and str(language).lower() not in {"auto", "automatic"}:
        data["language"] = language

    headers = {
        "Authorization": f"Bearer {_settings.openai_api_key}",
    }
    client = await get_http_client()
    timeout = httpx.Timeout(_settings.openai_timeout, connect=min(10.0, _settings.openai_timeout))
    base_url = str(_settings.openai_api_base).rstrip("/")
    response = await request_with_retry(
        "POST",
        f"{base_url}/audio/transcriptions",
        client=client,
        data=data,
        files={"file": (filename, audio_bytes, content_type or "audio/wav")},
        headers=headers,
        timeout=timeout,
    )

    return _normalize_openai_transcription(
        response.json(),
        requested_model=requested_model,
        language_hint=language,
    )


def _resolve_openai_asr_model(requested_model: Optional[str]) -> str:
    if not requested_model:
        return _settings.openai_asr_model
    lowered = requested_model.lower()
    if lowered.startswith("openai/"):
        return requested_model.split("/", 1)[1]
    if lowered in {"whisper/medium", "whisper-medium", "whisper_medium"}:
        return _settings.openai_asr_model
    return requested_model


def _normalize_openai_transcription(
    payload: Dict[str, Any],
    *,
    requested_model: Optional[str],
    language_hint: Optional[str],
) -> Dict[str, Any]:
    segments = payload.get("segments") or []
    normalized_segments = []
    for segment in segments:
        words = []
        for word in segment.get("words", []) or []:
            confidence = word.get("confidence")
            words.append(
                {
                    "start": float(word.get("start", 0.0)),
                    "end": float(word.get("end", 0.0)),
                    "word": word.get("word", ""),
                    "confidence": float(confidence) if confidence is not None else None,
                }
            )
        normalized_segments.append(
            {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": (segment.get("text") or "").strip(),
                "words": words or None,
            }
        )

    duration = payload.get("duration")
    if duration is None and segments:
        try:
            duration = float(segments[-1].get("end", 0.0))
        except (TypeError, ValueError):  # pragma: no cover - guard against malformed payloads
            duration = 0.0

    metadata_model = requested_model or _settings.openai_asr_model
    language = payload.get("language") or language_hint or "auto"

    return {
        "duration_seconds": float(duration or 0.0),
        "language": language,
        "text": (payload.get("text") or "").strip(),
        "segments": normalized_segments,
        "metadata": {
            "model": metadata_model,
            "compute_type": "openai-managed",
            "gpu_id": -1,
        },
    }


async def _transcribe_assemblyai(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    import tempfile
    import os

    # Save audio bytes to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_file.write(audio_bytes)
        temp_file_path = temp_file.name

    try:
        language = options.get("language", "pt")
        num_speakers = options.get("num_speakers", 2)

        # Call AssemblyAI integration
        result = await transcribe_with_assemblyai(
            audio_file_path=temp_file_path,
            language=language,
            num_speakers=num_speakers
        )

        return result
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_file_path)
        except:
            pass
