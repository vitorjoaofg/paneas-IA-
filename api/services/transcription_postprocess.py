"""
LLM-based transcription post-processing using OpenAI.
Improves transcription quality by correcting errors, formatting, and cleaning up the text.
"""

import json
import re
import structlog
from typing import Any, Dict, List, Optional

from services.llm_client import chat_completion
from services.llm_router import LLMTarget
import httpx

LOGGER = structlog.get_logger(__name__)

# Endpoint do LLM local
LLM_LOCAL_ENDPOINT = "http://llm-int4:8002/v1/chat/completions"
LLM_LOCAL_TIMEOUT = 30.0

# Prompt template for transcription improvement
TRANSCRIPTION_IMPROVEMENT_PROMPT = """Você é um especialista em transcrições de call center e correção de textos.

Sua tarefa é melhorar a transcrição fornecida, corrigindo erros de transcrição automática, pontuação, formatação e organizando o diálogo de forma clara e profissional.

**INSTRUÇÕES:**

1. **Corrija erros de transcrição**: Palavras mal transcritas, nomes de empresas (ex: "Aquedaclar" → "Claro"), termos técnicos, números, etc.

2. **Melhore a pontuação e formatação**: Adicione vírgulas, pontos, exclamações quando apropriado para tornar o texto mais natural e legível.

3. **Organize o diálogo**: Mantenha a estrutura de diálogo entre os speakers, com quebras de linha claras.

4. **Remova ruídos e hesitações excessivas**: Limpe ruídos verbais desnecessários (muitos "né", "então", repetições), mas mantenha naturalidade.

5. **Preserve o conteúdo**: NÃO invente informações. Mantenha fidelidade ao conteúdo original, apenas melhore a clareza.

6. **Mantenha identificação de speakers**: Se houver "Atendente:" ou "Cliente:" ou "SPEAKER_XX:", mantenha essas identificações.

7. **Adicione marcações de contexto**: Se identificar ruídos ou pausas significativas, pode adicionar marcações como "(ruído)", "(pausa)", etc.

**FORMATO DE SAÍDA:**

Retorne APENAS um JSON com a seguinte estrutura (sem explicações adicionais):

```json
{{
  "improved_text": "Texto completo melhorado aqui...",
  "notes": "Observações sobre correções principais realizadas (opcional)"
}}
```

**TRANSCRIÇÃO ORIGINAL:**

{transcript}

**JSON de saída:**"""

# Prompt template for improving individual segments
SEGMENT_IMPROVEMENT_PROMPT = """Você é um especialista em correção de transcrições.

Corrija e melhore o seguinte segmento de transcrição, mantendo fidelidade ao conteúdo mas melhorando clareza, pontuação e correção de erros.

REGRAS:
- Corrija palavras mal transcritas
- Melhore pontuação
- Mantenha o mesmo sentido
- Seja conciso
- Retorne APENAS o texto corrigido, sem explicações

Segmento original: {segment_text}

Texto corrigido:"""


async def postprocess_transcription(
    full_text: str,
    segments: Optional[List[Dict[str, Any]]] = None,
    model: str = "gpt-4o-mini",
    process_segments: bool = True,
) -> Dict[str, Any]:
    """
    Post-process transcription using OpenAI to improve quality.

    Args:
        full_text: The complete raw transcription text
        segments: Optional list of transcription segments with timing info
        model: OpenAI model to use (default: gpt-4o-mini)
        process_segments: Whether to also process individual segments

    Returns:
        Dict containing:
            - improved_text: The improved full transcription
            - improved_segments: List of segments with improved text (if segments provided)
            - processing_notes: Any notes from the LLM about corrections made
    """
    LOGGER.info(
        "postprocess_transcription_start",
        text_length=len(full_text),
        num_segments=len(segments) if segments else 0,
        model=model,
    )

    # Step 1: Improve full text
    improved_full_text, notes = await _improve_full_text(full_text, model)

    result = {
        "improved_text": improved_full_text,
        "processing_notes": notes,
    }

    # Step 2: Improve individual segments if requested
    if process_segments and segments:
        improved_segments = await _improve_segments(
            segments,
            original_full=full_text,
            improved_full=improved_full_text,
            model=model,
        )
        result["improved_segments"] = improved_segments
    else:
        result["improved_segments"] = segments

    LOGGER.info(
        "postprocess_transcription_complete",
        original_length=len(full_text),
        improved_length=len(improved_full_text),
    )

    return result


