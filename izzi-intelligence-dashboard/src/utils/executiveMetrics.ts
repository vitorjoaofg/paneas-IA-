import type { PerCallDetail } from "../types";

export interface SummaryMetrics {
  totalCalls: number;
  divergenceRate: number;
  followUpRate: number;
  angryRate: number;
  averageDurationMinutes: number;
  averageEngagement: number;
  averageSentiment: number;
}

export interface QualityMetrics {
  scriptAlignedRate: number;
  originRecognitionRate: number;
  pitchSatisfactoryRate: number;
  contraArgumentRate: number;
  averageSilence: number;
  averagePitchScore: number;
}

export interface AlertInfo {
  id: string;
  severity: "critical" | "warning" | "info";
  message: string;
}

export interface StatusDistributionItem {
  status: string;
  count: number;
  percent: number;
}

export interface DivergenceDonutItem {
  label: "divergent" | "aligned";
  value: number;
}

export interface TimelinePoint {
  date: string;
  divergenceRate: number;
  followUpRate: number;
  total: number;
}

export interface HeatmapPoint {
  engagementBucket: string;
  sentimentBucket: string;
  value: number;
}

export interface ExecutiveMetricsResult {
  summary: SummaryMetrics;
  quality: QualityMetrics;
  alerts: AlertInfo[];
  statusDistribution: StatusDistributionItem[];
  divergenceDonut: DivergenceDonutItem[];
  timeline: TimelinePoint[];
  heatmap: HeatmapPoint[];
  aiSummary: string;
}

const SENTIMENT_BUCKETS = [-1.0, -0.5, 0, 0.5, 1.0];
const ENGAGEMENT_BUCKETS = [0, 0.2, 0.4, 0.6, 0.8, 1.0];

const toBucketLabel = (value: number, buckets: number[]) => {
  for (let i = 0; i < buckets.length - 1; i += 1) {
    const start = buckets[i];
    const end = buckets[i + 1];
    if (value >= start && value <= end) {
      return `${start.toFixed(1)}-${end.toFixed(1)}`;
    }
  }
  return `${buckets[0].toFixed(1)}-${buckets[buckets.length - 1].toFixed(1)}`;
};

const safeAverage = (values: number[]) => {
  const valid = values.filter((value) => Number.isFinite(value));
  if (!valid.length) {
    return 0;
  }
  return valid.reduce((acc, value) => acc + value, 0) / valid.length;
};

const calcRate = (count: number, total: number) => {
  if (!total) {
    return 0;
  }
  return count / total;
};

const parseDate = (raw: string | null | undefined) => {
  if (!raw) return null;
  const [date] = raw.split(" ");
  if (!date) return null;
  const [day, month, year] = date.split("/");
  if (!day || !month || !year) return null;
  return new Date(Number(year), Number(month) - 1, Number(day));
};

const findTopIslandBy = (
  rows: PerCallDetail[],
  accessor: (row: PerCallDetail) => number,
  predicate: (row: PerCallDetail) => boolean = () => true,
) => {
  const map = new Map<string, { total: number; metric: number }>();
  rows.forEach((row) => {
    if (!predicate(row)) return;
    const island = row.island ?? row.queue ?? "Indefinido";
    const entry = map.get(island) ?? { total: 0, metric: 0 };
    entry.total += 1;
    entry.metric += accessor(row);
    map.set(island, entry);
  });
  const scored = Array.from(map.entries()).map(([key, { total, metric }]) => ({
    island: key,
    rate: total ? metric / total : 0,
    total,
  }));
  return scored.sort((a, b) => b.rate - a.rate)[0];
};

