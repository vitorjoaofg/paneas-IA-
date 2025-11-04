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


async def fix_speaker_labels_with_llm(
    segments: List[Dict[str, Any]],
    full_text: str,
) -> List[Dict[str, Any]]:
    """
    Usa LLM local para corrigir labels de speakers (Cliente vs Atendente).

    Analisa o contexto da conversa para identificar corretamente quem é cliente
    e quem é atendente, corrigindo erros comuns de diarização.

    Args:
        segments: Segmentos com speakers originais do PyAnnote
        full_text: Texto completo da transcrição para contexto

    Returns:
        Lista de segmentos com speakers corrigidos
    """
    if not segments:
        return segments

    LOGGER.info("fixing_speaker_labels", num_segments=len(segments))

    # Construir contexto dos segmentos para o LLM
    segments_info = []
    for i, seg in enumerate(segments[:30]):  # Limitar para 30 segmentos
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        start = seg.get("start", 0)

        if text:
            segments_info.append(f"[{i}] {start:.1f}s - {speaker}: {text}")

    segments_context = "\n".join(segments_info)

    prompt = f"""Você é um especialista em análise de conversas de call center.

CONTEXTO DA CONVERSA:
{full_text[:1500]}

SEGMENTOS COM TIMESTAMPS (alguns podem ter speakers incorretos):
{segments_context}

TAREFA:
Analise a conversa e identifique CORRETAMENTE quem é Cliente e quem é Atendente.

DICAS PARA IDENTIFICAÇÃO:
- **Atendente**: Apresenta-se primeiro, menciona nome da empresa, oferece produtos/serviços, fala de forma mais formal
- **Cliente**: Responde perguntas, fornece informações pessoais, toma decisões sobre ofertas

Para cada segmento [0] a [{len(segments_info)-1}], retorne "Cliente" ou "Atendente".

IMPORTANTE:
1. Baseie-se no CONTEÚDO de cada fala, não apenas na ordem
2. Se um segmento está marcado errado (ex: atendente fazendo oferta marcado como cliente), CORRIJA
3. Retorne um JSON array com {len(segments_info)} elementos

FORMATO DE SAÍDA:
Retorne APENAS um JSON array de strings, sem explicações:
["Atendente", "Cliente", "Atendente", ...]

JSON array:"""

    try:
        async with httpx.AsyncClient(timeout=LLM_LOCAL_TIMEOUT) as client:
            response = await client.post(
                LLM_LOCAL_ENDPOINT,
                json={
                    "model": "/models/qwen2_5/int4-awq-32b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()

            llm_result = response.json()
            llm_content = llm_result["choices"][0]["message"]["content"].strip()

            # Limpar resposta
            llm_content = _clean_json_response(llm_content)

            # Tentar parsear como JSON array
            try:
                # Primeiro tentar parsear como JSON array
                corrected_speakers = json.loads(llm_content)

                if not isinstance(corrected_speakers, list):
                    LOGGER.warning("llm_returned_non_array_for_speakers", type=type(corrected_speakers).__name__)
                    return segments

                # Aplicar correções aos segmentos
                updated_segments = []
                corrections_made = 0

                for i, segment in enumerate(segments):
                    new_segment = segment.copy()

                    if i < len(corrected_speakers):
                        original_speaker = segment.get("speaker", "")
                        corrected_speaker = corrected_speakers[i]

                        # Validar que é um speaker válido
                        if corrected_speaker in ["Cliente", "Atendente"]:
                            new_segment["speaker"] = corrected_speaker

                            if original_speaker != corrected_speaker:
                                corrections_made += 1
                                LOGGER.info(
                                    "speaker_corrected",
                                    segment_idx=i,
                                    original=original_speaker,
                                    corrected=corrected_speaker,
                                    text_preview=segment.get("text", "")[:50],
                                )

                    updated_segments.append(new_segment)

                LOGGER.info(
                    "speaker_labels_fixed",
                    total_segments=len(segments),
                    corrections_made=corrections_made,
                )

                return updated_segments

            except json.JSONDecodeError as e:
                LOGGER.error(
                    "failed_to_parse_speaker_json",
                    error=str(e),
                    content_preview=llm_content[:200],
                )
                return segments

    except Exception as e:
        LOGGER.error(
            "speaker_label_fixing_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return segments


async def postprocess_with_local_llm_only(
    full_text: str,
    segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Usa SOMENTE o LLM local para melhorar texto e segmentos em uma única chamada.
    Muito mais rápido que chamar OpenAI + LLM local separadamente.

    Args:
        full_text: Texto completo da transcrição
        segments: Segmentos originais com timestamps e speakers

    Returns:
        Dict com improved_text e improved_segments
    """
    LOGGER.info("postprocess_with_local_llm_only", text_length=len(full_text), num_segments=len(segments))

    # Construir contexto dos segmentos
    segments_info = []
    for i, seg in enumerate(segments[:50]):  # Limitar para performance
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        if text:
            segments_info.append(f"[{i}] {speaker}: {text}")

    segments_context = "\n".join(segments_info)

    prompt = f"""Você é um especialista em transcrições de call center e correção de textos.

TEXTO ORIGINAL DA TRANSCRIÇÃO:
{full_text[:3000]}

TAREFA:
Melhore esta transcrição corrigindo:
1. Erros de transcrição (ex: "Aquedaclar" → "Claro", "para pago" → "pré-pago")
2. Pontuação e formatação
3. Remova ruídos verbais excessivos

IMPORTANTE:
- Mantenha fidelidade ao conteúdo
- Corrija nomes de empresas
- Melhore clareza e organização

Retorne APENAS o texto melhorado, sem explicações.

TEXTO MELHORADO:"""

    try:
        async with httpx.AsyncClient(timeout=LLM_LOCAL_TIMEOUT) as client:
            response = await client.post(
                LLM_LOCAL_ENDPOINT,
                json={
                    "model": "/models/qwen2_5/int4-awq-32b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 3000,
                },
            )
            response.raise_for_status()

            llm_result = response.json()
            improved_text = llm_result["choices"][0]["message"]["content"].strip()

            LOGGER.info("local_llm_text_improved", original_length=len(full_text), improved_length=len(improved_text))

            # Agora mapear aos segmentos (reutilizando a outra função)
            improved_segments = await map_improved_text_to_segments_with_local_llm(
                improved_text=improved_text,
                original_segments=segments,
            )

            return {
                "improved_text": improved_text,
                "improved_segments": improved_segments,
                "processing_notes": "Processado com LLM local",
            }

    except Exception as e:
        LOGGER.error("local_llm_postprocess_failed", error=str(e))
        return {
            "improved_text": full_text,
            "improved_segments": segments,
            "processing_notes": None,
        }


def _map_text_heuristically(
    improved_text: str,
    original_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Mapeia texto melhorado de volta aos segmentos usando uma heurística rápida.
    Não usa LLM, apenas divide o texto proporcionalmente baseado nos tamanhos originais.

    Esta é uma alternativa ~20-25s mais rápida que usar LLM local.
    """
    # Separar por quebras de linha naturais no texto melhorado
    improved_lines = [line.strip() for line in improved_text.split('\n') if line.strip()]

    # Se temos aproximadamente o mesmo número de linhas que segmentos, mapeamento 1:1
    if abs(len(improved_lines) - len(original_segments)) <= 5:
        LOGGER.info("heuristic_11_mapping", improved_lines=len(improved_lines), segments=len(original_segments))
        updated_segments = []
        for i, segment in enumerate(original_segments):
            new_segment = segment.copy()
            if i < len(improved_lines):
                new_segment["text"] = improved_lines[i]
            updated_segments.append(new_segment)
        return updated_segments

    # Caso contrário, dividir o texto proporcionalmente ao comprimento dos segmentos originais
    LOGGER.info("heuristic_proportional_mapping", improved_lines=len(improved_lines), segments=len(original_segments))

    # Calcular comprimentos relativos
    total_original_length = sum(len(seg.get("text", "")) for seg in original_segments)
    if total_original_length == 0:
        return original_segments

    # Texto melhorado completo sem quebras
    improved_text_flat = " ".join(improved_lines)
    words = improved_text_flat.split()

    current_word_idx = 0
    updated_segments = []

    for i, segment in enumerate(original_segments):
        new_segment = segment.copy()
        original_text = segment.get("text", "")

        # Calcular quantas palavras este segmento deve ter proporcionalmente
        ratio = len(original_text) / total_original_length if total_original_length > 0 else 0
        num_words = max(1, int(len(words) * ratio))

        # Pegar palavras para este segmento
        segment_words = words[current_word_idx:current_word_idx + num_words]
        new_segment["text"] = " ".join(segment_words)

        current_word_idx += num_words
        updated_segments.append(new_segment)

    # Se sobraram palavras, adicionar ao último segmento
    if current_word_idx < len(words):
        remaining_words = words[current_word_idx:]
        if updated_segments:
            updated_segments[-1]["text"] += " " + " ".join(remaining_words)

    LOGGER.info("heuristic_mapping_complete", total_segments=len(updated_segments))
    return updated_segments


async def postprocess_with_local_llm_text_only(
    full_text: str,
    segments: List[Dict[str, Any]],
) -> str:
    """
    Usa SOMENTE o LLM local para melhorar o texto, retornando apenas o texto melhorado.
    Não mexe nos segmentos. Útil para o modo paneas-default onde queremos processar
    texto e speakers em paralelo separadamente.

    Args:
        full_text: Texto completo da transcrição
        segments: Segmentos originais (não são modificados)

    Returns:
        String com o texto melhorado
    """
    LOGGER.info("postprocess_with_local_llm_text_only", text_length=len(full_text))

    prompt = f"""Você é um especialista em transcrições de call center e correção de textos.

TEXTO ORIGINAL DA TRANSCRIÇÃO:
{full_text[:3000]}

TAREFA:
Melhore esta transcrição corrigindo:
1. Erros de transcrição (ex: "Aquedaclar" → "Claro", "para pago" → "pré-pago")
2. Pontuação e formatação
3. Remova ruídos verbais excessivos

IMPORTANTE:
- Mantenha fidelidade ao conteúdo
- Corrija nomes de empresas
- Melhore clareza e organização

Retorne APENAS o texto melhorado, sem explicações.

TEXTO MELHORADO:"""

    try:
        async with httpx.AsyncClient(timeout=LLM_LOCAL_TIMEOUT) as client:
            response = await client.post(
                LLM_LOCAL_ENDPOINT,
                json={
                    "model": "/models/qwen2_5/int4-awq-32b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 3000,
                },
            )
            response.raise_for_status()

            llm_result = response.json()
            improved_text = llm_result["choices"][0]["message"]["content"].strip()

            LOGGER.info("local_llm_text_only_improved", original_length=len(full_text), improved_length=len(improved_text))

            return improved_text

    except Exception as e:
        LOGGER.error("local_llm_text_only_failed", error=str(e))
        return full_text


async def fix_speaker_labels_with_openai(
    segments: List[Dict[str, Any]],
    full_text: str,
) -> List[Dict[str, Any]]:
    """
    Usa OpenAI para corrigir labels de speakers (Cliente vs Atendente).

    Analisa o contexto da conversa para identificar corretamente quem é cliente
    e quem é atendente, usando o poder do GPT-4o-mini para melhor compreensão.

    Args:
        segments: Segmentos com speakers originais do PyAnnote
        full_text: Texto completo da transcrição para contexto

    Returns:
        Lista de segmentos com speakers corrigidos
    """
    if not segments:
        return segments

    LOGGER.info("fixing_speaker_labels_with_openai", num_segments=len(segments))

    # Construir contexto dos segmentos para o LLM
    segments_info = []
    for i, seg in enumerate(segments[:30]):  # Limitar para 30 segmentos
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        start = seg.get("start", 0)

        if text:
            segments_info.append(f"[{i}] {start:.1f}s - {speaker}: {text}")

    segments_context = "\n".join(segments_info)

    prompt = f"""Você é um especialista em análise de conversas de call center.

CONTEXTO DA CONVERSA:
{full_text[:1500]}

SEGMENTOS COM TIMESTAMPS (alguns podem ter speakers incorretos):
{segments_context}

TAREFA:
Analise a conversa e identifique CORRETAMENTE quem é Cliente e quem é Atendente.

DICAS PARA IDENTIFICAÇÃO:
- **Atendente**: Apresenta-se primeiro, menciona nome da empresa, oferece produtos/serviços, fala de forma mais formal
- **Cliente**: Responde perguntas, fornece informações pessoais, toma decisões sobre ofertas

Para cada segmento [0] a [{len(segments_info)-1}], retorne "Cliente" ou "Atendente".

IMPORTANTE:
1. Baseie-se no CONTEÚDO de cada fala, não apenas na ordem
2. Se um segmento está marcado errado (ex: atendente fazendo oferta marcado como cliente), CORRIJA
3. Retorne um JSON array com {len(segments_info)} elementos

FORMATO DE SAÍDA:
Retorne APENAS um JSON array de strings, sem explicações:
["Atendente", "Cliente", "Atendente", ...]

JSON array:"""

    try:
        # Call OpenAI via our LLM client
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 500,
        }

        response = await chat_completion(payload, target=LLMTarget.OPENAI)
        llm_content = response["choices"][0]["message"]["content"].strip()

        # Limpar resposta
        llm_content = _clean_json_response(llm_content)

        # Tentar parsear como JSON array
        try:
            corrected_speakers = json.loads(llm_content)

            if not isinstance(corrected_speakers, list):
                LOGGER.warning("openai_returned_non_array_for_speakers", type=type(corrected_speakers).__name__)
                return segments

            # Aplicar correções aos segmentos
            updated_segments = []
            corrections_made = 0

            for i, segment in enumerate(segments):
                new_segment = segment.copy()

                if i < len(corrected_speakers):
                    original_speaker = segment.get("speaker", "")
                    corrected_speaker = corrected_speakers[i]

                    # Validar que é um speaker válido
                    if corrected_speaker in ["Cliente", "Atendente"]:
                        new_segment["speaker"] = corrected_speaker

                        if original_speaker != corrected_speaker:
                            corrections_made += 1
                            LOGGER.info(
                                "speaker_corrected_openai",
                                segment_idx=i,
                                original=original_speaker,
                                corrected=corrected_speaker,
                                text_preview=segment.get("text", "")[:50],
                            )

                updated_segments.append(new_segment)

            LOGGER.info(
                "speaker_labels_fixed_with_openai",
                total_segments=len(segments),
                corrections_made=corrections_made,
            )

            return updated_segments

        except json.JSONDecodeError as e:
            LOGGER.error(
                "failed_to_parse_openai_speaker_json",
                error=str(e),
                content_preview=llm_content[:200],
            )
            return segments

    except Exception as e:
        LOGGER.error(
            "openai_speaker_label_fixing_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return segments


async def map_improved_text_to_segments_with_local_llm(
    improved_text: str,
    original_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Usa o LLM local para mapear o texto melhorado de volta aos segmentos originais.
    Mantém timestamps e speakers, mas atualiza o texto de cada segmento.

    OPTIMIZATION: Para mais de 20 segmentos, usa heurística rápida ao invés de LLM.

    Args:
        improved_text: Texto completo já melhorado pela OpenAI
        original_segments: Segmentos originais com timestamps, speakers e texto original

    Returns:
        Lista de segmentos com textos atualizados
    """
    if not original_segments:
        return original_segments

    LOGGER.info("mapping_improved_text_to_segments", num_segments=len(original_segments))

    # OPTIMIZATION: Se há muitos segmentos, usar heurística rápida ao invés de LLM
    # Isso economiza ~20-25s de latência
    if len(original_segments) > 20:
        LOGGER.info("using_fast_heuristic_mapping", reason="too_many_segments")
        return _map_text_heuristically(improved_text, original_segments)

    # OPTIMIZATION: Limitar processamento para os primeiros 15 segmentos mais importantes
    # Economiza ~2-4s de latência LLM sem perda significativa de qualidade
    MAX_SEGMENTS_TO_PROCESS = 15

    # Construir contexto para o LLM
    segments_info = []
    for i, seg in enumerate(original_segments[:MAX_SEGMENTS_TO_PROCESS]):
        speaker = seg.get("speaker", "")
        original_text = seg.get("text", "").strip()
        start = seg.get("start", 0)
        end = seg.get("end", 0)

        if original_text:
            segments_info.append(f"[{i}] ({start:.1f}s-{end:.1f}s) {speaker}: {original_text}")

    segments_context = "\n".join(segments_info)

    # Limitar texto melhorado para 800 caracteres (economia de tokens)
    prompt = f"""Você é um assistente que mapeia texto melhorado de volta aos segmentos temporais originais.

TEXTO MELHORADO (corrigido e formatado):
{improved_text[:800]}

SEGMENTOS ORIGINAIS (com timestamps e speakers):
{segments_context}

TAREFA:
Para cada segmento original, encontre o texto correspondente no TEXTO MELHORADO e retorne um JSON array com os textos atualizados, mantendo a mesma ordem.

REGRAS IMPORTANTES:
1. Mantenha a mesma quantidade de segmentos ({len(segments_info)})
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
                    "temperature": 0.2,  # OPTIMIZATION: Reduzido para 0.2 (mais rápido e determinístico)
                    "max_tokens": 800,  # OPTIMIZATION: Reduzido de 1500 para 800
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
