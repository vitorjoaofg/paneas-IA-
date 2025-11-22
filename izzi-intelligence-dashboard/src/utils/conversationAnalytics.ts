import { parse, format } from "date-fns";
import type {
  AgentScore,
  ConversationAlert,
  ConversationEvent,
  ConversationEventTone,
  PerCallDetail,
  TranscriptSegment,
} from "../types";

export interface WordDatum {
  text: string;
  value: number;
}

const STOPWORDS = new Set([
  "a",
  "ao",
  "aos",
  "as",
  "da",
  "das",
  "de",
  "do",
  "dos",
  "e",
  "é",
  "foi",
  "será",
  "ser",
  "sou",
  "estou",
  "esta",
  "este",
  "estes",
  "estas",
  "isso",
  "isto",
  "que",
  "com",
  "para",
  "por",
  "pra",
  "na",
  "no",
  "nas",
  "nos",
  "em",
  "se",
  "sem",
  "mais",
  "mas",
  "ou",
  "um",
  "uma",
  "uns",
  "umas",
  "eu",
  "tu",
  "ele",
  "ela",
  "eles",
  "elas",
  "nos",
  "vos",
  "vocês",
  "ustedes",
  "usted",
  "nosotros",
  "vosotros",
  "qué",
  "que",
  "como",
  "cómo",
  "cuando",
  "cuándo",
  "donde",
  "dónde",
  "porque",
  "porqué",
  "pero",
  "sin",
  "con",
  "muy",
  "ya",
  "sí",
  "no",
  "lo",
  "la",
  "las",
  "los",
  "una",
  "uno",
  "sobre",
  "del",
  "al",
  "gente",
  "tá",
  "tô",
  "ah",
  "eh",
  "ehm",
  "hmm",
  "só",
  "vale",
  "ok",
  "okay",
  "então",
  "entonces",
  "pois",
  "entende",
  "entiende",
  "tudo",
  "todo",
  "toda",
  "todos",
  "todas",
  "bem",
  "bien",
  "boa",
  "buena",
  "bom",
  "bueno",
  "srs",
  "sr",
  "sra",
  "senhora",
  "senhor",
  "cliente",
  "agente",
  "operador",
  "operadora",
  "voz",
  "ivr",
  "tipo",
  "assim",
]);

const POSITIVE_KEYWORDS = [
  "resolvido",
  "resolvida",
  "solucionado",
  "solucionada",
  "obrigado",
  "obrigada",
  "gracias",
  "gracias",
  "perfecto",
  "perfeito",
  "excelente",
  "conforme",
  "feito",
  "listo",
  "bem",
  "funcionou",
  "funciona",
];

const NEGATIVE_KEYWORDS = [
  "cancelar",
  "cancelamento",
  "cancelación",
  "reclamar",
  "reclamação",
  "reclamación",
  "procon",
  "ombudsman",
  "processo",
  "insatisfeito",
  "insatisfecha",
  "problema",
  "não resolveu",
  "no resuelto",
  "fraude",
  "enganado",
  "enganada",
  "desligar",
  "mala",
  "pésimo",
  "horrible",
];

const FOLLOW_UP_KEYWORDS = [
  "retorno",
  "devolver",
  "te llamo",
  "llamar",
  "ligar",
  "voltar",
  "contacto",
  "contactarte",
  "follow",
  "seguimiento",
  "acompanhar",
  "retornamos",
  "retornarei",
  "agendar",
];

const RISK_KEYWORDS = [
  "cancelar",
  "cancelamento",
  "cancelación",
  "processo",
  "procon",
  "reclamar",
  "reclamação",
  "reclamación",
  "perda",
  "perder",
  "romper",
  "quebrar",
];

const DATE_FORMAT = "dd/MM/yyyy HH:mm:ss";

function normalizeWord(word: string): string {
  return word
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/gi, "")
    .toLowerCase();
}

