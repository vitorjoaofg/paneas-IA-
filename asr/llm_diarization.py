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
LLM_MODEL_PATH = "/models/qwen2_5/int4-awq"
LLM_TIMEOUT = 30.0

# Lexical cues for deterministic relabeling
ATTENDANT_PATTERNS = [
    r"meu nome é",
    r"sou da",
    r"estamos com valor",
    r"vou começar",
    r"vou iniciar",
    r"preciso do seu",
    r"posso confirmar",
    r"posso conferir",
    r"temos uma oferta",
    r"consigo aqui para você",
    r"lembrando que",
    r"você pode mudar",
    r"compareça",
    r"documentação",
    r"verifique",
    r"aguarde",
    r"vamos fazer",
    r"nós da",
]

CLIENT_PATTERNS = [
    r"vamos\b",
    r"esse mesmo",
    r"esse mesmo\.",
    r"tá ok",
    r"tá bom",
    r"tá certo",
    r"tá, ok",
    r"ok\b",
    r"sim\b",
    r"isso\b",
    r"entendi",
    r"meu nome é",
    r"está no nome da minha mãe",
    r"queria repassar",
    r"posso passar pro meu nome",
]

SHORT_CLIENT_DURATION = 1.8  # seconds
SHORT_CLIENT_WORDS = 3
LONG_ATTENDANT_DURATION = 6.0

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


