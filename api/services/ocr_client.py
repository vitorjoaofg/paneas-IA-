import uuid
from typing import Any, Dict

from fastapi import UploadFile

from config import get_settings
from services.http_client import get_http_client, request_with_retry

_settings = get_settings()


async def run_ocr(file: UploadFile, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = await get_http_client()
    url = f"http://{_settings.ocr_host}:{_settings.ocr_port}/ocr"

    form_data = {k: (None, str(v)) for k, v in payload.items() if k != "file"}
    form_data["request_id"] = (None, str(uuid.uuid4()))

    files = {
        "file": (file.filename, await file.read(), file.content_type or "application/pdf"),
    }

    response = await request_with_retry(
        "POST",
        url,
        client=client,
        data=form_data,
        files=files,
        timeout=60.0,
    )
    return response.json()