export const calculateExecutiveMetrics = (rows: PerCallDetail[]): ExecutiveMetricsResult => {
  const total = rows.length;
  if (total === 0) {
    return {
      summary: {
        totalCalls: 0,
        divergenceRate: 0,
        followUpRate: 0,
        angryRate: 0,
        averageDurationMinutes: 0,
        averageEngagement: 0,
        averageSentiment: 0,
      },
      quality: {
        scriptAlignedRate: 0,
        originRecognitionRate: 0,
        pitchSatisfactoryRate: 0,
        contraArgumentRate: 0,
        averageSilence: 0,
        averagePitchScore: 0,
      },
      alerts: [],
      statusDistribution: [],
      divergenceDonut: [
        { label: "divergent", value: 0 },
        { label: "aligned", value: 0 },
      ],
      timeline: [],
      heatmap: [],
      aiSummary: "",
    };
  }

  const divergentCount = rows.filter((row) => row.divergente === 1).length;
  const followUps = rows.filter((row) => row.follow_up_commitment === 1).length;
  const angry = rows.filter((row) => row.customer_anger_detected === 1).length;
  const durations = rows.map((row) => Number(row.duration_seconds_transcript || 0));
  const engagements = rows.map((row) => Number(row.customer_engagement_score || 0));
  const sentiments = rows.map((row) => Number(row.customer_sentiment_score || 0));
  const silences = rows.map((row) => Number(row.silence_ratio || 0));
  const pitchScores = rows.map((row) => Number(row.sales_pitch_score || 0));

  const alignedRows = rows.filter((row) => row.script_alignment_label === "aligned");
  const scriptApplicable = rows.filter((row) => row.script_alignment_label && row.script_alignment_label !== "unknown");
  const scriptAlignedRate = calcRate(alignedRows.length, scriptApplicable.length || total);

  const originRecognized = rows.filter((row) => row.operator_source_awareness === 1).length;
  const pitchSatisfactory = rows.filter((row) => {
    if (Number.isFinite(row.sales_pitch_score) && Number(row.sales_pitch_score) >= 0.7) return true;
    return row.sales_pitch_label === "satisfactory";
  }).length;
  const contraArguments = rows.filter((row) => (row.objection_handled ?? 0) === 1 || (row.objection_handled_count ?? 0) > 0).length;

  const statusMap = new Map<string, number>();
  rows.forEach((row) => {
    const key = row.status_real_detectado || "desconhecido";
    statusMap.set(key, (statusMap.get(key) ?? 0) + 1);
  });
  const statusDistribution: StatusDistributionItem[] = Array.from(statusMap.entries()).map(([status, count]) => ({
    status,
    count,
    percent: calcRate(count, total),
  }));

  const divergenceDonut: DivergenceDonutItem[] = [
    { label: "divergent", value: divergentCount },
    { label: "aligned", value: total - divergentCount },
  ];

  const timelineMap = new Map<string, { total: number; divergent: number; followUp: number }>();
  rows.forEach((row) => {
    const parsed = parseDate(row.call_datetime);
    if (!parsed) return;
    const key = [
      parsed.getFullYear(),
      String(parsed.getMonth() + 1).padStart(2, "0"),
      String(parsed.getDate()).padStart(2, "0"),
    ].join("-");
    const entry = timelineMap.get(key) ?? { total: 0, divergent: 0, followUp: 0 };
    entry.total += 1;
    entry.divergent += row.divergente === 1 ? 1 : 0;
    entry.followUp += row.follow_up_commitment === 1 ? 1 : 0;
    timelineMap.set(key, entry);
  });
  const timeline: TimelinePoint[] = Array.from(timelineMap.entries())
    .map(([date, values]) => ({
      date,
      divergenceRate: calcRate(values.divergent, values.total),
      followUpRate: calcRate(values.followUp, values.total),
      total: values.total,
    }))
    .sort((a, b) => (a.date < b.date ? -1 : 1));

  const heatmapMap = new Map<string, number>();
  rows.forEach((row) => {
    const engagement = Number(row.customer_engagement_score ?? 0);
    const sentiment = Number(row.customer_sentiment_score ?? 0);
    const engagementLabel = toBucketLabel(Math.min(Math.max(engagement, 0), 1), ENGAGEMENT_BUCKETS);
    const sentimentLabel = toBucketLabel(Math.min(Math.max(sentiment, -1), 1), SENTIMENT_BUCKETS);
    const key = `${engagementLabel}|${sentimentLabel}`;
    heatmapMap.set(key, (heatmapMap.get(key) ?? 0) + 1);
  });
  const heatmap: HeatmapPoint[] = Array.from(heatmapMap.entries()).map(([key, value]) => {
    const [engagementBucket, sentimentBucket] = key.split("|");
    return { engagementBucket, sentimentBucket, value };
  });

  const summary: SummaryMetrics = {
    totalCalls: total,
    divergenceRate: calcRate(divergentCount, total),
    followUpRate: calcRate(followUps, total),
    angryRate: calcRate(angry, total),
    averageDurationMinutes: safeAverage(durations) / 60,
    averageEngagement: safeAverage(engagements),
    averageSentiment: safeAverage(sentiments),
  };

  const quality: QualityMetrics = {
    scriptAlignedRate,
    originRecognitionRate: calcRate(originRecognized, total),
    pitchSatisfactoryRate: calcRate(pitchSatisfactory, total),
    contraArgumentRate: calcRate(contraArguments, total),
    averageSilence: safeAverage(silences),
    averagePitchScore: safeAverage(pitchScores),
  };

  const alerts: AlertInfo[] = [];

  if (summary.divergenceRate > 0.5) {
    const hotspot = findTopIslandBy(rows, (row) => (row.divergente === 1 ? 1 : 0));
    if (hotspot) {
      alerts.push({
        id: "divergence",
        severity: "critical",
        message: `A ilha ${hotspot.island} apresentou ${Math.round(hotspot.rate * 100)}% de divergência em ${hotspot.total} chamadas.`,
      });
    } else {
      alerts.push({
        id: "divergence",
        severity: "critical",
        message: "A taxa de divergência superou 50% no recorte atual.",
      });
    }
  }

  if (quality.pitchSatisfactoryRate < 0.7 || quality.averagePitchScore < 0.7) {
    alerts.push({
      id: "pitch",
      severity: "warning",
      message: `Pitch comercial está fraco (${Math.round(quality.pitchSatisfactoryRate * 100)}% de notas satisfatórias; média ${quality.averagePitchScore.toFixed(2)}).`,
    });
  }

  if (summary.angryRate > 0.1) {
    const angerHotspot = findTopIslandBy(rows, (row) => (row.customer_anger_detected === 1 ? 1 : 0), (row) => row.customer_anger_detected === 1);
    alerts.push({
      id: "anger",
      severity: "warning",
      message: angerHotspot
        ? `Clientes irritados acima de 10%. A ilha ${angerHotspot.island} concentra ${(angerHotspot.rate * 100).toFixed(1)}% dos casos.`
        : "Clientes irritados acima de 10% no período analisado.",
    });
  }

  if (summary.averageEngagement < 0.4) {
    alerts.push({
      id: "engagement",
      severity: "warning",
      message: `Engajamento médio baixo (${summary.averageEngagement.toFixed(2)}). Avalie estratégia de abordagem.`,
    });
  }

  const lastTimeline = timeline[timeline.length - 1];
  const firstTimeline = timeline[0];
  const divergenceDelta =
    timeline.length > 1 ? lastTimeline.divergenceRate - firstTimeline.divergenceRate : summary.divergenceRate;
  const followUpDelta =
    timeline.length > 1 ? lastTimeline.followUpRate - firstTimeline.followUpRate : summary.followUpRate;

  let aiSummary = "";
  if (timeline.length > 1) {
    const divergenceText = `${Math.round(Math.abs(divergenceDelta) * 100)} pontos`;
    const followUpText = `${Math.round(Math.abs(followUpDelta) * 100)} pontos`;
    aiSummary = `A divergência variou ${divergenceText} ao longo do período analisado, enquanto os follow-ups oscilaram ${followUpText}. O engajamento médio é ${summary.averageEngagement.toFixed(2)} e o silêncio ocupou ${Math.round(quality.averageSilence * 100)}% das ligações.`;
  } else {
    aiSummary = `O recorte atual possui ${summary.totalCalls} chamadas, com ${Math.round(summary.divergenceRate * 100)}% de divergência, engajamento médio de ${summary.averageEngagement.toFixed(2)} e silêncio médio de ${Math.round(quality.averageSilence * 100)}%.`;
  }

  return {
    summary,
    quality,
    alerts,
    statusDistribution,
    divergenceDonut,
    timeline,
    heatmap,
    aiSummary,
  };
};