def _multi_pass_llm_correction(
    segments: List[Dict[str, Any]],
    window_size: int = 20,
    overlap: int = 10
) -> Dict[str, str]:
    """
    Multi-pass LLM analysis with sliding windows for improved accuracy.

    Args:
        segments: List of segments with text
        window_size: Number of segments per window
        overlap: Number of overlapping segments between windows

    Returns:
        Consensus speaker mapping
    """
    segments_with_text = [s for s in segments if s.get("text", "").strip()]

    if not segments_with_text:
        return {}

    # Collect votes from each window
    votes = defaultdict(lambda: {"Atendente": 0, "Cliente": 0})

    # Pass 1: Analyze first window (most important)
    window_1_end = min(window_size, len(segments_with_text))
    transcript_1 = "\n".join([
        f"{seg.get('speaker', 'SPEAKER_00')}: {seg.get('text', '').strip()}"
        for seg in segments_with_text[:window_1_end]
    ])

    mapping_1 = _query_llm_for_mapping(transcript_1, temperature=0.1)
    if mapping_1:
        for speaker, role in mapping_1.items():
            votes[speaker][role] += 3  # Higher weight for first window

    # Pass 2: Sliding windows for middle section (if conversation is long enough)
    if len(segments_with_text) > window_size:
        for start_idx in range(window_size // 2, len(segments_with_text) - window_size // 2, window_size - overlap):
            end_idx = min(start_idx + window_size, len(segments_with_text))

            transcript = "\n".join([
                f"{seg.get('speaker', 'SPEAKER_00')}: {seg.get('text', '').strip()}"
                for seg in segments_with_text[start_idx:end_idx]
            ])

            mapping = _query_llm_for_mapping(transcript, temperature=0.2)
            if mapping:
                for speaker, role in mapping.items():
                    votes[speaker][role] += 1

    # Pass 3: Analyze last window (to catch pattern changes)
    if len(segments_with_text) > window_size:
        window_3_start = max(0, len(segments_with_text) - window_size)
        transcript_3 = "\n".join([
            f"{seg.get('speaker', 'SPEAKER_00')}: {seg.get('text', '').strip()}"
            for seg in segments_with_text[window_3_start:]
        ])

        mapping_3 = _query_llm_for_mapping(transcript_3, temperature=0.1)
        if mapping_3:
            for speaker, role in mapping_3.items():
                votes[speaker][role] += 2  # Higher weight for last window

    # Consensus: pick role with most votes
    consensus = {}
    for speaker, role_votes in votes.items():
        consensus[speaker] = max(role_votes.items(), key=lambda x: x[1])[0]

    logger.info(f"Multi-pass consensus mapping: {consensus}")
    logger.debug(f"Vote distribution: {dict(votes)}")

    return consensus


def _query_llm_for_mapping(transcript: str, temperature: float = 0.2) -> Dict[str, str]:
    """
    Query LLM for speaker mapping.

    Args:
        transcript: Formatted transcript
        temperature: LLM temperature

    Returns:
        Speaker mapping dict or empty dict on failure
    """
    prompt = DIARIZATION_PROMPT_TEMPLATE.format(transcript=transcript)

    try:
        with httpx.Client(timeout=LLM_TIMEOUT) as client:
            response = client.post(
                LLM_ENDPOINT,
                json={
                    "model": LLM_MODEL_PATH,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 100,
                },
            )
            response.raise_for_status()

            llm_result = response.json()
            llm_content = llm_result["choices"][0]["message"]["content"].strip()

            # Parse JSON response
            if llm_content.startswith("```json"):
                llm_content = llm_content.replace("```json\n", "").replace("```", "")
            elif llm_content.startswith("```"):
                llm_content = llm_content.replace("```\n", "").replace("```", "")

            json_match = re.search(r'\{[^}]+\}', llm_content)
            if json_match:
                llm_content = json_match.group()

            mapping = json.loads(llm_content)

            # Validate mapping
            if "SPEAKER_00" in mapping and "SPEAKER_01" in mapping:
                return mapping

    except Exception as e:
        logger.debug(f"LLM query failed: {e}")

    return {}


def correct_speaker_labels_sync(
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Synchronous version for use in non-async context.
    Use multi-pass LLM analysis with RAG and temporal validation to correct speaker labels.

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

    # 🔹 STAGE 1: Multi-pass LLM mapping (3 passes with sliding windows)
    logger.info("Stage 1: Multi-pass LLM analysis")
    mapping = _multi_pass_llm_correction(segments, window_size=20, overlap=10)

    if not mapping or "SPEAKER_00" not in mapping or "SPEAKER_01" not in mapping:
        logger.warning(f"Invalid mapping from multi-pass LLM: {mapping}")
        return segments

    # Apply mapping to all segments
    corrected_segments = _apply_mapping(segments, mapping)

    # 🔹 STAGE 2: Apply lexical/rule-based corrections
    logger.info("Stage 2: Lexical rule-based refinement")
    corrected_segments = apply_role_rules(corrected_segments)

    # 🔹 STAGE 3: RAG-based semantic enhancement
    logger.info("Stage 3: RAG semantic enhancement")
    try:
        from asr.speaker_embeddings_rag import enhance_segments_with_rag
        corrected_segments = enhance_segments_with_rag(corrected_segments, confidence_threshold=0.65)
    except Exception as e:
        logger.warning(f"RAG enhancement failed: {e}")

    # 🔹 STAGE 4: Temporal graph validation
    logger.info("Stage 4: Temporal consistency validation")
    try:
        from asr.temporal_graph_validator import validate_and_fix_temporal_consistency, enforce_conversational_patterns
        corrected_segments, validation_report = validate_and_fix_temporal_consistency(
            corrected_segments,
            fix_anomalies=True
        )
        logger.info(f"Temporal validation: {validation_report.get('fixes_applied', 0)} fixes applied")

        # Enforce call center patterns
        corrected_segments = enforce_conversational_patterns(corrected_segments, expected_pattern="call_center")
    except Exception as e:
        logger.warning(f"Temporal validation failed: {e}")

    # 🔹 STAGE 5: Advanced temporal and semantic refinement
    logger.info("Stage 5: Final semantic refinement")

    # Enhanced patterns for semantic role detection
    attendant_markers = re.compile(
        r"^(coloca|deixa|faça|aguarde|compareça|envie|informe|precisa|precisar|tem que|"
        r"verifique|confirme|consigo|posso|nós|a gente|no sistema|vou|vamos|"
        r"lembre-se|lembrando|pra você|entendeu|tá certo|tudo bem|consegui|"
        r"estou|está|temos|tenho|oferece|ofereço|gostaria)",
        re.IGNORECASE
    )

    # Enhanced client confirmation patterns
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

        # Fix temporal ordering - ensure start time is after previous end
        if start < last_end:
            old_start = start
            start = round(last_end + 0.01, 2)
            logger.debug(f"Fixed temporal order: segment {i} start {old_start} -> {start}")
            corrections_made += 1

        # Update last_end
        last_end = max(last_end, end)

        # Apply semantic corrections based on linguistic patterns
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

        # Merge consecutive short segments from same speaker
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

    # Remove micro-gaps between segments (< 0.2s)
    for i in range(1, len(refined_segments)):
        gap = refined_segments[i]["start"] - refined_segments[i-1]["end"]
        if 0 < gap < 0.2:
            refined_segments[i]["start"] = round(refined_segments[i-1]["end"] + 0.01, 2)
            corrections_made += 1

    refined_segments = merge_adjacent_segments(refined_segments)
    refined_segments = reassign_short_segments(refined_segments)
    refined_segments = normalize_timestamps(refined_segments)

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

    # 🔹 STAGE 6: Calculate confidence scores and metrics
    logger.info("Stage 6: Calculating confidence scores")
    try:
        from asr.diarization_metrics import calculate_conversation_confidence, generate_quality_report
        refined_segments, metrics = calculate_conversation_confidence(refined_segments)

        # Log quality report at debug level
        if logger.isEnabledFor(logging.DEBUG):
            report = generate_quality_report(refined_segments, metrics)
            logger.debug(f"\n{report}")
        else:
            logger.info(f"Quality metrics: avg_confidence={metrics.get('avg_confidence', 0.0):.2%}, "
                       f"anomalies={len(metrics.get('anomalies', []))}")

    except Exception as e:
        logger.warning(f"Confidence scoring failed: {e}")

    return refined_segments


# For compatibility with async code
async def correct_speaker_labels(
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Async wrapper for correct_speaker_labels_sync.
    """
    return correct_speaker_labels_sync(segments)


def _apply_mapping(segments: List[Dict[str, Any]], mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    corrected = []
    for seg in segments:
        new_seg = seg.copy()
        old_speaker = seg.get("speaker", "SPEAKER_00")
        new_seg["speaker"] = mapping.get(old_speaker, old_speaker)
        corrected.append(new_seg)
    return corrected


def apply_role_rules(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Force deterministic labels based on lexical and temporal cues.
    """
    if not segments:
        return segments

    compiled_attendant = [re.compile(pat, re.IGNORECASE) for pat in ATTENDANT_PATTERNS]
    compiled_client = [re.compile(pat, re.IGNORECASE) for pat in CLIENT_PATTERNS]

    normalized = []
    for seg in segments:
        role = _normalize_role(seg.get("speaker"))
        text = seg.get("text", "") or ""
        duration = max(seg.get("end", 0.0) - seg.get("start", 0.0), 0.0)
        words = len(text.split())
        text_lower = text.lower()

        if any(pat.search(text_lower) for pat in compiled_attendant):
            role = "Atendente"
        elif any(pat.search(text_lower) for pat in compiled_client):
            role = "Cliente"
        elif duration >= LONG_ATTENDANT_DURATION:
            role = "Atendente"
        elif duration <= SHORT_CLIENT_DURATION or words <= SHORT_CLIENT_WORDS:
            role = "Cliente"

        normalized.append({**seg, "speaker": role})

    # Smooth inconsistent short segments by looking at neighbors
    smoothed: List[Dict[str, Any]] = []
    total = len(normalized)
    for idx, seg in enumerate(normalized):
        role = seg["speaker"]
        duration = max(seg.get("end", 0.0) - seg.get("start", 0.0), 0.0)
        if duration <= SHORT_CLIENT_DURATION + 0.5:
            prev_role = normalized[idx - 1]["speaker"] if idx > 0 else None
            next_role = normalized[idx + 1]["speaker"] if idx + 1 < total else None
            if prev_role and next_role and prev_role == next_role and prev_role != role:
                role = prev_role
            elif prev_role and duration <= SHORT_CLIENT_DURATION and prev_role != role:
                role = prev_role
        smoothed.append({**seg, "speaker": role})

    return smoothed


def merge_adjacent_segments(
    segments: List[Dict[str, Any]],
    max_gap: float = 0.4,
) -> List[Dict[str, Any]]:
    if not segments:
        return segments

    merged: List[Dict[str, Any]] = [segments[0].copy()]
    for seg in segments[1:]:
        prev = merged[-1]
        gap = seg.get("start", 0.0) - prev.get("end", 0.0)
        if seg.get("speaker") == prev.get("speaker") and gap <= max_gap:
            prev["end"] = max(prev["end"], seg.get("end", prev["end"]))
            prev["text"] = (prev.get("text", "").strip() + " " + seg.get("text", "").strip()).strip()
        else:
            merged.append(seg.copy())
    return merged


def reassign_short_segments(
    segments: List[Dict[str, Any]],
    min_duration: float = 0.9,
    max_words: int = 3,
) -> List[Dict[str, Any]]:
    if not segments:
        return segments

    remapped: List[Dict[str, Any]] = []
    total = len(segments)
    for idx, seg in enumerate(segments):
        duration = seg.get("end", 0.0) - seg.get("start", 0.0)
        word_count = len(seg.get("text", "").split())
        if duration >= min_duration or word_count > max_words:
            remapped.append(seg)
            continue

        prev_seg = remapped[-1] if remapped else None
        next_seg = segments[idx + 1] if idx + 1 < total else None

        candidate = None
        if prev_seg and next_seg:
            prev_duration = prev_seg.get("end", 0.0) - prev_seg.get("start", 0.0)
            next_duration = next_seg.get("end", 0.0) - next_seg.get("start", 0.0)
            candidate = prev_seg if prev_duration >= next_duration else next_seg
        else:
            candidate = prev_seg or next_seg

        new_seg = seg.copy()
        if candidate:
            new_seg["speaker"] = candidate.get("speaker", new_seg.get("speaker"))
        remapped.append(new_seg)

    return remapped


def normalize_timestamps(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    last_end = 0.0
    for seg in sorted(segments, key=lambda s: s.get("start", 0.0)):
        start = max(seg.get("start", 0.0), last_end)
        end = max(seg.get("end", start), start)
        normalized.append(
            {
                **seg,
                "start": round(start, 2),
                "end": round(end, 2),
            }
        )
        last_end = end
    return normalized


def _normalize_role(role: str | None) -> str:
    if not role:
        return "Atendente"
    role_lower = role.lower()
    if "atendente" in role_lower or "agent" in role_lower:
        return "Atendente"
    if "cliente" in role_lower or "customer" in role_lower:
        return "Cliente"
    return role