async def _improve_full_text(text: str, model: str) -> tuple[str, Optional[str]]:
    """
    Use OpenAI to improve the full transcription text.

    Returns:
        Tuple of (improved_text, notes)
    """
    prompt = TRANSCRIPTION_IMPROVEMENT_PROMPT.format(transcript=text)

    try:
        # Call OpenAI via our LLM client
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # Low temp for consistent corrections
            "max_tokens": 4000,  # Enough for long transcriptions
        }

        response = await chat_completion(payload, target=LLMTarget.OPENAI)

        llm_content = response["choices"][0]["message"]["content"].strip()

        LOGGER.info(
            "llm_raw_response",
            content_preview=llm_content[:300],
        )

        # Parse JSON response
        cleaned_content = _clean_json_response(llm_content)

        LOGGER.info(
            "llm_cleaned_response",
            content_preview=cleaned_content[:300],
        )

        try:
            result = json.loads(cleaned_content)

            LOGGER.info(
                "llm_parsed_json",
                keys=list(result.keys()) if isinstance(result, dict) else "not_a_dict",
            )

            improved_text = result.get("improved_text", text)
            notes = result.get("notes")

            LOGGER.info(
                "full_text_improvement_success",
                original_length=len(text),
                improved_length=len(improved_text),
                has_notes=bool(notes),
            )

            return improved_text, notes

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            LOGGER.warning(
                "json_parse_failed_using_raw_response",
                error=str(e),
                error_type=type(e).__name__,
                content_preview=cleaned_content[:200],
            )
            # If JSON parsing fails, use the raw response as improved text
            return llm_content, None

    except Exception as e:
        LOGGER.error(
            "full_text_improvement_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        # Return original text on error
        return text, None


async def _improve_segments(
    segments: List[Dict[str, Any]],
    original_full: str,
    improved_full: str,
    model: str,
) -> List[Dict[str, Any]]:
    """
    Improve individual segment texts.

    Strategy: Use a simpler prompt for each segment to maintain consistency
    with the overall improved transcription.
    """
    improved_segments = []

    # For efficiency, batch process segments or use the improved full text as reference
    # Here we'll use a smarter approach: map the improved full text back to segments
    # based on content matching and position

    LOGGER.info("improving_segments", count=len(segments))

    # Simple approach: Try to intelligently split the improved text back into segments
    # based on the original segment structure

    for i, segment in enumerate(segments):
        new_segment = segment.copy()
        original_text = segment.get("text", "").strip()

        if not original_text:
            improved_segments.append(new_segment)
            continue

        # Try to find corresponding text in improved version
        # This is a heuristic approach - we look for similar content
        improved_segment_text = await _improve_single_segment(original_text, model)

        new_segment["text"] = improved_segment_text
        improved_segments.append(new_segment)

    return improved_segments


async def _improve_single_segment(segment_text: str, model: str) -> str:
    """
    Improve a single segment text using OpenAI.
    """
    if len(segment_text) < 5:  # Skip very short segments
        return segment_text

    prompt = SEGMENT_IMPROVEMENT_PROMPT.format(segment_text=segment_text)

    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 200,
        }

        response = await chat_completion(payload, target=LLMTarget.OPENAI)
        improved = response["choices"][0]["message"]["content"].strip()

        # Remove quotes if the LLM wrapped the response
        improved = improved.strip('"\'')

        return improved if improved else segment_text

    except Exception as e:
        LOGGER.warning(
            "segment_improvement_failed",
            error=str(e),
            original=segment_text[:50],
        )
        return segment_text


