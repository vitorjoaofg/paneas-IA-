"""
Diarization Quality Metrics and Confidence Scoring System.
Calculates confidence scores for speaker labels and tracks performance metrics.
"""

import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


def calculate_segment_confidence(
    segment: Dict[str, Any],
    context: Dict[str, Any]
) -> float:
    """
    Calculate confidence score for a single segment's speaker label.

    Args:
        segment: Segment with speaker label, text, duration
        context: Context information (neighboring segments, stats, etc.)

    Returns:
        Confidence score from 0.0 to 1.0
    """
    score = 0.5  # Base score

    text = segment.get("text", "").strip()
    speaker = segment.get("speaker", "Unknown")
    duration = segment.get("end", 0.0) - segment.get("start", 0.0)
    word_count = len(text.split())

    # Factor 1: Text content confidence (20%)
    if "rag_confidence" in segment:
        # Use RAG confidence if available
        score += 0.2 * segment["rag_confidence"]
    elif text:
        # Heuristic based on text characteristics
        if word_count >= 5:
            score += 0.15  # Longer text = more confident
        elif word_count >= 2:
            score += 0.10
        else:
            score += 0.05  # Very short text = less confident

    # Factor 2: Duration confidence (15%)
    if duration >= 3.0:
        score += 0.15  # Long utterance = more confident
    elif duration >= 1.0:
        score += 0.10
    elif duration >= 0.5:
        score += 0.05
    else:
        score += 0.0  # Very short = less confident

    # Factor 3: Role-specific patterns (20%)
    text_lower = text.lower()

    # Strong Atendente indicators
    atendente_keywords = ["meu nome é", "sou da", "nós da", "posso confirmar", "vou fazer", "temos"]
    if speaker == "Atendente" and any(kw in text_lower for kw in atendente_keywords):
        score += 0.20
    elif speaker == "Atendente" and duration > 5.0:
        score += 0.15  # Long speech typical for Atendente

    # Strong Cliente indicators
    client_keywords = ["sim", "ok", "tá bom", "vamos", "entendi", "isso", "oi", "alô"]
    if speaker == "Cliente" and any(kw == text_lower or text_lower.startswith(kw) for kw in client_keywords):
        score += 0.20
    elif speaker == "Cliente" and word_count <= 3 and duration < 2.0:
        score += 0.15  # Short responses typical for Cliente

    # Factor 4: Neighbor agreement (15%)
    prev_speaker = context.get("prev_speaker")
    next_speaker = context.get("next_speaker")

    if prev_speaker and next_speaker:
        if prev_speaker != speaker and next_speaker != speaker:
            # Surrounded by different speaker = high confidence
            score += 0.15
        elif prev_speaker == speaker or next_speaker == speaker:
            # Same speaker on at least one side = medium confidence
            score += 0.10
    elif prev_speaker and prev_speaker != speaker:
        score += 0.10
    elif next_speaker and next_speaker != speaker:
        score += 0.10

    # Factor 5: Temporal consistency (10%)
    if context.get("temporal_validation_passed", True):
        score += 0.10

    # Factor 6: Multi-pass agreement (20%)
    if "multi_pass_agreement" in context:
        # If multiple LLM passes agreed, high confidence
        agreement_ratio = context["multi_pass_agreement"]
        score += 0.20 * agreement_ratio

    # Normalize to [0, 1]
    return min(1.0, max(0.0, score))


