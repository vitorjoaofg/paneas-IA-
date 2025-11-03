"""
LLM-based speaker diarization correction utility.
Uses contextual clues to identify Agent vs Customer and correct PyAnnote labels.
"""

import logging
import json
import re
from typing import List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

# LLM configuration - using the int4 service on port 8002
LLM_ENDPOINT = "http://llm-int4:8002/v1/chat/completions"
LLM_TIMEOUT = 30.0

# Based on the excellent prompt from asr_batch.py
DIARIZATION_PROMPT_TEMPLATE = """Você é um especialista em análise de transcrições de call center.
Analise a transcrição e identifique qual speaker (SPEAKER_00 ou SPEAKER_01) é o "Atendente" e qual é o "Cliente".

CARACTERÍSTICAS PARA IDENTIFICAÇÃO:

ATENDENTE (Operador/Vendedor):
- Se apresenta com nome e empresa (ex: "Meu nome é Carlos, sou da Claro")
- Faz perguntas sobre dados pessoais (CPF, nome completo, endereço)
- Oferece produtos, planos ou serviços
- Explica condições, valores e benefícios
- Usa linguagem mais formal e técnica
- Faz perguntas procedimentais ("Posso confirmar seus dados?")
- Pede confirmações ("Correto?", "Ok?", "Tudo bem?")
- Agradece e se despede formalmente

CLIENTE:
- Responde às perguntas do atendente
- Geralmente fala menos em cada turno
- Fornece dados pessoais quando solicitado
- Faz perguntas sobre o serviço
- Aceita ou recusa ofertas ("Sim", "Não", "Vamos", "Ok")
- Expressa dúvidas ou problemas pessoais
- Fala de forma mais informal

REGRAS IMPORTANTES:
1. O primeiro "Oi" ou "Alô" geralmente é do CLIENTE atendendo a ligação
2. Quem se apresenta com nome e empresa é SEMPRE o Atendente
3. Respostas curtas como "Sim", "Ok", "Tá" são geralmente do Cliente
4. Analise TODO o contexto antes de decidir - seja consistente

FORMATO DE SAÍDA:
Retorne APENAS um JSON com o mapeamento, sem explicações:
{{"SPEAKER_00": "Atendente"|"Cliente", "SPEAKER_01": "Atendente"|"Cliente"}}

TRANSCRIÇÃO PARA ANÁLISE:
{transcript}
"""


