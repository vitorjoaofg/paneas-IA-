import asyncio

import pytest

from services.insight_manager import InsightConfig, InsightManager


@pytest.mark.asyncio
async def test_insight_manager_triggers_after_threshold():
    emitted = []

    async def fake_send(payload):
        emitted.append(payload)

    async def fake_llm(payload, target):  # noqa: ARG001
        return {
            "choices": [
                {"message": {"content": "Resumo breve. Sugerir próxima ação."}}
            ]
        }

    config = InsightConfig(min_tokens=6, min_interval_sec=0.0, retain_tokens=3)
    manager = InsightManager(config=config, llm_callable=fake_llm)

    await manager.register_session("session-1", fake_send)

    await manager.handle_transcript("session-1", "Cliente relatou problema na fatura.")
    await manager.handle_transcript(
        "session-1",
        "Cliente relatou problema na fatura. Solicita negociação imediata.",
    )

    # Allow async task to complete.
    await asyncio.sleep(0.05)

    assert emitted, "Insight should have been emitted when threshold is surpassed"
    insight = emitted[0]
    assert insight["event"] == "insight"
    assert "Resumo breve" in insight["text"]
    await manager.close_session("session-1")
