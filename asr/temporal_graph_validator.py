"""
Temporal Graph Validator for Speaker Diarization.
Models conversation as a directed graph to detect and fix impossible speaker transitions.
"""

import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict, Counter
import statistics

logger = logging.getLogger(__name__)


class ConversationGraph:
    """Models conversation flow as a directed graph for validation."""

    def __init__(self, segments: List[Dict[str, Any]]):
        """
        Initialize conversation graph from segments.

        Args:
            segments: List of diarized segments with speaker labels
        """
        self.segments = segments
        self.transitions = defaultdict(int)
        self.speaker_stats = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0.0,
            'avg_duration': 0.0,
            'max_duration': 0.0,
            'min_duration': float('inf')
        })

        self._build_graph()

    def _build_graph(self):
        """Build transition graph and compute speaker statistics."""
        for i, seg in enumerate(self.segments):
            speaker = seg.get("speaker", "Unknown")
            duration = seg.get("end", 0.0) - seg.get("start", 0.0)

            # Update speaker stats
            stats = self.speaker_stats[speaker]
            stats['count'] += 1
            stats['total_duration'] += duration
            stats['max_duration'] = max(stats['max_duration'], duration)
            stats['min_duration'] = min(stats['min_duration'], duration)

            # Record transition
            if i > 0:
                prev_speaker = self.segments[i-1].get("speaker", "Unknown")
                self.transitions[(prev_speaker, speaker)] += 1

        # Compute averages
        for speaker, stats in self.speaker_stats.items():
            if stats['count'] > 0:
                stats['avg_duration'] = stats['total_duration'] / stats['count']

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalous patterns in the conversation graph.

        Returns:
            List of anomaly dictionaries with type, severity, and details
        """
        anomalies = []

        # Anomaly 1: Excessive consecutive segments from same speaker
        anomalies.extend(self._detect_excessive_consecutive())

        # Anomaly 2: Unusual speaker dominance
        anomalies.extend(self._detect_unusual_dominance())

        # Anomaly 3: Impossible short transitions
        anomalies.extend(self._detect_impossible_transitions())

        # Anomaly 4: Missing expected role (in call center context)
        anomalies.extend(self._detect_missing_roles())

        return anomalies

    def _detect_excessive_consecutive(self) -> List[Dict[str, Any]]:
        """Detect when same speaker has too many consecutive segments."""
        anomalies = []
        current_speaker = None
        consecutive_count = 0
        start_idx = 0

        for i, seg in enumerate(self.segments):
            speaker = seg.get("speaker", "Unknown")

            if speaker == current_speaker:
                consecutive_count += 1
            else:
                # Check if previous run was excessive
                if consecutive_count > 5:  # More than 5 consecutive segments is suspicious
                    total_duration = sum(
                        self.segments[j].get("end", 0.0) - self.segments[j].get("start", 0.0)
                        for j in range(start_idx, i)
                    )

                    # If total duration is short (< 10s), likely segmentation error
                    if total_duration < 10.0:
                        anomalies.append({
                            'type': 'excessive_consecutive',
                            'severity': 'high',
                            'speaker': current_speaker,
                            'start_idx': start_idx,
                            'end_idx': i - 1,
                            'count': consecutive_count,
                            'total_duration': total_duration,
                            'message': f"{current_speaker} has {consecutive_count} consecutive short segments ({total_duration:.1f}s total)"
                        })

                # Reset counter
                current_speaker = speaker
                consecutive_count = 1
                start_idx = i

        return anomalies

    def _detect_unusual_dominance(self) -> List[Dict[str, Any]]:
        """Detect when one speaker dominates unusually (>85% of segments)."""
        anomalies = []
        total_segments = len(self.segments)

        if total_segments == 0:
            return anomalies

        for speaker, stats in self.speaker_stats.items():
            dominance_ratio = stats['count'] / total_segments

            if dominance_ratio > 0.85:  # One speaker > 85% of segments
                anomalies.append({
                    'type': 'unusual_dominance',
                    'severity': 'medium',
                    'speaker': speaker,
                    'ratio': dominance_ratio,
                    'count': stats['count'],
                    'total': total_segments,
                    'message': f"{speaker} dominates {dominance_ratio*100:.1f}% of segments"
                })

        return anomalies

    def _detect_impossible_transitions(self) -> List[Dict[str, Any]]:
        """Detect transitions that are physically impossible (overlapping, too fast)."""
        anomalies = []

        for i in range(1, len(self.segments)):
            prev_seg = self.segments[i-1]
            curr_seg = self.segments[i]

            prev_end = prev_seg.get("end", 0.0)
            curr_start = curr_seg.get("start", 0.0)
            gap = curr_start - prev_end

            prev_speaker = prev_seg.get("speaker", "Unknown")
            curr_speaker = curr_seg.get("speaker", "Unknown")

            # Negative gap = overlap (possible but suspicious if large)
            if gap < -0.5:  # More than 0.5s overlap
                anomalies.append({
                    'type': 'impossible_overlap',
                    'severity': 'high',
                    'index': i,
                    'gap': gap,
                    'prev_speaker': prev_speaker,
                    'curr_speaker': curr_speaker,
                    'message': f"Segments {i-1} and {i} overlap by {-gap:.2f}s"
                })

            # Very fast alternation (< 0.05s gap) with speaker change is suspicious
            elif 0 < gap < 0.05 and prev_speaker != curr_speaker:
                anomalies.append({
                    'type': 'too_fast_transition',
                    'severity': 'medium',
                    'index': i,
                    'gap': gap,
                    'prev_speaker': prev_speaker,
                    'curr_speaker': curr_speaker,
                    'message': f"Speaker change in {gap*1000:.0f}ms is suspiciously fast"
                })

        return anomalies

    def _detect_missing_roles(self) -> List[Dict[str, Any]]:
        """Detect if expected roles are missing (for call center context)."""
        anomalies = []

        speakers = set(seg.get("speaker", "Unknown") for seg in self.segments)

        # In call center, we expect both Cliente and Atendente
        if "Cliente" not in speakers:
            anomalies.append({
                'type': 'missing_role',
                'severity': 'high',
                'role': 'Cliente',
                'message': "Missing 'Cliente' speaker in conversation"
            })

        if "Atendente" not in speakers:
            anomalies.append({
                'type': 'missing_role',
                'severity': 'high',
                'role': 'Atendente',
                'message': "Missing 'Atendente' speaker in conversation"
            })

        return anomalies

    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        return {
            'total_segments': len(self.segments),
            'total_duration': sum(
                seg.get("end", 0.0) - seg.get("start", 0.0)
                for seg in self.segments
            ),
            'speaker_stats': dict(self.speaker_stats),
            'transitions': dict(self.transitions),
            'num_speakers': len(self.speaker_stats)
        }


def validate_and_fix_temporal_consistency(
    segments: List[Dict[str, Any]],
    fix_anomalies: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate temporal consistency and optionally fix detected anomalies.

    Args:
        segments: List of diarized segments
        fix_anomalies: Whether to attempt automatic fixes

    Returns:
        Tuple of (fixed_segments, validation_report)
    """
    if not segments:
        return segments, {'anomalies': [], 'fixes_applied': 0}

    # Build conversation graph
    graph = ConversationGraph(segments)

    # Detect anomalies
    anomalies = graph.detect_anomalies()

    logger.info(f"Temporal validation: found {len(anomalies)} anomalies")
    for anomaly in anomalies:
        logger.debug(f"  [{anomaly['severity'].upper()}] {anomaly['message']}")

    fixes_applied = 0
    fixed_segments = segments.copy()

    if fix_anomalies:
        # Fix 1: Merge excessive consecutive short segments
        for anomaly in [a for a in anomalies if a['type'] == 'excessive_consecutive']:
            if anomaly['total_duration'] < 10.0:
                start_idx = anomaly['start_idx']
                end_idx = anomaly['end_idx']

                # Merge all segments in this range
                merged_text = " ".join(
                    fixed_segments[i].get("text", "")
                    for i in range(start_idx, end_idx + 1)
                )

                merged_seg = {
                    "start": fixed_segments[start_idx]["start"],
                    "end": fixed_segments[end_idx]["end"],
                    "text": merged_text,
                    "speaker": anomaly['speaker']
                }

                # Replace segments
                fixed_segments = (
                    fixed_segments[:start_idx] +
                    [merged_seg] +
                    fixed_segments[end_idx + 1:]
                )

                fixes_applied += 1
                logger.debug(f"Merged {end_idx - start_idx + 1} consecutive segments")

        # Fix 2: Correct unusual dominance by re-examining short segments
        for anomaly in [a for a in anomalies if a['type'] == 'unusual_dominance']:
            if anomaly['ratio'] > 0.85:
                dominant_speaker = anomaly['speaker']
                other_speaker = "Cliente" if dominant_speaker == "Atendente" else "Atendente"

                # Find very short segments from dominant speaker
                for i, seg in enumerate(fixed_segments):
                    if seg.get("speaker") == dominant_speaker:
                        duration = seg.get("end", 0.0) - seg.get("start", 0.0)
                        word_count = len(seg.get("text", "").split())

                        # Very short segments might be misclassified
                        if duration < 1.0 and word_count <= 2:
                            text_lower = seg.get("text", "").lower()

                            # Check if it looks like client response
                            client_keywords = ["sim", "ok", "tá", "não", "isso", "uhm", "aham"]
                            if any(kw in text_lower for kw in client_keywords):
                                fixed_segments[i]["speaker"] = other_speaker
                                fixes_applied += 1
                                logger.debug(f"Reassigned short segment '{seg.get('text')}' to {other_speaker}")

        # Fix 3: Resolve impossible overlaps
        for anomaly in [a for a in anomalies if a['type'] == 'impossible_overlap']:
            idx = anomaly['index']
            gap = anomaly['gap']

            if idx < len(fixed_segments):
                # Adjust start time to eliminate overlap
                fixed_segments[idx]["start"] = max(
                    fixed_segments[idx-1]["end"] + 0.01,
                    fixed_segments[idx]["start"]
                )
                fixes_applied += 1
                logger.debug(f"Fixed overlap at segment {idx}")

    # Generate validation report
    stats = graph.get_statistics()
    report = {
        'anomalies': anomalies,
        'fixes_applied': fixes_applied,
        'statistics': stats,
        'validation_passed': len([a for a in anomalies if a['severity'] == 'high']) == 0
    }

    logger.info(f"Temporal validation complete: {fixes_applied} fixes applied")

    return fixed_segments, report


