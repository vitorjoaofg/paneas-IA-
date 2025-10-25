import uuid
from typing import Any, Dict

from fastapi import UploadFile

from config import get_settings
from services.http_client import get_http_client

_settings = get_settings()


async def transcribe(
    file: UploadFile,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.asr_host}:{_settings.asr_port}/transcribe"

    form_data = {
        "request_id": (None, str(uuid.uuid4())),
        **{k: (None, str(v)) for k, v in options.items()},
    }

    files = {"file": (file.filename, await file.read(), file.content_type or "audio/wav")}
    response = await client.post(url, data=form_data, files=files)
    response.raise_for_status()
    return response.json()
