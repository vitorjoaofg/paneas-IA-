export interface NumericStats {
  avg: number;
  median: number;
  min: number;
  max: number;
  std: number;
}

export interface DatasetSummary {
  total_calls: number;
  calls_with_agent: number;
  calls_with_customer_after_agent: number;
  ivr_only_calls: number;
  voicemail_detected_calls: number;
  customer_only_calls: number;
  connected_calls: number;
  connected_call_ratio: number;
  low_audio_transcription_calls: number;
  divergent_calls: number;
  divergence_rate: number;
  total_duration_transcript_seconds: number;
  total_words_customer: number;
  total_words_agent: number;
  talk_ratio_customer: NumericStats;
  talk_ratio_agent: NumericStats;
  talk_ratio_ivr: NumericStats;
  silence_ratio: NumericStats;
  duration_transcription: NumericStats;
  customer_sentiment_score: NumericStats;
  agent_sentiment_score: NumericStats;
  customer_engagement_score: NumericStats;
  customer_sentiment_label_distribution: Record<string, number>;
  agent_sentiment_label_distribution: Record<string, number>;
  script_alignment_counts?: Record<string, number>;
  script_alignment_applicable?: number;
  script_alignment_aligned_rate?: number;
  script_alignment_off_script_rate?: number;
  script_alignment_score_avg?: number;
  operator_source_awareness_calls?: number;
  operator_source_awareness_rate?: number;
  operator_source_awareness_level_distribution?: Record<string, number>;
  sales_pitch_distribution?: Record<string, number>;
  sales_pitch_score_avg?: number;
  sales_pitch_satisfactory_rate?: number;
  follow_up_commitment_calls?: number;
  follow_up_commitment_rate?: number;
  follow_up_by_agent?: number;
  follow_up_by_customer?: number;
  objection_handled_calls?: number;
  objection_handled_rate?: number;
  objection_sequences_total?: number;
  customer_anger_calls?: number;
  customer_anger_rate?: number;
  customer_anger_negative_sentiment_overlap?: number;
  [key: string]: unknown;
}

export interface StatusMatch {
  reported_count: number;
  matched_count: number;
  divergent_count: number;
  match_rate: number;
}

export interface StatusDetected {
  detected_count: number;
  share: number;
}

export interface ConfusionRow {
  izzi_status: string;
  actual_status: string;
  count: number;
}

export interface StatusAnalysis {
  by_izzi_status: Record<string, StatusMatch>;
  by_actual_status: Record<string, StatusDetected>;
  confusion_matrix: ConfusionRow[];
}

export interface DivergenceReason {
  reason: string;
  count: number;
}

export interface DivergenceSummary {
  total_divergent_calls: number;
  divergence_rate: number;
  divergence_breakdown: DivergenceReason[];
}

export interface PerCallDetail {
  call_id: string;
  script: string | null;
  product_offer: string | null;
  queue: string | null;
  contact_type: string | null;
  call_datetime: string | null;
  duration_seconds_metadata: number;
  duration_seconds_transcript: number;
  duration_seconds_transcript_raw: number;
  duration_reference_seconds: number;
  word_count_total: number;
  unique_word_count: number;
  segment_count: number;
  turn_count: number;
  avg_words_per_segment: number;
  avg_segment_duration: number;
  words_agent: number;
  words_customer: number;
  words_ivr: number;
  talk_time_agent: number;
  talk_time_customer: number;
  talk_time_ivr: number;
  silence_time_estimate: number;
  silence_ratio: number;
  talk_ratio_agent: number;
  talk_ratio_customer: number;
  talk_ratio_ivr: number;
  speech_rate_agent_wpm: number;
  speech_rate_customer_wpm: number;
  customer_sentiment_score: number;
  customer_sentiment_label: string;
  agent_sentiment_score: number;
  agent_sentiment_label: string;
  customer_engagement_score: number;
  customer_after_agent: number;
  first_agent_start: number;
  first_customer_start: number;
  contains_voicemail_keywords: number;
  contains_invalid_number_keywords: number;
  contains_suspension_keywords: number;
  contains_fax_keywords: number;
  contains_order_keywords: number;
  agent_language_detected: number;
  script_alignment_label: string;
  script_alignment_score: number;
  script_keyword_hits: number;
  script_keyword_total: number;
  script_keywords_matched: string[];
  operator_source_awareness: number;
  operator_source_awareness_level: number;
  operator_source_awareness_matches: string[];
  sales_pitch_score: number;
  sales_pitch_label: string;
  sales_pitch_topics: string[];
  follow_up_commitment: number;
  follow_up_actor: "agent" | "customer" | null;
  follow_up_matches: string[];
  objection_handled: number;
  objection_handled_count: number;
  customer_anger_detected: number;
  customer_anger_matches: string[];
  izzi_status_reportado: string | null;
  izzi_status_normalizado: string;
  status_real_detectado: string;
  divergente: number;
  divergencia_motivo: string | null;
  llm_timeline?: { role: string; text: string }[];
  llm_notes?: string;
  llm_enrichment_source?: string;
  operator?: string | null;
  phone_number?: string | null;
  exec_id?: string | null;
  island?: string | null;
  agent_name_detected?: string | null;
  agent_name_confidence?: number | null;
  customer_name_detected?: string | null;
  customer_name_confidence?: number | null;
}

export interface DashboardData {
  dataset_summary: DatasetSummary;
  status_analysis: StatusAnalysis;
  divergence_summary: DivergenceSummary;
  per_call_details: PerCallDetail[];
}

export interface DashboardFilters {
  search: string;
  izziStatus: string;
  realStatus: string;
  divergence: "all" | "divergent" | "matched";
  sentiment: string;
  sentimentAgent: string;
  duration: [number, number];
  engagement: [number, number];
  silence: [number, number];
  product: string;
  queue: string;
  contactType: string;
  script: string;
  source: string;
  salesPitch: string;
  followUp: string;
  objection: string;
  anger: string;
}

export interface TranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
  speaker: string;
}

export type ConversationEventTone = "positive" | "negative" | "neutral";

export interface ConversationEvent {
  id: string;
  time: number;
  tone: ConversationEventTone;
  title: string;
  description: string;
  excerpt?: string;
}

export interface ConversationAlert {
  id: string;
  level: "critical" | "warning" | "info";
  message: string;
  hint?: string;
}

export interface AgentScore {
  agent: string;
  month: string;
  score: number;
  sentiment: number;
  engagement: number;
  silence: number;
  pitch: number;
  calls: number;
}