function tokenize(text: string): string[] {
  return text
    .replace(/https?:\/\/\S+/gi, " ")
    .split(/[\s,.;:!?()\[\]{}"'«»<>¿¡…%$#@^*+=\\/-]+/)
    .map((token) => normalizeWord(token))
    .filter((token) => token.length >= 3 && !STOPWORDS.has(token) && !/^[0-9]+$/.test(token));
}

function classifySpeaker(raw: string): "agent" | "customer" | "ivr" | "other" {
  const value = raw.toLowerCase();
  if (value.includes("agent") || value.includes("agente") || value.includes("operator")) return "agent";
  if (value.includes("customer") || value.includes("cliente")) return "customer";
  if (value.includes("ivr") || value.includes("sistema")) return "ivr";
  return "other";
}

function collectFallbackTexts(rows: PerCallDetail[], role: "agent" | "customer" | "all"): string[] {
  return rows.map((row) => {
    const parts: string[] = [];
    if (role === "agent" || role === "all") {
      parts.push(row.follow_up_matches?.join(" ") ?? "");
      parts.push(row.script_keywords_matched?.join(" ") ?? "");
      parts.push(row.sales_pitch_topics?.join(" ") ?? "");
    }
    if (role === "customer" || role === "all") {
      parts.push(row.customer_anger_matches?.join(" ") ?? "");
      parts.push(row.divergencia_motivo ?? "");
    }
    parts.push(row.llm_notes ?? "");
    return parts.filter(Boolean).join(" ");
  });
}

export function computeWordFrequencies(
  segmentsMap: Map<string, TranscriptSegment[]>,
  options: { role: "agent" | "customer" | "all"; limit?: number; fallbackRows?: PerCallDetail[] } = { role: "all" },
): WordDatum[] {
  const limit = options.limit ?? 80;
  const counts = new Map<string, number>();

  segmentsMap.forEach((segments) => {
    segments.forEach((segment) => {
      const speaker = classifySpeaker(segment.speaker);
      if (options.role === "agent" && speaker !== "agent") return;
      if (options.role === "customer" && speaker !== "customer") return;
      if (segment.text?.length) {
        const tokens = tokenize(segment.text);
        tokens.forEach((token) => {
          counts.set(token, (counts.get(token) ?? 0) + 1);
        });
      }
    });
  });

  if (counts.size === 0 && options.fallbackRows?.length) {
    const texts = collectFallbackTexts(options.fallbackRows, options.role);
    texts.forEach((text) => {
      tokenize(text).forEach((token) => {
        counts.set(token, (counts.get(token) ?? 0) + 1);
      });
    });
  }

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([text, value]) => ({ text, value }));
}

export function summarizeEngagement(score: number): string {
  if (!Number.isFinite(score)) return "desconhecido";
  if (score >= 0.6) return "alto";
  if (score >= 0.35) return "moderado";
  if (score > 0) return "baixo";
  return "nulo";
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0m00s";
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}m${remainder}s`;
}

function safeLower(text: string | null | undefined): string {
  return (text ?? "").toLowerCase();
}

export function buildConversationSummary(
  call: PerCallDetail,
  options: { segments?: TranscriptSegment[]; fallbackReason?: string } = {},
): string[] {
  const reason = call.izzi_status_reportado || call.divergencia_motivo || options.fallbackReason || "motivo não identificado";
  const sentimentLabel = call.customer_sentiment_label;
  const anger = call.customer_anger_detected === 1;
  const sentimentScore = call.customer_sentiment_score;
  const engagement = call.customer_engagement_score;
  const sentimentAdjective = anger
    ? "irritado"
    : sentimentLabel === "positive"
      ? "satisfeito"
      : sentimentLabel === "neutral"
        ? "neutro"
        : "insatisfeito";

  const resolutionStatus = safeLower(call.status_real_detectado);
  const resolved = /resolvid|solucion|venta exitosa|efectiv/.test(resolutionStatus);
  const partiallyResolved = /parcial|parcialmente/.test(resolutionStatus);
  const divergenceNote = call.divergente === 1 ? "- divergência com status IZZI" : "- alinhado com status IZZI";

  const followUpLine = (() => {
    if (call.follow_up_commitment === 1) {
      const actor = call.follow_up_actor === "agent" ? "agente" : call.follow_up_actor === "customer" ? "cliente" : "não informado";
      return `Follow-up comprometido com ${actor}.`;
    }
    return "Sem follow-up registrado.";
  })();

  const summaryLines: string[] = [
    `Motivo da ligação: ${reason}.`,
    resolved
      ? "O atendente concluiu a solicitação com confirmação de resolução."
      : partiallyResolved
        ? "O atendente avançou parcialmente, mas ficou pendência aberta."
        : "O atendente não conseguiu concluir a demanda durante a chamada.",
    `Humor do cliente: ${sentimentAdjective} (sentimento ${sentimentScore.toFixed(2)}).`,
    call.divergente === 1
      ? `Status real indica divergência ${divergenceNote}.`
      : `Status real confirma aderência ${divergenceNote}.`,
    `Engajamento do cliente: ${summarizeEngagement(engagement)} (${engagement.toFixed(2)}).`,
    `Duração de ${formatDuration(call.duration_seconds_transcript)} · ${followUpLine}`,
  ];

  const notes = call.llm_notes?.trim();
  if (notes) {
    summaryLines.push(`Resumo automático: ${notes}`);
  }

  return summaryLines;
}

function parseCallDate(call: PerCallDetail): Date | null {
  if (!call.call_datetime) return null;
  const parsed = parse(call.call_datetime, DATE_FORMAT, new Date());
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function getMonthKey(call: PerCallDetail): string | null {
  const date = parseCallDate(call);
  if (!date) return null;
  return format(date, "yyyy-MM");
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function normalizeSentiment(score: number): number {
  if (!Number.isFinite(score)) return 0.5;
  return clamp01((score + 1) / 2);
}

export function computeAgentScores(rows: PerCallDetail[]): {
  scores: AgentScore[];
  months: string[];
} {
  const metrics = new Map<string, { sentiment: number; engagement: number; silence: number; pitch: number; calls: number }>();

  rows.forEach((row) => {
    const agent = row.operator?.trim() || "Agente desconhecido";
    const month = getMonthKey(row);
    if (!month) return;
    const key = `${agent}::${month}`;
    if (!metrics.has(key)) {
      metrics.set(key, { sentiment: 0, engagement: 0, silence: 0, pitch: 0, calls: 0 });
    }
    const entry = metrics.get(key)!;
    entry.calls += 1;
    entry.sentiment += normalizeSentiment(row.customer_sentiment_score);
    entry.engagement += clamp01(row.customer_engagement_score);
    entry.silence += clamp01(1 - clamp01(row.silence_ratio));
    const pitchValue = row.sales_pitch_label === "satisfactory" ? 1 : row.sales_pitch_label === "nominal" ? 0.5 : 0;
    entry.pitch += pitchValue;
  });

  const scores: AgentScore[] = [];
  metrics.forEach((value, key) => {
    const [agent, month] = key.split("::");
    if (value.calls === 0) return;
    const sentiment = value.sentiment / value.calls;
    const engagement = value.engagement / value.calls;
    const silence = value.silence / value.calls;
    const pitch = value.pitch / value.calls;
    const score = sentiment * 0.4 + engagement * 0.3 + silence * 0.2 + pitch * 0.1;
    scores.push({ agent, month, score, sentiment, engagement, silence, pitch, calls: value.calls });
  });

  const months = Array.from(new Set(scores.map((item) => item.month))).sort();
  return { scores, months };
}

function buildEvent(
  id: string,
  time: number,
  tone: ConversationEventTone,
  title: string,
  description: string,
  excerpt?: string,
): ConversationEvent {
  return { id, time, tone, title, description, excerpt };
}

export function buildTimelineEvents(call: PerCallDetail, segments: TranscriptSegment[]): ConversationEvent[] {
  const events: ConversationEvent[] = [];
  const duration = segments.length
    ? segments.reduce((acc, segment) => Math.max(acc, segment.end ?? acc), call.duration_seconds_transcript)
    : call.duration_seconds_transcript;

  events.push(
    buildEvent(
      `${call.call_id}-start`,
      0,
      "neutral",
      "Início da conversa",
      `Chamada iniciada às ${call.call_datetime ?? "horário desconhecido"}.`,
      segments[0]?.text,
    ),
  );

  segments.forEach((segment, index) => {
    const time = Number.isFinite(segment.start) ? segment.start : index;
    const text = segment.text ?? "";
    const lower = text.toLowerCase();
    if (!lower) return;
    if (POSITIVE_KEYWORDS.some((word) => lower.includes(word))) {
      events.push(
        buildEvent(
          `${call.call_id}-pos-${index}`,
          time,
          "positive",
          "Ponto positivo",
          "Indício de progresso ou satisfação registrado no diálogo.",
          text,
        ),
      );
    }
    if (NEGATIVE_KEYWORDS.some((word) => lower.includes(word))) {
      events.push(
        buildEvent(
          `${call.call_id}-neg-${index}`,
          time,
          "negative",
          "Ponto negativo",
          "Sinalização de risco, conflito ou intenção de cancelamento.",
          text,
        ),
      );
    }
  });

  if (call.follow_up_commitment === 1) {
    events.push(
      buildEvent(
        `${call.call_id}-followup`,
        duration - 5,
        "neutral",
        "Follow-up combinado",
        call.follow_up_actor === "agent"
          ? "Agente mantém responsabilidade pelo retorno."
          : call.follow_up_actor === "customer"
            ? "Cliente ficou encarregado de retornar."
            : "Follow-up sem responsável definido.",
      ),
    );
  }

  const sentimentTone: ConversationEventTone = call.customer_sentiment_score < 0.2 ? "negative" : call.customer_sentiment_score > 0.5 ? "positive" : "neutral";
  events.push(
    buildEvent(
      `${call.call_id}-outcome`,
      duration,
      sentimentTone,
      "Clima final",
      `Sentimento ${call.customer_sentiment_label} (${call.customer_sentiment_score.toFixed(2)}).`,
    ),
  );

  if (segments.length === 0) {
    const notes = call.llm_notes?.toLowerCase() ?? "";
    if (notes.includes("cancel") || notes.includes("reclama")) {
      events.push(
        buildEvent(
          `${call.call_id}-note-risk`,
          duration * 0.6,
          "negative",
          "Risco identificado",
          "Resumo indica termos críticos (cancelamento, reclamação).",
          call.llm_notes ?? undefined,
        ),
      );
    } else if (notes.includes("resol") || notes.includes("solucion")) {
      events.push(
        buildEvent(
          `${call.call_id}-note-solution`,
          duration * 0.6,
          "positive",
          "Indício de solução",
          "Resumo aponta resolução do atendimento.",
          call.llm_notes ?? undefined,
        ),
      );
    }
  }

  return events.sort((a, b) => a.time - b.time);
}

function hasConsecutiveAnger(rows: PerCallDetail[], target: PerCallDetail): boolean {
  const phone = target.phone_number || target.call_id;
  if (!phone) return false;
  const relevant = rows
    .filter((row) => (row.phone_number || row.call_id) === phone)
    .map((row) => ({ row, date: parseCallDate(row) }))
    .filter((item) => item.date !== null)
    .sort((a, b) => (a.date!.getTime() > b.date!.getTime() ? 1 : -1));

  let consecutive = 0;
  for (const item of relevant) {
    const angry = item.row.customer_anger_detected === 1 || safeLower(item.row.customer_sentiment_label).includes("negative");
    if (angry) {
      consecutive += 1;
    } else {
      consecutive = 0;
    }
    if (item.row.call_id === target.call_id && consecutive >= 2) {
      return true;
    }
  }
  return false;
}

function findKeywordMatches(segments: TranscriptSegment[], keywords: string[], fallbackText?: string): string[] {
  const matches: string[] = [];
  const lowerKeywords = keywords.map((keyword) => keyword.toLowerCase());
  segments.forEach((segment) => {
    const text = segment.text?.toLowerCase() ?? "";
    if (!text) return;
    lowerKeywords.forEach((keyword) => {
      if (text.includes(keyword)) {
        matches.push(segment.text.trim());
      }
    });
  });
  if (matches.length === 0 && fallbackText) {
    const lower = fallbackText.toLowerCase();
    lowerKeywords.forEach((keyword) => {
      if (lower.includes(keyword)) {
        matches.push(fallbackText.trim());
      }
    });
  }
  return matches;
}

export function buildAlerts(
  call: PerCallDetail,
  rows: PerCallDetail[],
  segments: TranscriptSegment[],
): ConversationAlert[] {
  const alerts: ConversationAlert[] = [];
  const fallbackText = call.llm_notes ?? "";

  if (hasConsecutiveAnger(rows, call)) {
    alerts.push({
      id: `${call.call_id}-anger`,
      level: "critical",
      message: "Cliente irritado em chamadas consecutivas para o mesmo número.",
      hint: "Recomenda-se ação pró-ativa da equipe de relacionamento.",
    });
  }

  if (call.silence_ratio > 0.4 || safeLower(call.sales_pitch_label) === "fragile") {
    alerts.push({
      id: `${call.call_id}-silence`,
      level: "warning",
      message: "Atendente apresentou silêncio prolongado ou pitch fraco.",
      hint: `Silêncio: ${(call.silence_ratio * 100).toFixed(1)}% · Pitch ${call.sales_pitch_label || "desconhecido"}`,
    });
  }

  if (call.customer_sentiment_score < 0.2) {
    alerts.push({
      id: `${call.call_id}-sentiment`,
      level: "critical",
      message: "Sentimento crítico identificado (score < 0.2).",
      hint: `Sentimento ${call.customer_sentiment_label} (${call.customer_sentiment_score.toFixed(2)}).`,
    });
  }

  const followUpMentions = findKeywordMatches(segments, FOLLOW_UP_KEYWORDS, fallbackText);
  if (followUpMentions.length && call.follow_up_commitment !== 1) {
    alerts.push({
      id: `${call.call_id}-followup-missed`,
      level: "warning",
      message: "Follow-up mencionado em áudio, mas não registrado no pipeline.",
      hint: followUpMentions[0],
    });
  }

  const riskMentions = findKeywordMatches(segments, RISK_KEYWORDS, fallbackText);
  if (riskMentions.length) {
    alerts.push({
      id: `${call.call_id}-risk`,
      level: "critical",
      message: "Palavras de risco detectadas (cancelamento/processo).",
      hint: riskMentions[0],
    });
  }

  return alerts;
}

export function segmentsToMap(callIds: string[], loader: (id: string) => TranscriptSegment[] | undefined): Map<string, TranscriptSegment[]> {
  const map = new Map<string, TranscriptSegment[]>();
  callIds.forEach((id) => {
    const segments = loader(id);
    if (segments && segments.length) {
      map.set(id, segments);
    }
  });
  return map;
}