def _clean_json_response(content: str) -> str:
    """
    Clean LLM response to extract JSON.
    """
    # Remove markdown code blocks
    if content.startswith("```json"):
        content = content.replace("```json\n", "").replace("```json", "")
    if content.startswith("```"):
        content = content.replace("```\n", "").replace("```", "")

    content = content.replace("```", "").strip()

    # Try to extract JSON object
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        return json_match.group()

    return content


async def map_improved_text_to_segments_with_local_llm(
    improved_text: str,
    original_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Usa o LLM local para mapear o texto melhorado de volta aos segmentos originais.
    Mantém timestamps e speakers, mas atualiza o texto de cada segmento.

    Args:
        improved_text: Texto completo já melhorado pela OpenAI
        original_segments: Segmentos originais com timestamps, speakers e texto original

    Returns:
        Lista de segmentos com textos atualizados
    """
    if not original_segments:
        return original_segments

    LOGGER.info("mapping_improved_text_to_segments", num_segments=len(original_segments))

    # Construir contexto para o LLM
    segments_info = []
    for i, seg in enumerate(original_segments):
        speaker = seg.get("speaker", "")
        original_text = seg.get("text", "").strip()
        start = seg.get("start", 0)
        end = seg.get("end", 0)

        if original_text:
            segments_info.append(f"[{i}] ({start:.1f}s-{end:.1f}s) {speaker}: {original_text}")

    segments_context = "\n".join(segments_info[:50])  # Limitar a 50 primeiros segmentos

    prompt = f"""Você é um assistente que mapeia texto melhorado de volta aos segmentos temporais originais.

TEXTO MELHORADO (corrigido e formatado):
{improved_text[:2000]}

SEGMENTOS ORIGINAIS (com timestamps e speakers):
{segments_context}

TAREFA:
Para cada segmento original, encontre o texto correspondente no TEXTO MELHORADO e retorne um JSON array com os textos atualizados, mantendo a mesma ordem.

REGRAS IMPORTANTES:
1. Mantenha a mesma quantidade de segmentos ({len(original_segments[:50])})
2. Preserve o sentido de cada segmento
3. Use o texto melhorado quando disponível
4. Se não encontrar correspondência, use o texto original
5. Seja conciso - cada segmento deve ser curto (1-2 frases no máximo)

FORMATO DE SAÍDA:
Retorne APENAS um JSON array de strings, sem explicações:
["texto do segmento 1", "texto do segmento 2", ...]

JSON array:"""

    try:
        # Chamar LLM local de forma síncrona
        async with httpx.AsyncClient(timeout=LLM_LOCAL_TIMEOUT) as client:
            response = await client.post(
                LLM_LOCAL_ENDPOINT,
                json={
                    "model": "/models/qwen2_5/int4-awq-32b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()

            llm_result = response.json()
            llm_content = llm_result["choices"][0]["message"]["content"].strip()

            # Limpar resposta
            llm_content = _clean_json_response(llm_content)

            # Parsear JSON array
            try:
                improved_texts = json.loads(llm_content)

                if not isinstance(improved_texts, list):
                    LOGGER.warning("llm_returned_non_array", type=type(improved_texts).__name__)
                    return original_segments

                # Atualizar segmentos com textos melhorados
                updated_segments = []
                for i, segment in enumerate(original_segments):
                    new_segment = segment.copy()

                    if i < len(improved_texts) and improved_texts[i]:
                        new_segment["text"] = improved_texts[i]

                    updated_segments.append(new_segment)

                LOGGER.info(
                    "segments_mapped_successfully",
                    original_count=len(original_segments),
                    updated_count=len(updated_segments),
                )

                return updated_segments

            except json.JSONDecodeError as e:
                LOGGER.error(
                    "failed_to_parse_llm_json",
                    error=str(e),
                    content_preview=llm_content[:200],
                )
                return original_segments

    except Exception as e:
        LOGGER.error(
            "segment_mapping_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return original_segments