def correct_speaker_labels_sync(
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Synchronous version for use in non-async context.
    Use LLM to identify which PyAnnote speaker is Agent vs Customer,
    then relabel all segments accordingly.

    Args:
        segments: List of segments with 'text' and 'speaker' (SPEAKER_00/SPEAKER_01)

    Returns:
        List of segments with corrected speaker labels (Atendente/Cliente)
    """
    if not segments:
        return segments

    # Check if we have meaningful text to analyze
    segments_with_text = [s for s in segments if s.get("text", "").strip()]
    if not segments_with_text:
        logger.warning("No segments with text found for LLM correction")
        return segments

    # Build context for LLM: show first 20 segments to identify pattern
    transcript_lines = []
    for seg in segments_with_text[:20]:  # Use first 20 segments for speed
        speaker = seg.get("speaker", "SPEAKER_00")
        text = seg.get("text", "").strip()
        if text:
            transcript_lines.append(f"{speaker}: {text}")

    if not transcript_lines:
        logger.warning("No valid transcript lines for LLM analysis")
        return segments

    context = "\n".join(transcript_lines)
    prompt = DIARIZATION_PROMPT_TEMPLATE.format(transcript=context)

    # Call LLM synchronously
    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as client:
            response = client.post(
                LLM_ENDPOINT,
                json={
                    "model": "/models/qwen2_5/int4-awq-32b",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,  # Low temperature for consistency
                    "max_tokens": 100,    # Just need the JSON mapping
                },
            )
            response.raise_for_status()

            llm_result = response.json()
            llm_content = llm_result["choices"][0]["message"]["content"].strip()

            # Parse JSON response
            # Handle different possible response formats
            if llm_content.startswith("```json"):
                llm_content = llm_content.replace("```json\n", "").replace("```", "")
            elif llm_content.startswith("```"):
                llm_content = llm_content.replace("```\n", "").replace("```", "")

            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[^}]+\}', llm_content)
            if json_match:
                llm_content = json_match.group()

            mapping = json.loads(llm_content)
            logger.info(f"LLM speaker mapping: {mapping}")

            # Validate mapping
            if "SPEAKER_00" not in mapping or "SPEAKER_01" not in mapping:
                logger.warning(f"Invalid mapping from LLM: {mapping}")
                return segments

            # Apply mapping to all segments
            corrected_segments = []
            for seg in segments:
                new_seg = seg.copy()
                old_speaker = seg.get("speaker", "SPEAKER_00")
                new_speaker = mapping.get(old_speaker, old_speaker)
                new_seg["speaker"] = new_speaker
                corrected_segments.append(new_seg)

            # Apply advanced temporal and semantic refinement
            logger.info("Applying advanced temporal and semantic refinement")

            # 🔹 Enhanced patterns for semantic role detection
            attendant_markers = re.compile(
                r"^(coloca|deixa|faça|aguarde|compareça|envie|informe|precisa|precisar|tem que|"
                r"verifique|confirme|consigo|posso|nós|a gente|no sistema|vou|vamos|"
                r"lembre-se|lembrando|pra você|entendeu|tá certo|tudo bem|consegui|"
                r"estou|está|temos|tenho|oferece|ofereço|gostaria)",
                re.IGNORECASE
            )

            # 🔹 Enhanced client confirmation patterns
            client_markers = re.compile(
                r"^(sim|isso|ok|tá|tudo bem|entendi|aham|beleza|ah tá|show|claro|ah sim|"
                r"tá ok|tá bom|certo|perfeito|obrigado|obrigada|uhm|ah|oi|vamos|pode ser|"
                r"sem problemas?)\b",
                re.IGNORECASE
            )

            refined_segments = []
            last_end = 0.0
            last_speaker = None
            corrections_made = 0

            for i, seg in enumerate(corrected_segments):
                start = seg.get("start", 0.0)
                end = seg.get("end", 0.0)
                text = seg.get("text", "").strip()
                speaker = seg.get("speaker", "Unknown")

                if not text:  # Skip empty segments
                    continue

                # 🔸 Fix temporal ordering - ensure start time is after previous end
                if start < last_end:
                    old_start = start
                    start = round(last_end + 0.01, 2)
                    logger.debug(f"Fixed temporal order: segment {i} start {old_start} -> {start}")
                    corrections_made += 1

                # Update last_end
                last_end = max(last_end, end)

                # 🔸 Apply semantic corrections based on linguistic patterns
                text_lower = text.lower()
                words = text.split()

                # PRIORITY 1: Very short responses (1-2 words) are typically Cliente
                if len(words) <= 2 and client_markers.search(text_lower):
                    if speaker != "Cliente":
                        logger.debug(f"Semantic fix: short client response '{text}' -> Cliente")
                        speaker = "Cliente"
                        corrections_made += 1

                # PRIORITY 2: Longer phrases with attendant markers
                elif attendant_markers.search(text_lower) and len(words) > 2:
                    if speaker != "Atendente":
                        logger.debug(f"Semantic fix: attendant pattern '{text[:30]}...' -> Atendente")
                        speaker = "Atendente"
                        corrections_made += 1

                # PRIORITY 3: Medium-length client confirmations (3-5 words)
                elif len(words) <= 5 and client_markers.search(text_lower):
                    if speaker != "Cliente":
                        logger.debug(f"Semantic fix: client response '{text}' -> Cliente")
                        speaker = "Cliente"
                        corrections_made += 1

                # 🔸 Merge consecutive short segments from same speaker
                if (refined_segments and
                    speaker == refined_segments[-1]["speaker"] and
                    len(words) < 5 and
                    start - refined_segments[-1]["end"] < 1.0):  # Within 1 second

                    # Merge with previous segment
                    refined_segments[-1]["text"] += " " + text
                    refined_segments[-1]["end"] = end
                    logger.debug(f"Merged segment {i} with previous (same speaker, short text)")
                else:
                    # Add as new segment
                    refined_segments.append({
                        "start": start,
                        "end": end,
                        "text": text,
                        "speaker": speaker
                    })

                last_speaker = speaker

            # 🔸 Remove micro-gaps between segments (< 0.2s)
            for i in range(1, len(refined_segments)):
                gap = refined_segments[i]["start"] - refined_segments[i-1]["end"]
                if 0 < gap < 0.2:
                    refined_segments[i]["start"] = round(refined_segments[i-1]["end"] + 0.01, 2)
                    corrections_made += 1

            logger.info(f"Refinement complete: {corrections_made} corrections made, "
                       f"{len(corrected_segments)} -> {len(refined_segments)} segments")

            # Log final statistics
            speaker_counts = {}
            total_duration = {}
            for seg in refined_segments:
                speaker = seg.get("speaker", "Unknown")
                duration = seg["end"] - seg["start"]
                speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
                total_duration[speaker] = total_duration.get(speaker, 0) + duration

            logger.info(f"Final speaker distribution: {speaker_counts}")
            logger.info(f"Final duration by speaker: {' | '.join(f'{k}: {v:.1f}s' for k, v in total_duration.items())}")

            return refined_segments

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code} - {e.response.text[:200]}")
        return segments
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"LLM response was: {llm_content[:200] if 'llm_content' in locals() else 'N/A'}")
        return segments
    except Exception as e:
        logger.error(f"LLM diarization correction failed: {e}", exc_info=True)
        return segments


# For compatibility with async code
async def correct_speaker_labels(
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Async wrapper for correct_speaker_labels_sync.
    """
    return correct_speaker_labels_sync(segments)