def calculate_conversation_confidence(
    segments: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Calculate confidence scores for all segments and overall metrics.

    Args:
        segments: List of diarized segments

    Returns:
        Tuple of (segments_with_confidence, metrics_dict)
    """
    if not segments:
        return segments, {}

    segments_with_conf = []

    # Build context for each segment
    for i, seg in enumerate(segments):
        prev_speaker = segments[i-1].get("speaker") if i > 0 else None
        next_speaker = segments[i+1].get("speaker") if i+1 < len(segments) else None

        context = {
            "prev_speaker": prev_speaker,
            "next_speaker": next_speaker,
            "temporal_validation_passed": True,  # Assume passed if no validation run
            "multi_pass_agreement": 1.0  # Assume full agreement if no multi-pass data
        }

        confidence = calculate_segment_confidence(seg, context)

        segments_with_conf.append({
            **seg,
            "confidence": confidence
        })

    # Calculate overall metrics
    confidences = [s["confidence"] for s in segments_with_conf]
    avg_confidence = statistics.mean(confidences) if confidences else 0.0
    min_confidence = min(confidences) if confidences else 0.0
    max_confidence = max(confidences) if confidences else 0.0

    # Calculate speaker distribution
    speaker_counts = defaultdict(int)
    speaker_durations = defaultdict(float)

    for seg in segments_with_conf:
        speaker = seg.get("speaker", "Unknown")
        duration = seg.get("end", 0.0) - seg.get("start", 0.0)

        speaker_counts[speaker] += 1
        speaker_durations[speaker] += duration

    # Detect anomalies
    anomalies = []

    # Anomaly 1: Very low average confidence
    if avg_confidence < 0.5:
        anomalies.append({
            "type": "low_confidence",
            "severity": "high",
            "message": f"Average confidence is very low: {avg_confidence:.2f}"
        })

    # Anomaly 2: High variance in confidence
    if len(confidences) > 5:
        conf_stddev = statistics.stdev(confidences)
        if conf_stddev > 0.3:
            anomalies.append({
                "type": "high_variance",
                "severity": "medium",
                "message": f"High confidence variance: {conf_stddev:.2f}"
            })

    # Anomaly 3: Many low-confidence segments
    low_conf_segments = [c for c in confidences if c < 0.4]
    low_conf_ratio = len(low_conf_segments) / len(confidences) if confidences else 0

    if low_conf_ratio > 0.3:
        anomalies.append({
            "type": "many_low_confidence",
            "severity": "high",
            "message": f"{low_conf_ratio*100:.1f}% of segments have low confidence"
        })

    # Anomaly 4: Unusual speaker distribution
    if len(speaker_counts) == 2:
        counts = list(speaker_counts.values())
        ratio = max(counts) / sum(counts) if sum(counts) > 0 else 0

        if ratio > 0.9:
            anomalies.append({
                "type": "unbalanced_speakers",
                "severity": "medium",
                "message": f"One speaker dominates {ratio*100:.1f}% of segments"
            })

    metrics = {
        "avg_confidence": avg_confidence,
        "min_confidence": min_confidence,
        "max_confidence": max_confidence,
        "low_confidence_ratio": low_conf_ratio,
        "speaker_counts": dict(speaker_counts),
        "speaker_durations": {k: round(v, 2) for k, v in speaker_durations.items()},
        "total_segments": len(segments_with_conf),
        "anomalies": anomalies
    }

    logger.info(f"Confidence metrics: avg={avg_confidence:.2f}, min={min_confidence:.2f}, max={max_confidence:.2f}")
    if anomalies:
        logger.warning(f"Detected {len(anomalies)} anomalies:")
        for anomaly in anomalies:
            logger.warning(f"  [{anomaly['severity'].upper()}] {anomaly['message']}")

    return segments_with_conf, metrics


def should_use_premium_fallback(metrics: Dict[str, Any]) -> bool:
    """
    Determine if premium API fallback should be used based on metrics.

    Args:
        metrics: Metrics dictionary from calculate_conversation_confidence

    Returns:
        True if premium fallback recommended
    """
    avg_confidence = metrics.get("avg_confidence", 1.0)
    anomalies = metrics.get("anomalies", [])

    # Use premium if average confidence is very low
    if avg_confidence < 0.45:
        logger.info(f"Recommending premium fallback: avg_confidence={avg_confidence:.2f} < 0.45")
        return True

    # Use premium if there are high-severity anomalies
    high_severity_anomalies = [a for a in anomalies if a["severity"] == "high"]
    if len(high_severity_anomalies) >= 2:
        logger.info(f"Recommending premium fallback: {len(high_severity_anomalies)} high-severity anomalies")
        return True

    # Use premium if more than 40% of segments have low confidence
    low_conf_ratio = metrics.get("low_confidence_ratio", 0.0)
    if low_conf_ratio > 0.4:
        logger.info(f"Recommending premium fallback: {low_conf_ratio*100:.1f}% low confidence segments")
        return True

    return False


def generate_quality_report(
    segments: List[Dict[str, Any]],
    metrics: Dict[str, Any]
) -> str:
    """
    Generate human-readable quality report.

    Args:
        segments: Segments with confidence scores
        metrics: Metrics dictionary

    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 60)
    report.append("DIARIZATION QUALITY REPORT")
    report.append("=" * 60)

    # Overall stats
    report.append(f"\nTotal Segments: {metrics.get('total_segments', 0)}")
    report.append(f"Average Confidence: {metrics.get('avg_confidence', 0.0):.2%}")
    report.append(f"Confidence Range: {metrics.get('min_confidence', 0.0):.2%} - {metrics.get('max_confidence', 0.0):.2%}")

    # Speaker distribution
    report.append("\nSpeaker Distribution:")
    for speaker, count in metrics.get("speaker_counts", {}).items():
        duration = metrics.get("speaker_durations", {}).get(speaker, 0.0)
        report.append(f"  {speaker}: {count} segments ({duration:.1f}s total)")

    # Low confidence segments
    low_conf_segments = [s for s in segments if s.get("confidence", 1.0) < 0.4]
    if low_conf_segments:
        report.append(f"\nLow Confidence Segments ({len(low_conf_segments)}):")
        for seg in low_conf_segments[:5]:  # Show first 5
            text = seg.get("text", "")[:50]
            conf = seg.get("confidence", 0.0)
            speaker = seg.get("speaker", "Unknown")
            report.append(f"  [{conf:.2%}] {speaker}: {text}...")

    # Anomalies
    anomalies = metrics.get("anomalies", [])
    if anomalies:
        report.append(f"\nAnomalies Detected ({len(anomalies)}):")
        for anomaly in anomalies:
            report.append(f"  [{anomaly['severity'].upper()}] {anomaly['message']}")

    # Recommendation
    if should_use_premium_fallback(metrics):
        report.append("\n⚠️  RECOMMENDATION: Consider using premium API fallback for higher accuracy")
    else:
        report.append("\n✅  Quality is acceptable")

    report.append("=" * 60)

    return "\n".join(report)
