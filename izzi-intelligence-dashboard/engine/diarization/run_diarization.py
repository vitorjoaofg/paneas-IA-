#!/usr/bin/env python3
"""
Classifica heurísticamente cada segmento das transcrições como IVR, cliente ou atendente.

Uso:
    python engine/diarization/run_diarization.py --call-id 0105-...
    python engine/diarization/run_diarization.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = ROOT_DIR
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

sys.path.append(str(ROOT_DIR))
from llm_enrichment import call_openai, DEFAULT_MODEL as LLM_MODEL  # noqa: E402

DIARIZATION_LLM_MODEL = os.environ.get("DIARIZATION_LLM_MODEL", LLM_MODEL or "gpt-4o")

try:  # Optional audio-based diarization dependencies
    import numpy as np
    import torch
    import torchaudio
    from speechbrain.pretrained import EncoderClassifier
    from sklearn.cluster import AgglomerativeClustering

    AUDIO_DIARIZATION_AVAILABLE = True
except Exception:  # pragma: no cover - falls back to text-only path
    AUDIO_DIARIZATION_AVAILABLE = False
    EncoderClassifier = None  # type: ignore

TARGET_SAMPLE_RATE = 16_000
MIN_SEGMENT_SECONDS = 0.35

IVR_PATTERNS = [
    "pulse 1",
    "pulse 2",
    "por favor",
    "asesor te está",
    "asesor te esta",
    "espera un momento",
    "no cuelgue",
    "no se retire",
    "navega con izzi",
    "promoción exclusiva",
    "bienvenido",
    "gracias por llamar a",
    "marca 1",
    "marca uno",
    "te interesa",
    "nuestros asesores",
    "gracias por tu espera",
    "mensaje después del tono",
    "mensaje despues del tono",
]

AGENT_PATTERNS = [
    "no se preocupe",
    "permítame",
    "permitame",
    "lo pondremos",
    "lo canalizo",
    "la canalizo",
    "lo transfiero",
    "con gusto",
    "le comento",
    "le informo",
    "le indico",
    "estoy verificando",
    "estamos verificando",
    "muchísimas gracias",
    "muchisimas gracias",
    "gracias por comunicarse",
    "me puede apoyar",
    "me ayudas con",
    "le apoyo",
    "le puedo ayudar",
    "puede confirmarme",
    "me confirma",
    "permanezca en la línea",
    "permanezca en la linea",
    "quedo a sus órdenes",
    "quedo a sus ordenes",
    "cualquier cosa",
    "será un placer",
    "sera un placer",
    "contratación",
    "contratacion",
    "le atiende",
    "mi nombre es",
    "queda pendiente",
    "comentarios para que",
    "le registramos",
    "le marcamos",
    "gracias por su tiempo",
    "con gusto le apoyo",
]

AGENT_STRONG_PATTERNS = [
    "lo pondremos en los comentarios",
    "lo registramos en comentarios",
    "gracias por llamar",
    "contratación de izzi",
    "contratacion de izzi",
    "contratación de vix",
    "contratacion de vix",
    "habla tu asesor",
    "servicio a clientes izzi",
]

CUSTOMER_PATTERNS = [
    "yo",
    "me llamaron",
    "mi problema",
    "necesito",
    "quisiera",
    "no quiero",
    "creo que se equivocaron",
    "tengo un problema",
    "no estoy interesado",
    "no me interesa",
    "mi número",
    "mi numero",
    "mi casa",
    "mi mamá",
    "mi mama",
    "con quien hablo",
    "hola?",
    "buen día",
    "buen dia",
]

CUSTOMER_STRONG_PATTERNS = [
    "creo que se equivocaron",
    "creo que se equivocaron de llamada",
    "se equivocaron de llamada",
    "es de mi casa",
    "es mi casa",
    "esta es la casa",
    "no soy cliente",
    "no quiero",
    "no me interesa",
    "no estoy interesado",
    "por favor no llamen",
    "llamada equivocada",
    "quien habla",
    "hola?",
    "hola?",
    "hola, quién habla",
    "hola quien habla",
    "disculpe",
    "perdón",
    "perdon",
    "perdona",
    "no, gracias",
    "hasta luego",
]

FAREWELL_PATTERNS_AGENT = [
    "hasta luego",
    "que tenga",
    "muchísimas gracias",
    "muchisimas gracias",
    "bye",
    "gracias por contactar",
    "gracias por comunicarse",
]

NOISE_PATTERNS = [
    "subtítulos realizados por la comunidad de amara.org",
    "subtitulos realizados por la comunidad de amara.org",
]

VALID_ROLES = {"agent", "customer", "ivr"}


_ENCODER: object | None = None
_RESAMPLER: object | None = None


def _load_encoder() -> object | None:
    if not AUDIO_DIARIZATION_AVAILABLE:
        return None
    global _ENCODER
    if _ENCODER is None:
        try:
            _ENCODER = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": "cpu"},
            )
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] Falha ao carregar modelo de embeddings: {exc}", file=sys.stderr)
            return None
    return _ENCODER


def _get_resampler(sample_rate: int) -> object | None:
    if not AUDIO_DIARIZATION_AVAILABLE or sample_rate == TARGET_SAMPLE_RATE:
        return None
    global _RESAMPLER
    if _RESAMPLER is None or getattr(_RESAMPLER, "orig_freq", TARGET_SAMPLE_RATE) != sample_rate:
        try:
            _RESAMPLER = torchaudio.transforms.Resample(sample_rate, TARGET_SAMPLE_RATE)
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] Falha ao criar resampler: {exc}", file=sys.stderr)
            return None
    return _RESAMPLER


def _locate_audio_path(call_id: str, transcript: Dict[str, object]) -> Path | None:
    candidates: List[Path] = []
    raw_path = transcript.get("file_path") or transcript.get("audio_path")
    if isinstance(raw_path, str) and raw_path.strip():
        path_candidate = Path(raw_path.strip())
        if path_candidate.is_file():
            candidates.append(path_candidate)
        else:
            candidates.append((ROOT_DIR / path_candidate).resolve())
            candidates.append((ROOT_DIR.parent / path_candidate).resolve())
    file_name = transcript.get("file_name")
    if isinstance(file_name, str) and file_name.strip():
        candidates.append((ROOT_DIR / file_name.strip()).resolve())
        candidates.append((ROOT_DIR.parent / file_name.strip()).resolve())
    base_name = f"{call_id}.WAV"
    candidates.append(ROOT_DIR.parent / "public" / "audio" / base_name)
    candidates.append(ROOT_DIR / base_name)
    lower_alt = base_name.lower()
    if lower_alt != base_name:
        candidates.append(ROOT_DIR.parent / "public" / "audio" / lower_alt)
        candidates.append(ROOT_DIR / lower_alt)
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return None


def _compute_segment_embeddings(
    audio_path: Path,
    segments: List[Dict[str, object]],
) -> Tuple[List[int], object, List[float]]:
    encoder = _load_encoder()
    if encoder is None:
        return [], np.empty((0,)), []
    try:
        waveform, sample_rate = torchaudio.load(str(audio_path))
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] Falha ao carregar áudio {audio_path}: {exc}", file=sys.stderr)
        return [], np.empty((0,)), []
    if waveform.size(0) > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    resampler = _get_resampler(sample_rate)
    if resampler is not None:
        waveform = resampler(waveform)
        sample_rate = TARGET_SAMPLE_RATE
    indices: List[int] = []
    embeddings: List[np.ndarray] = []
    durations: List[float] = []
    total_samples = waveform.size(-1)
    for idx, segment in enumerate(segments):
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", start) or start)
        duration = max(0.0, end - start)
        if duration < MIN_SEGMENT_SECONDS:
            continue
        start_sample = max(0, int(start * sample_rate))
        end_sample = min(total_samples, int(end * sample_rate))
        if end_sample - start_sample <= int(MIN_SEGMENT_SECONDS * sample_rate):
            continue
        chunk = waveform[:, start_sample:end_sample]
        if chunk.numel() == 0:
            continue
        if chunk.abs().max() > 0:
            chunk = chunk / chunk.abs().max()
        chunk = chunk.squeeze(0).unsqueeze(0)
        with torch.no_grad():
            try:
                embedding = encoder.encode_batch(chunk)
            except Exception as exc:  # pragma: no cover
                print(f"[WARN] Falha ao gerar embedding (segmento {idx}): {exc}", file=sys.stderr)
                continue
        embeddings.append(embedding.squeeze(0).cpu().numpy())
        indices.append(idx)
        durations.append(duration)
    if not embeddings:
        return [], np.empty((0,)), []
    matrix = np.vstack(embeddings)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    return indices, matrix, durations


def _score_texts(texts: List[str], patterns: Iterable[str]) -> float:
    score = 0.0
    for text in texts:
        lowered = text.lower()
        for pattern in patterns:
            if pattern in lowered:
                score += 1.0
    return score


def _assign_clusters_to_roles(
    segments: List[Dict[str, object]],
    indices: List[int],
    labels: Iterable[int],
) -> Dict[int, str]:
    cluster_map: Dict[int, Dict[str, object]] = {}
    for seg_index, label in zip(indices, labels):
        info = cluster_map.setdefault(int(label), {"indices": [], "texts": [], "duration": 0.0})
        segment = segments[seg_index]
        info["indices"].append(seg_index)
        info["texts"].append(normalize_text(segment.get("text")))
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", start) or start)
        info["duration"] += max(0.0, end - start)

    cluster_roles: Dict[int, str] = {}
    role_scores: Dict[int, Dict[str, float]] = {}
    for label, info in cluster_map.items():
        texts = [text for text in info["texts"] if text]
        combined = " ".join(texts).lower()
        agent_score = _score_texts(texts, AGENT_PATTERNS) * 2 + _score_texts(texts, AGENT_STRONG_PATTERNS) * 3
        customer_score = _score_texts(texts, CUSTOMER_PATTERNS) * 2 + _score_texts(texts, CUSTOMER_STRONG_PATTERNS) * 3
        ivr_score = _score_texts(texts, IVR_PATTERNS) * 3
        first_person = sum(combined.count(token) for token in [" yo ", " me ", " mi ", " mí ", "soy", "estoy", "llamada", "problema"])
        customer_score += first_person * 1.2
        agent_score += combined.count("gracias") * 0.5
        ivr_score += combined.count("pulse") * 0.8
        role_scores[label] = {
            "agent": agent_score + info["duration"] * 0.2,
            "customer": customer_score + info["duration"] * 0.2,
            "ivr": ivr_score + (len(info["texts"]) - len(texts)) * 0.5,
        }

    if not role_scores:
        return {}

    # IVR choice prioritises keyword match and low lexical diversity
    ivr_label = max(role_scores.items(), key=lambda item: item[1]["ivr"])[0]
    if role_scores[ivr_label]["ivr"] > max(role_scores[ivr_label]["agent"], role_scores[ivr_label]["customer"]) * 1.2:
        cluster_roles[ivr_label] = "ivr"

    remaining_labels = [label for label in role_scores.keys() if label not in cluster_roles]
    if remaining_labels:
        agent_label = max(remaining_labels, key=lambda label: role_scores[label]["agent"])
        cluster_roles[agent_label] = "agent"
        remaining_labels = [label for label in remaining_labels if label != agent_label]
    if remaining_labels:
        customer_label = max(remaining_labels, key=lambda label: role_scores[label]["customer"])
        cluster_roles[customer_label] = "customer"

    # Fallbacks when keywords were weak
    if "customer" not in cluster_roles.values() and remaining_labels:
        fallback_label = remaining_labels[0]
        cluster_roles[fallback_label] = "customer"
    if "agent" not in cluster_roles.values() and role_scores:
        fallback_label = max(role_scores.items(), key=lambda item: item[1]["agent"])[0]
        cluster_roles[fallback_label] = "agent"
    if "ivr" not in cluster_roles.values() and role_scores:
        fallback_label = max(role_scores.items(), key=lambda item: item[1]["ivr"])[0]
        cluster_roles[fallback_label] = "ivr"

    overrides: Dict[int, str] = {}
    for label, info in cluster_map.items():
        role = cluster_roles.get(label)
        if role:
            for seg_index in info["indices"]:
                overrides[seg_index] = role
    return overrides


def audio_diarization_overrides(call_id: str, transcript: Dict[str, object], segments: List[Dict[str, object]]) -> Dict[int, str]:
    if not AUDIO_DIARIZATION_AVAILABLE:
        return {}
    audio_path = _locate_audio_path(call_id, transcript)
    if audio_path is None:
        return {}
    indices, matrix, _ = _compute_segment_embeddings(audio_path, segments)
    if matrix.size == 0 or len(indices) < 2:
        return {}
    num_clusters = min(3, len(indices))
    if num_clusters < 2:
        return {}
    try:
        clustering = AgglomerativeClustering(n_clusters=num_clusters, metric="cosine", linkage="average")
        labels = clustering.fit_predict(matrix)
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] Clustering falhou ({call_id}): {exc}", file=sys.stderr)
        return {}
    return _assign_clusters_to_roles(segments, indices, labels)


def load_transcript(call_id: str) -> Dict[str, object]:
    path = TRANSCRIPT_DIR / f"{call_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Transcrição não encontrada: {path}")
    with path.open() as handle:
        return json.load(handle)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(text.strip().split())


def score_patterns(text: str, patterns: Iterable[str]) -> int:
    score = 0
    for pattern in patterns:
        if pattern in text:
            score += 1
    return score


@dataclass
class SegmentClassification:
    index: int
    role: str
    confidence: float


def classify_segments(segments: List[Dict[str, object]]) -> List[SegmentClassification]:
    results: List[SegmentClassification] = []
    previous_role: str | None = None
    seen_agent = False
    seen_customer = False

    for idx, segment in enumerate(segments):
        text = normalize_text(segment.get("text"))
        lowered = text.lower()
        if not text:
            role = previous_role or "ivr"
            confidence = 0.2
        elif any(pattern in lowered for pattern in NOISE_PATTERNS):
            role = "ivr"
            confidence = 0.99
        else:
            scores = {"ivr": 0.0, "agent": 0.0, "customer": 0.0}

            # Base heurística por padrões
            scores["ivr"] += score_patterns(lowered, IVR_PATTERNS) * 2
            scores["agent"] += score_patterns(lowered, AGENT_PATTERNS) * 2
            scores["agent"] += score_patterns(lowered, AGENT_STRONG_PATTERNS) * 3
            scores["customer"] += score_patterns(lowered, CUSTOMER_PATTERNS) * 2
            scores["customer"] += score_patterns(lowered, CUSTOMER_STRONG_PATTERNS) * 3

            # Ajustes por características do texto
            words = lowered.split()
            punctuation = {c for c in text if c in "?!¡¿"}
            if any(token.isdigit() for token in words):
                scores["ivr"] += 1.0
            if len(words) <= 3 and "buen" in lowered and "día" in lowered:
                scores["agent"] += 2.0
            if "gracias por tu espera" in lowered or "gracias por su espera" in lowered:
                scores["ivr"] += 3.0
            if "comentarios" in lowered and "pon" in lowered:
                scores["agent"] += 2.5
            if punctuation and "?" in punctuation:
                scores["customer"] += 1.0
            if len(words) >= 25:
                scores["ivr"] += 0.5  # IVR costuma ter frases longas
            if lowered.count("gracias") >= 2:
                scores["agent"] += 1.5

            first_person = sum(lowered.count(token) for token in [
                " yo ",
                " me ",
                " mi ",
                " mí ",
                "soy ",
                "estoy ",
                "llamada",
                "llamaron",
                "casa",
                "mamá",
                "mama",
                "familia",
                "nos ",
                "nuestro",
                "nuestra",
            ])
            if first_person >= 3:
                scores["customer"] += 4.0
            elif first_person == 2:
                scores["customer"] += 2.5
            elif first_person == 1:
                scores["customer"] += 1.5

            if "equivoc" in lowered or "llamada equivocada" in lowered:
                scores["customer"] += 3.5
            if lowercase := lowered.strip():
                if lowercase.startswith(("hola", "disculpe", "perdón", "perdon", "perdona")):
                    scores["customer"] += 2.0

            if "muchísimas gracias" in lowered or "muchisimas gracias" in lowered:
                scores["agent"] += 1.5

            if any(pattern in lowered for pattern in FAREWELL_PATTERNS_AGENT):
                scores["agent"] += 1.5
                scores["customer"] -= 0.5

            # Considera papel anterior (continuidade)
            if previous_role:
                scores[previous_role] += 0.3

            # Escolhe a maior pontuação
            role = max(scores.items(), key=lambda item: item[1])[0]
            confidence = scores[role] / (sum(scores.values()) + 1e-6)

            # Pós-ajustes
            if role == "ivr" and ("lo pondremos" in lowered or "contratacion" in lowered):
                role = "agent"
                confidence = max(confidence, 0.6)

        if role == "agent":
            seen_agent = True
        if role == "customer":
            seen_customer = True

        previous_role = role
        results.append(SegmentClassification(index=idx, role=role, confidence=min(confidence, 0.99)))

    # Se não encontrou agente mas há frases típicas, marca o primeiro candidato
    if not seen_agent:
        for item, segment in zip(results, segments):
            lowered = normalize_text(segment.get("text")).lower()
            if score_patterns(lowered, AGENT_PATTERNS + AGENT_STRONG_PATTERNS):
                item.role = "agent"
                item.confidence = max(item.confidence, 0.6)
                seen_agent = True
                break

    # Se nunca marcou cliente, assume que os trechos não-ivr restantes são cliente
    if not seen_customer:
        for item in results:
            if item.role == "ivr":
                continue
            if item.role != "agent":
                item.role = "customer"
                seen_customer = True
                break

    return results


def _build_segment_prompt_rows(
    segments: List[Dict[str, object]],
    baseline_roles: List[str],
) -> str:
    rows: List[str] = []
    for idx, segment in enumerate(segments):
        text = normalize_text(segment.get("text") or "")
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", start) or start)
        original = (segment.get("role") or segment.get("speaker") or "unknown").lower()
        baseline = baseline_roles[idx] if idx < len(baseline_roles) else original
        snippet = text
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        rows.append(
            f"{idx} | {start:.1f}-{end:.1f}s | original={original} | baseline={baseline} | \"{snippet}\""
        )
    return "\n".join(rows)


def llm_classify_segments(
    call_id: str,
    segments: List[Dict[str, object]],
    baseline: List[SegmentClassification],
) -> Dict[int, str]:
    if not segments:
        return {}
    baseline_roles = [item.role for item in baseline]
    table = _build_segment_prompt_rows(segments, baseline_roles)
    prompt = (
        "Você é responsável por corrigir a diarização de uma chamada.\n"
        "Cada linha abaixo representa um segmento da transcrição com o texto reconhecido e o papel sugerido.\n"
        "Reclassifique **cada segmento** usando exatamente estes rótulos: 'ivr', 'agent' ou 'customer'.\n"
        "Definições rápidas:\n"
        " - ivr: mensagens automáticas, menus, gravações ou áudios sintéticos.\n"
        " - agent: pessoa da Izzi/atendente humano oferecendo ajuda, validando dados, encerrando.\n"
        " - customer: pessoa que recebeu a chamada ou outro humano fora da Izzi.\n"
        "Regras adicionais:\n"
        " - Considere o contexto: ofertas, verificações e explicações são do agente; recusas, dúvidas ou relatos pessoais são do cliente.\n"
        " - Marque blocos breves de cumprimento ou despedida conforme quem fala (agente costuma agradecer e se identificar).\n"
        " - Mensagens repetitivas de menu ou instruções automáticas são IVR, mesmo que soem humanas.\n"
        " - Preencha todos os índices exatamente uma vez; não pule e não adicione índices novos.\n"
        "Retorne apenas um JSON com esta estrutura exata:\n"
        "{\n"
        '  "segments": [ {"index": 0, "role": "ivr"}, {"index": 1, "role": "customer"}, ... ],\n'
        '  "speaker_summary": [ {"role": "ivr", "count": <int>, "evidence": "<frases-chave>"} ... ]\n'
        "}\n"
        "Utilize aspas duplas e rótulos em minúsculas. Se o segmento estiver vazio, mantenha o papel sugerido pela heurística.\n"
        f"Call ID: {call_id}\n"
        "Segmentos (index | tempo | papéis | texto):\n"
        f"{table}\n"
    )

    try:
        response = call_openai(DIARIZATION_LLM_MODEL, prompt)
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] LLM diarization falhou ({call_id}): {exc}", file=sys.stderr)
        return {}

    assignments: Dict[int, str] = {}
    segments_resp = response.get("segments")
    if isinstance(segments_resp, list):
        for item in segments_resp:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            role = (item.get("role") or "").strip().lower()
            if isinstance(idx, int) and role in VALID_ROLES:
                assignments[idx] = role
    return assignments


def process_call(call_id: str) -> Path:
    data = load_transcript(call_id)
    segments = data.get("segments") or []
    if not segments:
        raise ValueError(f"Transcrição sem segmentos: {call_id}")

    classified = classify_segments(segments)
    audio_roles = audio_diarization_overrides(call_id, data, segments)
    if audio_roles:
        for item in classified:
            if item.index in audio_roles:
                item.role = audio_roles[item.index]
                item.confidence = max(item.confidence, 0.85)
    baseline_role_map = {item.index: item.role for item in classified}
    llm_roles = llm_classify_segments(call_id, segments, classified)
    if llm_roles:
        for item in classified:
            if item.index in llm_roles:
                item.role = llm_roles[item.index]
                heuristic_role = baseline_role_map.get(item.index, item.role)
                if llm_roles[item.index] == heuristic_role:
                    item.confidence = max(item.confidence, 0.97)
                else:
                    item.confidence = max(item.confidence, 0.9)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{call_id}.annotated.json"

    enriched_segments = []
    for item, segment in zip(classified, segments):
        normalized_text = normalize_text(segment.get("text"))
        lowered = normalized_text.lower()
        role = item.role
        if "subtítulos" in lowered or "subtitulos" in lowered:
            role = "ivr"
        elif "señorita" in lowered and "bye" in lowered and role != "ivr":
            role = "agent"
        enriched_segments.append(
            {
                "segment_index": item.index,
                "start": float(segment.get("start", 0.0) or 0.0),
                "end": float(segment.get("end", 0.0) or 0.0),
                "text": normalized_text,
                "original_role": (segment.get("role") or segment.get("speaker") or "unknown").lower(),
                "role": role,
                "confidence": round(item.confidence, 3),
            }
        )

    summary = {
        "call_id": call_id,
        "segments": enriched_segments,
        "agent_segments": sum(1 for item in enriched_segments if item["role"] == "agent"),
        "customer_segments": sum(1 for item in enriched_segments if item["role"] == "customer"),
        "ivr_segments": sum(1 for item in enriched_segments if item["role"] == "ivr"),
    }

    with output_path.open("w") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    return output_path


def iter_call_ids(all_calls: bool, ids: List[str]) -> List[str]:
    if all_calls:
        return sorted(
            fname.stem
            for fname in TRANSCRIPT_DIR.iterdir()
            if fname.suffix == ".json" and fname.stem not in {"full_analysis", "global_metrics"}
        )
    return sorted(set(ids))


def main() -> None:
    parser = argparse.ArgumentParser(description="Heurística de diarização por transcrição.")
    parser.add_argument("--call-id", action="append", help="ID da chamada (pode repetir).")
    parser.add_argument("--all", action="store_true", help="Processa todos os arquivos em engine/*.json.")
    args = parser.parse_args()

    targets = iter_call_ids(args.all, args.call_id or [])
    if not targets:
        parser.error("Informe --all ou ao menos um --call-id.")

    processed = 0
    for call_id in targets:
        try:
            output = process_call(call_id)
            print(f"[OK] {call_id} → {output.relative_to(ROOT_DIR)}")
            processed += 1
        except Exception as exc:  # pragma: no cover
            print(f"[ERRO] {call_id}: {exc}", file=sys.stderr)

    print(f"\nTotal processado: {processed} chamadas")


if __name__ == "__main__":
    main()
