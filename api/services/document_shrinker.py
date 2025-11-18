from __future__ import annotations

from typing import List, Sequence

import structlog

from config import get_settings
from services.llm_client import chat_completion
from services.llm_router import LLMTarget

LOGGER = structlog.get_logger(__name__)
settings = get_settings()

SUMMARY_MODEL_NAME = settings.long_doc_model_name if hasattr(settings, "long_doc_model_name") else "paneas-q32b"
CHUNK_CHAR_LIMIT = max(getattr(settings, "long_doc_chunk_chars", 6000), 2000)
CHUNK_MAX_TOKENS = 320
FINAL_MAX_TOKENS = 256
MAX_SUMMARY_CHUNKS = 6

CHUNK_SYSTEM_PROMPT = (
    "Você resume trechos extensos mantendo fatos, datas, valores e pedidos principais. "
    "Não invente dados e escreva no máximo quatro frases curtas."
)

FINAL_SYSTEM_PROMPT = (
    "Você recebe resumos numerados de um documento longo. "
    "Produza um resumo único, direto e cronológico com foco em partes envolvidas, fatos centrais, valores e pedidos."
)


def chunk_text(text: str, max_chunk_chars: int) -> List[str]:
    """Split text into blocks while trying to respect paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n")]
    paragraphs = [p for p in paragraphs if p]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for paragraph in paragraphs:
        length = len(paragraph)
        if length >= max_chunk_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            for start in range(0, length, max_chunk_chars):
                chunks.append(paragraph[start : start + max_chunk_chars])
            continue

        if current_len + length + (2 if current else 0) > max_chunk_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = length
        else:
            current.append(paragraph)
            current_len += length if current_len == 0 else length + 2

    if current:
        chunks.append("\n\n".join(current))
    if not chunks:
        return [text.strip()]
    return chunks


def _select_chunk_indexes(total_chunks: int, max_chunks: int) -> Sequence[int]:
    """Spread selected indexes across document to keep contexto global."""
    if total_chunks <= max_chunks:
        return list(range(total_chunks))

    if max_chunks < 2:
        return [0]

    positions = []
    for i in range(max_chunks):
        fraction = i / (max_chunks - 1)
        idx = int(round(fraction * (total_chunks - 1)))
        positions.append(idx)

    deduped: List[int] = []
    for idx in positions:
        if idx not in deduped:
            deduped.append(idx)
    candidate = 0
    while len(deduped) < max_chunks:
        if candidate not in deduped:
            deduped.append(candidate)
        candidate += 1
        if candidate >= total_chunks:
            candidate = 0

    return sorted(deduped)


async def _run_completion(messages: List[dict], max_tokens: int, reason: str) -> str:
    payload = {
        "model": SUMMARY_MODEL_NAME,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    response = await chat_completion(
        payload,
        LLMTarget.INT4,
        router_metadata={"router_decision": LLMTarget.INT4.value, "router_reason": reason},
    )
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("Resumo não retornou choices")
    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("Resumo retornou conteúdo vazio")
    return content


async def summarize_long_document(content: str) -> str:
    """
    Condense um documento extenso em poucas linhas para caber no limite do modelo.

    Faz duas etapas: sumariza trechos selecionados e gera um resumo consolidado.
    """
    text = content.strip()
    if not text:
        return content

    chunks = chunk_text(text, CHUNK_CHAR_LIMIT)
    if len(chunks) == 1:
        return content

    selected_indexes = _select_chunk_indexes(len(chunks), MAX_SUMMARY_CHUNKS)
    partial_summaries: List[str] = []
    for relative_order, chunk_index in enumerate(selected_indexes, start=1):
        chunk = chunks[chunk_index]
        LOGGER.info(
            "long_doc_chunk_summary",
            chunk_index=chunk_index,
            total_chunks=len(chunks),
            chunk_chars=len(chunk),
        )
        user_content = (
            f"Trecho {chunk_index + 1} de {len(chunks)}. Extraia fatos principais, "
            f"valores, datas e pedidos.\n\n{chunk}"
        )
        summary = await _run_completion(
            [
                {"role": "system", "content": CHUNK_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            CHUNK_MAX_TOKENS,
            reason="long_doc_chunk",
        )
        partial_summaries.append(f"Trecho {chunk_index + 1}: {summary}")

    if len(chunks) > MAX_SUMMARY_CHUNKS:
        skipped = len(chunks) - len(selected_indexes)
        partial_summaries.append(
            f"[Aviso] Outros {skipped} trechos foram condensados automaticamente para caber no limite."
        )

    summaries_text = "\n\n".join(partial_summaries)
    final_content = await _run_completion(
        [
            {"role": "system", "content": FINAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Com base nos resumos numerados abaixo, produza um único parágrafo claro "
                    "com contexto, fatos centrais e pedidos.\n\n"
                    f"{summaries_text}"
                ),
            },
        ],
        FINAL_MAX_TOKENS,
        reason="long_doc_final",
    )

    sanitized = final_content.strip()
    if not sanitized:
        return content

    metadata = (
        f"\n\n[Documento original com {len(content)} caracteres resumido automaticamente para {len(sanitized)} "
        "caracteres para caber no contexto.]"
    )
    return sanitized + metadata
