import pytest

from routers.llm import (
    AUTO_SUMMARY_MIN_CHARS,
    _auto_shrink_messages,
    _estimate_tokens,
)
from schemas.llm import ChatMessage, ChatRequest


def _make_long_text(min_chars: int) -> str:
    token = "paragrafo "
    repeats = (min_chars // len(token)) + 5
    return token * repeats


@pytest.mark.asyncio
async def test_auto_shrink_invokes_summarizer_for_large_message():
    long_text = _make_long_text(AUTO_SUMMARY_MIN_CHARS + 1000)
    payload = ChatRequest(
        model="paneas-q32b",
        messages=[ChatMessage(role="user", content=long_text)],
        max_tokens=10,
        temperature=0.7,
    )

    calls = []

    async def fake_summarizer(text: str) -> str:
        calls.append(len(text))
        return "resumo sintetico"

    result_tokens = await _auto_shrink_messages(payload, context_limit=100, summarizer=fake_summarizer)

    assert calls, "Summarizer should have been invoked for oversized payload"
    assert payload.messages[0].content == "resumo sintetico"
    assert result_tokens + payload.max_tokens <= 100


@pytest.mark.asyncio
async def test_auto_shrink_skips_small_messages():
    text = _make_long_text(AUTO_SUMMARY_MIN_CHARS // 4)
    payload = ChatRequest(
        model="paneas-q32b",
        messages=[ChatMessage(role="user", content=text)],
        max_tokens=10,
    )

    calls = []

    async def fake_summarizer(_: str) -> str:
        calls.append(True)
        return "should not run"

    original_content = payload.messages[0].content
    result_tokens = await _auto_shrink_messages(payload, context_limit=20, summarizer=fake_summarizer)

    assert not calls, "Summarizer must not run for short content"
    assert payload.messages[0].content == original_content
    assert result_tokens == _estimate_tokens(original_content)