def enforce_conversational_patterns(
    segments: List[Dict[str, Any]],
    expected_pattern: str = "call_center"
) -> List[Dict[str, Any]]:
    """
    Enforce expected conversational patterns based on context.

    Args:
        segments: List of diarized segments
        expected_pattern: Type of conversation pattern to enforce
            - "call_center": Atendente starts, alternates with Cliente

    Returns:
        Segments with enforced patterns
    """
    if not segments or expected_pattern != "call_center":
        return segments

    fixed = []

    # Rule 1: First meaningful utterance should be Cliente (answering call)
    # Rule 2: First self-introduction should be Atendente
    found_introduction = False

    for i, seg in enumerate(segments):
        text = seg.get("text", "").lower()
        speaker = seg.get("speaker", "Unknown")

        # Detect self-introduction pattern
        if not found_introduction and ("meu nome" in text or "sou da" in text or "sou do" in text):
            if "empresa" in text or len(text.split()) > 5:
                # This is the atendente introducing themselves
                seg = {**seg, "speaker": "Atendente"}
                found_introduction = True
                logger.debug(f"Enforced Atendente for introduction: '{text[:50]}...'")

        # First "Oi" or "Alô" should be Cliente
        if i == 0 and ("oi" in text or "alô" in text or "alô" in text) and len(text.split()) <= 3:
            seg = {**seg, "speaker": "Cliente"}
            logger.debug(f"Enforced Cliente for greeting: '{text}'")

        fixed.append(seg)

    # Rule 3: Detect and fix unnatural patterns (e.g., Atendente speaking 10 times in a row)
    smoothed = []
    consecutive_count = 1
    last_speaker = None

    for seg in fixed:
        speaker = seg.get("speaker")

        if speaker == last_speaker:
            consecutive_count += 1

            # If same speaker for 8+ short segments, might be wrong
            if consecutive_count >= 8:
                duration = seg.get("end", 0.0) - seg.get("start", 0.0)
                if duration < 2.0:
                    # Flip to other speaker
                    other_speaker = "Cliente" if speaker == "Atendente" else "Atendente"
                    seg = {**seg, "speaker": other_speaker}
                    logger.debug(f"Fixed excessive consecutive pattern at segment {len(smoothed)}")
                    consecutive_count = 1
                    last_speaker = other_speaker
        else:
            consecutive_count = 1
            last_speaker = speaker

        smoothed.append(seg)

    return smoothed
