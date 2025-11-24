import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LoginPortal } from "./components/LoginPortal";
import { LanguageToggle } from "./components/LanguageToggle";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ChartLine,
  Clock3,
  CloudMoon,
  ChevronLeft,
  ChevronRight,
  Download,
  FileBarChart,
  FileSpreadsheet,
  Filter as FilterIcon,
  Flame,
  Hourglass,
  Bot,
  CalendarClock,
  Loader2,
  Megaphone,
  MicVocal,
  PhoneOff,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  User,
  X,
} from "lucide-react";
import clsx from "clsx";
import type { DashboardData, DashboardFilters, PerCallDetail, TranscriptSegment } from "./types";
import { LanguageProvider, useTranslate, getCurrentLocale } from "./i18n";
import { ExecutiveMetrics } from "./components/executive/ExecutiveMetrics";
import { QualityIndicators } from "./components/executive/QualityIndicators";
import { AlertsSummary } from "./components/executive/AlertsSummary";
import { ExecutiveCharts } from "./components/executive/ExecutiveCharts";
import { AISummary } from "./components/executive/AISummary";
import { calculateExecutiveMetrics } from "./utils/executiveMetrics";
import { formatNumber, formatPercent } from "./utils/numberFormat";
import { ReincidenciasTab } from "./components/reincidencias/ReincidenciasTab";
import { MonthlyComparisonTab } from "./components/MonthlyComparisonTab";
import { AgentPerformanceTab } from "./components/AgentPerformanceTab";
import { loadTranscript as loadTranscriptSegments, getCachedTranscript as getCachedTranscriptSegments } from "./utils/transcriptLoader";
import "./index.css";

const STORAGE_KEY = "izzi-dashboard-filters-v2";

const initialFilters: DashboardFilters = {
  search: "",
  month: "all",
  izziStatus: "all",
  realStatus: "all",
  divergence: "all",
  sentiment: "all",
  sentimentAgent: "all",
  duration: [0, 2000],
  engagement: [0, 1],
  silence: [0, 1],
  product: "all",
  queue: "all",
  contactType: "all",
  script: "all",
  source: "all",
  salesPitch: "all",
  followUp: "all",
  objection: "all",
  anger: "all",
};

const ACCENT_GRADIENT = "linear-gradient(135deg, rgba(132,183,255,0.35), rgba(78,158,255,0.12))";
const SENTIMENT_COLOR: Record<string, string> = {
  positive: "#22c55e",
  neutral: "#a5b4fc",
  negative: "#ef4444",
};
const SENTIMENT_EMOJI: Record<string, string> = {
  positive: "😊",
  neutral: "😐",
  negative: "😞",
};

function translateSentiment(label: string, t: TranslateFn) {
  if (label === "positive") return t("Positivo", "Positivo");
  if (label === "neutral") return t("Neutro", "Neutro");
  if (label === "negative") return t("Negativo", "Negativo");
  return label;
}

function isSatisfactoryPitch(label: string | null | undefined): boolean {
  if (!label) return false;
  const normalized = label.toLowerCase();
  return normalized === "satisfactory" || normalized === "satisfatório" || normalized === "satisfatorio";
}

function isConnectedCall(row: PerCallDetail): boolean {
  // Uma chamada é "conectada" quando há diálogo entre agente e cliente
  return row.status_real_detectado === "dialogo_conectado";
}

const DIVERGENCE_REASON_TRANSLATIONS: Record<string, string> = {
  "Agente fala sem resposta do cliente.": "El agente habla sin respuesta del cliente.",
  "Atendimento humano detectado, não sinal de fax.": "Se detectó atención humana, no una señal de fax.",
  "Chamada atendida por pessoas, não por caixa postal.": "La llamada fue atendida por personas, no por buzón de voz.",
  "Chamada ativa mesmo com status de linha suspensa.": "La llamada estuvo activa aunque la línea figure como suspendida.",
  "Chamada conectou com pessoas; número não é inexistente.": "La llamada conectó con personas; el número no es inexistente.",
  "Cliente fala apesar da marcação de suspensão.": "El cliente habla a pesar de la marcación de suspensión.",
  "Existe áudio com diálogo, diferente de 'Sin Audio'.": "Existe audio con diálogo, distinto de 'Sin Audio'.",
  "Fala humana presente; não é contestadora.": "Hay voz humana presente; no es una contestadora.",
  "Há diálogo agente-cliente apesar de IZZI marcar 'No Contesto'.": "Hay diálogo agente-cliente aunque IZZI lo marcó como 'No Contesto'.",
  "Há fala humana mesmo com marcação 'Sin Audio'.": "Hay voz humana aun con la marcación 'Sin Audio'.",
  "Há resposta humana; número existe.": "Hay respuesta humana; el número existe.",
  "Mensagem típica de caixa postal detectada.": "Se detectó un mensaje típico de buzón de voz.",
  "Ouvimos fala humana em vez de caixa postal.": "Se escucha voz humana en lugar de buzón de voz.",
  "Somente IVR sem interação humana.": "Solo IVR sin interacción humana.",
};

function translateReason(reason: string | null | undefined, t: TranslateFn) {
  if (!reason) return reason ?? "";
  const translation = DIVERGENCE_REASON_TRANSLATIONS[reason];
  if (translation) {
    return t(reason, translation);
  }
  return reason;
}

type TranslateFn = (pt: string, es: string) => string;

const formatSeconds = (value: number) => {
  if (!Number.isFinite(value)) return "-";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60)
    .toString()
    .padStart(2, "0");
  const locale = getCurrentLocale();
  const minuteLabel = locale === "es-ES" ? "m" : "m";
  const secondLabel = "s";
  return `${minutes}${minuteLabel}${seconds}${secondLabel}`;
};

function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslate();

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        setLoading(true);
        const base = import.meta.env.BASE_URL ?? "/";
        const jsonUrl = base.endsWith("/") ? `${base}data/full_analysis.json` : `${base}/data/full_analysis.json`;
        const response = await fetch(jsonUrl, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`${t("Falha ao carregar dados", "Error al cargar los datos")} (${response.status})`);
        }
        const payload = (await response.json()) as DashboardData;
        setData(payload);
        setError(null);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(
          (err as Error).message ||
            t("Não foi possível carregar os dados", "No fue posible cargar los datos"),
        );
      } finally {
        setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [t]);

  return { data, loading, error };
}

function loadFilters(): DashboardFilters {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return initialFilters;
    const parsed = JSON.parse(raw) as DashboardFilters;
    return { ...initialFilters, ...parsed };
  } catch (error) {
    console.warn("Falha ao carregar filtros persistidos", error);
    return initialFilters;
  }
}

function saveFilters(filters: DashboardFilters) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
}

function applyFilters(rows: PerCallDetail[], filters: DashboardFilters) {
  const searchTerm = filters.search.trim().toLowerCase();
  return rows.filter((row) => {
    if (searchTerm) {
      const haystack = [
        row.call_id,
        row.script ?? "",
        row.product_offer ?? "",
        row.queue ?? "",
        row.contact_type ?? "",
        row.izzi_status_reportado ?? "",
        row.status_real_detectado,
        row.divergencia_motivo ?? "",
        row.script_alignment_label ?? "",
        row.sales_pitch_label ?? "",
        row.follow_up_actor ?? "",
        row.sales_pitch_topics?.join(" ") ?? "",
        row.script_keywords_matched?.join(" ") ?? "",
        row.operator_source_awareness === 1 ? "source-aware" : "",
        row.customer_anger_detected === 1 ? "cliente-irritado" : "",
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(searchTerm)) return false;
    }

    if (filters.product !== "all" && row.product_offer !== filters.product) return false;
    if (filters.queue !== "all" && row.queue !== filters.queue) return false;
    if (filters.contactType !== "all" && row.contact_type !== filters.contactType) return false;

    if (filters.month !== "all") {
      const callMonth = row.call_datetime?.split(" ")[0]?.split("/")[1];
      if (callMonth !== filters.month) return false;
    }

    if (filters.izziStatus !== "all" && row.izzi_status_normalizado !== filters.izziStatus) return false;
    if (filters.realStatus !== "all" && row.status_real_detectado !== filters.realStatus) return false;

    if (filters.divergence === "divergent" && row.divergente !== 1) return false;
    if (filters.divergence === "matched" && row.divergente === 1) return false;

    if (filters.sentiment !== "all" && row.customer_sentiment_label !== filters.sentiment) return false;
    if (filters.sentimentAgent !== "all" && row.agent_sentiment_label !== filters.sentimentAgent)
      return false;

    if (filters.script !== "all") {
      const label = (row.script_alignment_label ?? "unknown").toLowerCase();
      if (filters.script === "aligned" && label !== "aligned") return false;
      if (filters.script === "partial" && label !== "partial") return false;
      if (filters.script === "off" && label !== "off_script") return false;
      if (filters.script === "unknown" && label !== "unknown") return false;
    }

    if (filters.source !== "all") {
      const level = row.operator_source_awareness_level ?? 0;
      if (filters.source === "detected" && level <= 0) return false;
      if (filters.source === "strong" && level < 2) return false;
      if (filters.source === "undetected" && level > 0) return false;
    }

    if (filters.salesPitch !== "all" && row.sales_pitch_label !== filters.salesPitch) return false;

    if (filters.followUp !== "all") {
      if (filters.followUp === "yes" && row.follow_up_commitment !== 1) return false;
      if (filters.followUp === "no" && row.follow_up_commitment === 1) return false;
      if (filters.followUp === "agent" && row.follow_up_actor !== "agent") return false;
      if (filters.followUp === "customer" && row.follow_up_actor !== "customer") return false;
    }

    if (filters.objection !== "all") {
      if (filters.objection === "yes" && row.objection_handled !== 1) return false;
      if (filters.objection === "no" && row.objection_handled === 1) return false;
    }

    if (filters.anger !== "all") {
      if (filters.anger === "yes" && row.customer_anger_detected !== 1) return false;
      if (filters.anger === "no" && row.customer_anger_detected === 1) return false;
    }

    if (
      row.duration_seconds_transcript < filters.duration[0] ||
      row.duration_seconds_transcript > filters.duration[1]
    )
      return false;

    if (
      row.customer_engagement_score < filters.engagement[0] ||
      row.customer_engagement_score > filters.engagement[1]
    )
      return false;

    if (row.silence_ratio < filters.silence[0] || row.silence_ratio > filters.silence[1]) return false;

    return true;
  });
}

function regressionLine(data: { x: number; y: number }[]) {
  if (data.length === 0) return [] as { x: number; y: number }[];
  const n = data.length;
  const sumX = data.reduce((acc, point) => acc + point.x, 0);
  const sumY = data.reduce((acc, point) => acc + point.y, 0);
  const sumXY = data.reduce((acc, point) => acc + point.x * point.y, 0);
  const sumX2 = data.reduce((acc, point) => acc + point.x * point.x, 0);
  const denominator = n * sumX2 - sumX * sumX;
  const slope = denominator === 0 ? 0 : (n * sumXY - sumX * sumY) / denominator;
  const intercept = (sumY - slope * sumX) / n;
  const sorted = [...data].sort((a, b) => a.x - b.x);
  const firstX = sorted[0]?.x ?? 0;
  const lastX = sorted[sorted.length - 1]?.x ?? firstX;
  return [
    { x: firstX, y: slope * firstX + intercept },
    { x: lastX, y: slope * lastX + intercept },
  ];
}

function buildBins(values: number[], binCount = 10) {
  if (!values.length) return [] as { range: string; count: number }[];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const step = (max - min) / binCount || 1;
  return Array.from({ length: binCount }, (_, index) => {
    const start = min + index * step;
    const end = index === binCount - 1 ? max : start + step;
    const count = values.filter((value) => value >= start && value <= end).length;
    return { range: `${Math.round(start * 100)}-${Math.round(end * 100)}%`, count };
  });
}

function buildInsights(data: DashboardData, t: TranslateFn) {
  const insights: { title: string; description: string; tone: "critical" | "warning" | "info" }[] = [];
  const fallbackQueue = t("Sem fila", "Sin cola asignada");

  const divergenceRate = data.dataset_summary.divergence_rate;
  if (divergenceRate) {
    insights.push({
      title: t("📉 Radar de divergência", "📉 Radar de divergencia"),
      description: t(
        `${formatPercent(divergenceRate, 1)} do legado da Izzi está fora de sintonia (${formatNumber(data.dataset_summary.divergent_calls)} chamadas).`,
        `${formatPercent(divergenceRate, 1)} del legado de Izzi está fuera de sintonía (${formatNumber(data.dataset_summary.divergent_calls)} llamadas).`,
      ),
      tone: divergenceRate > 0.6 ? "critical" : "warning",
    });
  }

  const actualStatuses = Object.entries(data.status_analysis.by_actual_status ?? {});
  if (actualStatuses.length) {
    const [status, stats] = actualStatuses.sort((a, b) => b[1].detected_count - a[1].detected_count)[0];
    insights.push({
      title: t("🧭 Realidade predominante", "🧭 Realidad predominante"),
      description: t(
        `${formatNumber(stats.detected_count)} chamadas (${formatPercent(stats.share)}) terminaram como ${status}.`,
        `${formatNumber(stats.detected_count)} llamadas (${formatPercent(stats.share)}) terminaron como ${status}.`,
      ),
      tone: "info",
    });
  }

  const mainReason = data.divergence_summary.divergence_breakdown?.[0];
  if (mainReason && mainReason.count > 0) {
    insights.push({
      title: t("🎯 Motivo recorrente", "🎯 Motivo recurrente"),
      description: t(
        `${mainReason.count} divergências repetem o padrão "${translateReason(mainReason.reason, t)}".`,
        `${mainReason.count} divergencias repiten el patrón "${translateReason(mainReason.reason, t)}".`,
      ),
      tone: "warning",
    });
  }

  const queueStats = new Map<string, { total: number; divergent: number }>();
  for (const call of data.per_call_details) {
    const key = call.queue ?? fallbackQueue;
    const entry = queueStats.get(key) ?? { total: 0, divergent: 0 };
    entry.total += 1;
    if (call.divergente === 1) entry.divergent += 1;
    queueStats.set(key, entry);
  }
  const queueHotspot = Array.from(queueStats.entries())
    .filter(([, value]) => value.divergent > 0)
    .sort((a, b) => b[1].divergent - a[1].divergent)[0];
  if (queueHotspot) {
    const [queueName, stats] = queueHotspot;
    insights.push({
      title: t("📞 Fila sob observação", "📞 Cola en observación"),
      description: t(
        `${queueName} concentra ${formatNumber(stats.divergent)} divergências (${formatPercent(stats.divergent / data.dataset_summary.divergent_calls)} do total).`,
        `${queueName} concentra ${formatNumber(stats.divergent)} divergencias (${formatPercent(stats.divergent / data.dataset_summary.divergent_calls)} del total).`,
      ),
      tone: "critical",
    });
  }

  const scriptApplicable = Number(data.dataset_summary.script_alignment_applicable ?? 0);
  const scriptAlignedRate = Number(data.dataset_summary.script_alignment_aligned_rate ?? 0);
  if (scriptApplicable > 0) {
    insights.push({
      title: t("🧾 Execução do script", "🧾 Ejecución del guion"),
      description: t(
        `${formatPercent(scriptAlignedRate, 1)} das ${formatNumber(scriptApplicable)} chamadas com script seguiram o roteiro.`,
        `${formatPercent(scriptAlignedRate, 1)} de las ${formatNumber(scriptApplicable)} llamadas con guion siguieron el libreto.`,
      ),
      tone: scriptAlignedRate < 0.55 ? "warning" : "info",
    });
  }

  const followUpRate = Number(data.dataset_summary.follow_up_commitment_rate ?? 0);
  const followUpCalls = Number(data.dataset_summary.follow_up_commitment_calls ?? 0);
  if (followUpCalls > 0) {
    insights.push({
      title: t("📆 Follow-up combinado", "📆 Seguimiento combinado"),
      description: t(
        `${formatPercent(followUpRate, 1)} das chamadas terminam com algum compromisso de retorno (${formatNumber(followUpCalls)} casos).`,
        `${formatPercent(followUpRate, 1)} de las llamadas terminan con algún compromiso de retorno (${formatNumber(followUpCalls)} casos).`,
      ),
      tone: followUpRate < 0.2 ? "warning" : "info",
    });
  }

  const angerRate = Number(data.dataset_summary.customer_anger_rate ?? 0);
  const angerCalls = Number(data.dataset_summary.customer_anger_calls ?? 0);
  if (angerCalls > 0) {
    insights.push({
      title: t("🚨 Clientes irritados", "🚨 Clientes molestos"),
      description: t(
        `${formatNumber(angerCalls)} chamadas trazem pedidos para parar as ligações (${formatPercent(angerRate, 1)} do recorte).`,
        `${formatNumber(angerCalls)} llamadas contienen pedidos de detener las llamadas (${formatPercent(angerRate, 1)} del recorte).`,
      ),
      tone: angerRate >= 0.1 ? "critical" : "warning",
    });
  }

  const hourBuckets = new Map<number, { total: number; divergent: number }>();
  for (const call of data.per_call_details) {
    if (!call.call_datetime) continue;
    const [, time] = call.call_datetime.split(" ");
    if (!time) continue;
    const hour = Number(time.slice(0, 2));
    if (Number.isNaN(hour)) continue;
    const entry = hourBuckets.get(hour) ?? { total: 0, divergent: 0 };
    entry.total += 1;
    if (call.divergente === 1) entry.divergent += 1;
    hourBuckets.set(hour, entry);
  }
  const hourHotspot = Array.from(hourBuckets.entries())
    .filter(([, value]) => value.total >= 5)
    .map(([hour, value]) => ({ hour, rate: value.total ? value.divergent / value.total : 0, total: value.total, divergent: value.divergent }))
    .sort((a, b) => b.rate - a.rate)[0];
  if (hourHotspot && hourHotspot.divergent > 0) {
    insights.push({
      title: t("🕒 Janela crítica", "🕒 Franja crítica"),
      description: t(
        `${hourHotspot.hour.toString().padStart(2, "0")}h apresenta ${formatPercent(hourHotspot.rate)} de divergência (base ${formatNumber(hourHotspot.total)} chamadas).`,
        `${hourHotspot.hour.toString().padStart(2, "0")}h presenta ${formatPercent(hourHotspot.rate)} de divergencia (base ${formatNumber(hourHotspot.total)} llamadas).`,
      ),
      tone: hourHotspot.rate > 0.6 ? "critical" : "warning",
    });
  }

  const agentLanguageCount = data.per_call_details.filter((call) => call.agent_language_detected === 1).length;
  if (agentLanguageCount) {
    insights.push({
      title: t("💬 Linguagem de agente aparente", "💬 Lenguaje de agente aparente"),
      description: t(
        `${formatPercent(agentLanguageCount / data.per_call_details.length)} das ligações exibem vocabulário típico de atendimento, mesmo quando o rótulo original era genérico.`,
        `${formatPercent(agentLanguageCount / data.per_call_details.length)} de las llamadas muestran vocabulario típico de atención, aun cuando la etiqueta original era genérica.`,
      ),
      tone: "info",
    });
  }

  const confusion = data.status_analysis.confusion_matrix ?? [];
  const mismatch = confusion.filter((item) => item.izzi_status !== item.actual_status);
  if (mismatch.length && insights.length < 6) {
    const top = mismatch.sort((a, b) => b.count - a.count)[0];
    const percent = top.count / data.dataset_summary.total_calls;
    insights.push({
      title: t("🔀 Desvio específico", "🔀 Desvío específico"),
      description: t(
        `${top.izzi_status} vira ${top.actual_status} em ${formatPercent(percent)} das chamadas (${formatNumber(top.count)} casos).`,
        `${top.izzi_status} se convierte en ${top.actual_status} en ${formatPercent(percent)} de las llamadas (${formatNumber(top.count)} casos).`,
      ),
      tone: "warning",
    });
  }

  return insights.slice(0, 6);
}

const Card = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div
    className={clsx(
      "relative overflow-hidden rounded-3xl border border-card-border/70 bg-card/80 p-6 shadow-glow backdrop-blur-xl",
      className,
    )}
  >
    <div className="pointer-events-none absolute inset-0 opacity-40" style={{ background: ACCENT_GRADIENT }} />
    <div className="relative z-10 flex flex-col gap-4">{children}</div>
  </div>
);

const Tabs = ({
  options,
  value,
  onChange,
}: {
  options: { key: string; label: string; icon: React.ReactNode }[];
  value: string;
  onChange: (next: string) => void;
}) => (
  <div className="flex flex-wrap gap-2">
    {options.map((option) => {
      const isActive = option.key === value;
      return (
        <button
          key={option.key}
          onClick={() => onChange(option.key)}
          className={clsx(
            "flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition",
            isActive ? "bg-white/90 text-slate-900 shadow-lg" : "text-slate-200 hover:bg-white/10",
          )}
        >
          {option.icon}
          <span className="truncate">{option.label}</span>
        </button>
      );
    })}
  </div>
);

function OverviewTab({
  filtered,
  data,
  insights,
  applyDetection,
}: {
  filtered: PerCallDetail[];
  data: DashboardData;
  insights: ReturnType<typeof buildInsights>;
  applyDetection: () => void;
}) {
  const t = useTranslate();
  const noQueueLabel = t("Sem fila", "Sin cola asignada");
  const divergence = filtered.filter((row) => row.divergente === 1).length;
  const avgDuration = filtered.length
    ? filtered.reduce((acc, row) => acc + row.duration_seconds_transcript, 0) / filtered.length
    : 0;
  const avgEngagement = filtered.length
    ? filtered.reduce((acc, row) => acc + row.customer_engagement_score, 0) / filtered.length
    : 0;
  const talkShareCustomer = filtered.length
    ? filtered.reduce((acc, row) => acc + row.talk_ratio_customer, 0) / filtered.length
    : 0;
  const talkShareAgent = filtered.length
    ? filtered.reduce((acc, row) => acc + row.talk_ratio_agent, 0) / filtered.length
    : 0;
  const talkShareSilence = filtered.length
    ? filtered.reduce((acc, row) => acc + row.silence_ratio, 0) / filtered.length
    : 0;
  const wordsCustomer = filtered.reduce((acc, row) => acc + row.words_customer, 0);
  const wordsAgent = filtered.reduce((acc, row) => acc + row.words_agent, 0);

  // Sales funnel metrics
  const connectedCalls = filtered.filter(isConnectedCall).length;
  const pitchSatisfactory = filtered.filter((row) => isConnectedCall(row) && isSatisfactoryPitch(row.sales_pitch_label)).length;
  const followUpCount = filtered.filter((row) => isConnectedCall(row) && row.follow_up_commitment === 1).length;
  const likelySales = filtered.filter((row) => isConnectedCall(row) && row.likely_sale === 1).length;

  const operatorSummary = useMemo(() => {
    return filtered.reduce(
      (acc, row) => {
        const scriptLabel = row.script_alignment_label ?? "unknown";
        if (row.script_keyword_total > 0) {
          acc.scriptApplicable += 1;
          if (scriptLabel === "aligned") acc.scriptAligned += 1;
          else if (scriptLabel === "partial") acc.scriptPartial += 1;
          else if (scriptLabel === "off_script") acc.scriptOff += 1;
        }
        if (row.operator_source_awareness === 1) {
          acc.sourceAware += 1;
          if ((row.operator_source_awareness_level ?? 0) >= 2) acc.sourceStrong += 1;
        }
        if (row.sales_pitch_label === "satisfactory") acc.salesSatisfactory += 1;
        if (row.sales_pitch_label === "nominal") acc.salesNominal += 1;
        if (row.follow_up_commitment === 1) {
          acc.followUps += 1;
          if (row.follow_up_actor === "agent") acc.followUpByAgent += 1;
          if (row.follow_up_actor === "customer") acc.followUpByCustomer += 1;
        }
        if (row.objection_handled === 1) {
          acc.objectionHandled += 1;
          acc.objectionSequences += row.objection_handled_count ?? 0;
        }
        if (row.customer_anger_detected === 1) {
          acc.angerCalls += 1;
        }
        return acc;
      },
      {
        scriptAligned: 0,
        scriptPartial: 0,
        scriptOff: 0,
        scriptApplicable: 0,
        sourceAware: 0,
        sourceStrong: 0,
        salesSatisfactory: 0,
        salesNominal: 0,
        followUps: 0,
        followUpByAgent: 0,
        followUpByCustomer: 0,
        objectionHandled: 0,
        objectionSequences: 0,
        angerCalls: 0,
      },
    );
  }, [filtered]);
  const totalFiltered = filtered.length;
  const scriptRate = operatorSummary.scriptApplicable
    ? operatorSummary.scriptAligned / operatorSummary.scriptApplicable
    : 0;
  // Source Awareness e Objections devem ser calculados sobre chamadas conectadas
  const sourceRate = connectedCalls ? operatorSummary.sourceAware / connectedCalls : 0;
  const salesRate = connectedCalls ? operatorSummary.salesSatisfactory / connectedCalls : 0;
  const followUpRate = connectedCalls ? operatorSummary.followUps / connectedCalls : 0;
  const objectionRate = connectedCalls ? operatorSummary.objectionHandled / connectedCalls : 0;
  const angerRate = totalFiltered ? operatorSummary.angerCalls / totalFiltered : 0;
  const operatorMetrics = [
    {
      key: "script",
      label: t("Script seguido", "Guion seguido"),
      value: operatorSummary.scriptApplicable ? formatPercent(scriptRate, 0) : "-",
      detail: operatorSummary.scriptApplicable
        ? t(
            `${formatNumber(operatorSummary.scriptAligned)} de ${formatNumber(operatorSummary.scriptApplicable)} chamadas com roteiro aplicado.`,
            `${formatNumber(operatorSummary.scriptAligned)} de ${formatNumber(operatorSummary.scriptApplicable)} llamadas con guion aplicado.`,
          )
        : t("Sem script cadastrado para o recorte atual.", "Sin guion registrado para este recorte."),
      icon: <Target className="h-5 w-5 text-emerald-200" />,
      emphasis: scriptRate >= 0.65 ? "positive" : scriptRate >= 0.4 ? "neutral" : "critical",
    },
    {
      key: "source",
      label: t("Origem reconhecida", "Origen reconocida"),
      value: connectedCalls ? formatPercent(sourceRate, 0) : "-",
      detail:
        operatorSummary.sourceAware === 0
          ? t("Sem menção ao bot ou origem da oportunidade.", "Sin mención al bot ni a la oportunidad.")
          : t(
              `${formatNumber(operatorSummary.sourceAware)} de ${formatNumber(connectedCalls)} chamadas conectadas citaram o bot (${formatNumber(operatorSummary.sourceStrong)} explícitas).`,
              `${formatNumber(operatorSummary.sourceAware)} de ${formatNumber(connectedCalls)} llamadas conectadas citaron el bot (${formatNumber(operatorSummary.sourceStrong)} explícitas).`,
            ),
      icon: <Bot className="h-5 w-5 text-sky-200" />,
      emphasis: sourceRate >= 0.5 ? "positive" : sourceRate >= 0.2 ? "neutral" : "warning",
    },
    {
      key: "sales",
      label: t("Pitch de vendas", "Pitch de ventas"),
      value: connectedCalls ? formatPercent(salesRate, 0) : "-",
      detail:
        operatorSummary.salesSatisfactory + operatorSummary.salesNominal === 0
          ? t("Quase nenhuma menção estruturada de oferta.", "Casi sin mención estructurada de la oferta.")
          : t(
              `${formatNumber(operatorSummary.salesSatisfactory)} de ${formatNumber(connectedCalls)} conectadas: pitches completos (${formatNumber(operatorSummary.salesNominal)} medianos).`,
              `${formatNumber(operatorSummary.salesSatisfactory)} de ${formatNumber(connectedCalls)} conectadas: pitches completos (${formatNumber(operatorSummary.salesNominal)} medianos).`,
            ),
      icon: <Megaphone className="h-5 w-5 text-amber-200" />,
      emphasis: salesRate >= 0.45 ? "positive" : salesRate >= 0.25 ? "neutral" : "warning",
    },
    {
      key: "followup",
      label: t("Follow-up acordado", "Seguimiento acordado"),
      value: connectedCalls ? formatPercent(followUpRate, 0) : "-",
      detail:
        operatorSummary.followUps === 0
          ? t("Nenhuma chamada sinalizou retorno/agendamento.", "Ninguna llamada señaló retorno/agendamiento.")
          : t(
              `${formatNumber(operatorSummary.followUps)} de ${formatNumber(connectedCalls)} conectadas (${formatNumber(operatorSummary.followUpByAgent)} pelo agente, ${formatNumber(operatorSummary.followUpByCustomer)} pelo cliente).`,
              `${formatNumber(operatorSummary.followUps)} de ${formatNumber(connectedCalls)} conectadas (${formatNumber(operatorSummary.followUpByAgent)} por el agente, ${formatNumber(operatorSummary.followUpByCustomer)} por el cliente).`,
            ),
      icon: <CalendarClock className="h-5 w-5 text-cyan-200" />,
      emphasis: followUpRate >= 0.35 ? "positive" : followUpRate >= 0.15 ? "neutral" : "warning",
    },
    {
      key: "objection",
      label: t("Contra-argumentos", "Contraargumentos"),
      value: connectedCalls ? formatPercent(objectionRate, 0) : "-",
      detail:
        operatorSummary.objectionHandled === 0
          ? t("Objeções do cliente ficam sem resposta estruturada.", "Las objeciones del cliente quedan sin respuesta estructurada.")
          : t(
              `${formatNumber(operatorSummary.objectionHandled)} de ${formatNumber(connectedCalls)} conectadas com resposta (${formatNumber(operatorSummary.objectionSequences)} contra-argumentos detectados).`,
              `${formatNumber(operatorSummary.objectionHandled)} de ${formatNumber(connectedCalls)} conectadas con respuesta (${formatNumber(operatorSummary.objectionSequences)} contraargumentos detectados).`,
            ),
      icon: <ShieldCheck className="h-5 w-5 text-emerald-200" />,
      emphasis: objectionRate >= 0.3 ? "positive" : objectionRate >= 0.15 ? "neutral" : "warning",
    },
    {
      key: "anger",
      label: t("Clientes irritados", "Clientes molestos"),
      value: totalFiltered ? formatPercent(angerRate, 0) : "-",
      detail:
        operatorSummary.angerCalls === 0
          ? t("Nenhum pedido para parar as ligações no recorte atual.", "No hay pedidos para detener las llamadas en este recorte.")
          : t(
              `${formatNumber(operatorSummary.angerCalls)} chamadas com pedidos de pausa nas ligações.`,
              `${formatNumber(operatorSummary.angerCalls)} llamadas con pedidos de pausar las llamadas.`,
            ),
      icon: <PhoneOff className="h-5 w-5 text-rose-200" />,
      emphasis: angerRate <= 0.05 ? "positive" : angerRate <= 0.12 ? "neutral" : "critical",
    },
  ] as const;
  const topHours = useMemo(() => {
    const raw = Array.isArray(data.dataset_summary.top_call_hours)
      ? (data.dataset_summary.top_call_hours as (number | string)[][])
      : [];
    return raw
      .map((entry) => {
        const [hour, count] = entry as [number | string, number | string];
        return {
          hour: typeof hour === "number" ? `${hour}h` : `${hour}h`,
          count: Number(count) || 0,
        };
      })
      .filter((item) => Number.isFinite(item.count));
  }, [data]);
  const divergenceByDay = useMemo(() => {
    const map = new Map<string, { total: number; divergent: number }>();
    filtered.forEach((row) => {
      if (!row.call_datetime) return;
      const day = row.call_datetime.split(" ")[0];
      const entry = map.get(day) ?? { total: 0, divergent: 0 };
      entry.total += 1;
      entry.divergent += row.divergente === 1 ? 1 : 0;
      map.set(day, entry);
    });
    return Array.from(map.entries())
      .map(([day, { total, divergent }]) => ({ day, rate: total ? divergent / total : 0, total }))
      .sort((a, b) => new Date(a.day.split("/").reverse().join("-")).getTime() - new Date(b.day.split("/").reverse().join("-")).getTime());
  }, [filtered]);

  const delta = (() => {
    if (divergenceByDay.length < 2) return 0;
    const first = divergenceByDay[0].rate;
    const last = divergenceByDay[divergenceByDay.length - 1].rate;
    return last - first;
  })();

  const grouped = useMemo(() => {
    const map = new Map<string, PerCallDetail[]>();
    filtered.forEach((row) => {
      const key = row.queue ?? noQueueLabel;
      const collection = map.get(key) ?? [];
      collection.push(row);
      map.set(key, collection);
    });
    return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
  }, [filtered, noQueueLabel]);

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Chamadas filtradas", "Llamadas filtradas")}
          </p>
          <div className="flex items-end justify-between">
            <span className="text-4xl font-semibold text-slate-50">{formatNumber(filtered.length)}</span>
            <Sparkles className="h-6 w-6 text-accent-soft" />
          </div>
          <p className="text-sm text-slate-400">
            {t("Linhas considerando filtros aplicados.", "Registros considerando los filtros aplicados.")}
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Taxa de divergência", "Tasa de divergencia")}
          </p>
          <div className="flex items-end justify-between">
            <span className="text-4xl font-semibold text-rose-300">
              {filtered.length === 0 ? "-" : formatPercent(divergence / filtered.length)}
            </span>
            <Flame className="h-6 w-6 text-rose-300/80" />
          </div>
          <p className="text-sm text-slate-400">
            {t(
              `${formatNumber(divergence)} chamadas com divergência ativa.`,
              `${formatNumber(divergence)} llamadas con divergencia activa.`,
            )}
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Duração média", "Duración media")}
          </p>
          <div className="flex items-end justify-between">
            <span className="text-4xl font-semibold text-slate-50">{formatSeconds(avgDuration)}</span>
            <Clock3 className="h-6 w-6 text-accent-soft" />
          </div>
          <p className="text-sm text-slate-400">
            {t("Tempo médio considerando o conjunto filtrado.", "Tiempo medio considerando el conjunto filtrado.")}
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Engajamento médio", "Compromiso medio")}
          </p>
          <div className="flex items-end justify-between">
            <span className="text-4xl font-semibold text-slate-50">{avgEngagement.toFixed(2)}</span>
            <MicVocal className="h-6 w-6 text-cyan-300" />
          </div>
          <p className="text-sm text-slate-400">
            {t(
              `Cliente domina ${formatPercent(talkShareCustomer)} da fala. Silêncio responde por ${formatPercent(talkShareSilence)}.`,
              `El cliente domina ${formatPercent(talkShareCustomer)} del habla. El silencio responde por ${formatPercent(talkShareSilence)}.`,
            )}
          </p>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Funil de Conversão (Proxy de Vendas)", "Embudo de Conversión (Proxy de Ventas)")}
          </h3>
          <TrendingUp className="h-5 w-5 text-green-400" />
        </div>
        <p className="text-xs text-slate-400">
          {t(
            "Funil de vendas: todas as métricas são calculadas sobre as chamadas conectadas (diálogo entre agente e cliente).",
            "Embudo de ventas: todas las métricas se calculan sobre las llamadas conectadas (diálogo entre agente y cliente).",
          )}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
            <p className="text-xs uppercase tracking-wider text-slate-400">{t("Base", "Base")}</p>
            <p className="text-[10px] text-slate-500">{t("Conectadas", "Conectadas")}</p>
            <div className="mt-1 flex items-end justify-between">
              <span className="text-2xl font-semibold text-slate-50">{formatNumber(connectedCalls)}</span>
              <span className="text-sm font-medium text-slate-300">100%</span>
            </div>
          </div>
          <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 px-4 py-3">
            <p className="text-xs uppercase tracking-wider text-cyan-300">{t("Passo 1", "Paso 1")}</p>
            <p className="text-[10px] text-cyan-400/70">{t("Pitch OK", "Pitch OK")}</p>
            <div className="mt-1 flex items-end justify-between">
              <span className="text-2xl font-semibold text-cyan-300">{formatNumber(pitchSatisfactory)}</span>
              <span className="text-sm font-medium text-cyan-300">
                {connectedCalls > 0 ? formatPercent(pitchSatisfactory / connectedCalls) : "0%"}
              </span>
            </div>
          </div>
          <div className="rounded-2xl border border-blue-400/20 bg-blue-400/5 px-4 py-3">
            <p className="text-xs uppercase tracking-wider text-blue-300">{t("Passo 2", "Paso 2")}</p>
            <p className="text-[10px] text-blue-400/70">{t("Follow-up", "Seguimiento")}</p>
            <div className="mt-1 flex items-end justify-between">
              <span className="text-2xl font-semibold text-blue-300">{formatNumber(followUpCount)}</span>
              <span className="text-sm font-medium text-blue-300">
                {connectedCalls > 0 ? formatPercent(followUpCount / connectedCalls) : "0%"}
              </span>
            </div>
          </div>
          <div className="rounded-2xl border border-green-400/30 bg-green-400/10 px-4 py-3">
            <p className="text-xs uppercase tracking-wider text-green-300">{t("Conversão", "Conversión")}</p>
            <p className="text-[10px] text-green-400/70">{t("Pitch + Follow-up", "Pitch + Seguimiento")}</p>
            <div className="mt-1 flex items-end justify-between">
              <span className="text-2xl font-semibold text-green-400">{formatNumber(likelySales)}</span>
              <span className="text-sm font-medium text-green-400">
                {connectedCalls > 0 ? formatPercent(likelySales / connectedCalls) : "0%"}
              </span>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Playbook do operador", "Playbook del operador")}
          </h3>
          <Sparkles className="h-5 w-5 text-accent-soft" />
        </div>
        <p className="text-xs text-slate-400">
          {t(
            "Como os agentes estão lidando com script, origem, pitch, follow-up, objeções e clientes irritados no recorte atual.",
            "Cómo los agentes están gestionando guion, origen, pitch, seguimiento, objeciones y clientes molestos en este recorte.",
          )}
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {operatorMetrics.map((metric) => (
            <div
              key={metric.key}
              className="flex items-start gap-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-3"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-white/10 bg-white/10">
                {metric.icon}
              </div>
              <div className="flex-1">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{metric.label}</p>
                <p
                  className={clsx(
                    "text-xl font-semibold",
                    metric.emphasis === "positive" && "text-emerald-200",
                    metric.emphasis === "neutral" && "text-slate-100",
                    metric.emphasis === "warning" && "text-amber-200",
                    metric.emphasis === "critical" && "text-rose-200",
                  )}
                >
                  {metric.value}
                </p>
                <p className="text-[11px] text-slate-400">{metric.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
              {t("Detecção automática", "Detección automática")}
            </p>
            <h3 className="text-lg font-semibold text-slate-50">
              {t(
                'Filtra instantaneamente chamadas com inconsistências graves (número inexistente falando, "sem áudio" com voz, etc.)',
                'Filtra instantáneamente llamadas con inconsistencias graves (número inexistente hablando, "sin audio" con voz, etc.).',
              )}
            </h3>
          </div>
          <button
            onClick={applyDetection}
            className="flex items-center gap-2 rounded-2xl bg-white/90 px-4 py-2 text-sm font-semibold text-slate-900 shadow-lg transition hover:shadow-xl"
          >
            <AlertTriangle className="h-4 w-4" /> {t("Modo automático", "Modo automático")}
          </button>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Insights inteligentes", "Insights inteligentes")}
          </h3>
          <Sparkles className="h-5 w-5 text-accent-soft" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {insights.map((insight) => (
            <div
              key={insight.title}
              className={clsx(
                "rounded-2xl border px-4 py-5 text-sm shadow-inner backdrop-blur",
                insight.tone === "critical" && "border-rose-500/40 bg-rose-500/10 text-rose-100",
                insight.tone === "warning" && "border-amber-400/40 bg-amber-400/10 text-amber-100",
                insight.tone === "info" && "border-accent-soft/40 bg-accent-soft/10 text-slate-200",
              )}
            >
              <p className="font-semibold">{insight.title}</p>
              <p className="mt-2 text-slate-200/80">{insight.description}</p>
            </div>
          ))}
        </div>
      </Card>

      {topHours.length > 0 && (
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Horários mais movimentados", "Horarios con mayor movimiento")}
            </h3>
            <Hourglass className="h-5 w-5 text-accent-soft" />
          </div>
          <ul className="mt-3 grid gap-3 md:grid-cols-2">
            {topHours.map(({ hour, count }) => (
              <li key={hour} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                <span className="text-slate-100">{hour}</span> —
                {t(
                  ` ${formatNumber(count)} chamadas registradas`,
                  ` ${formatNumber(count)} llamadas registradas`,
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Tabela mestre (agrupado por fila)", "Tabla maestra (agrupada por cola)")}
          </h3>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
            {t("Top 20 por fila", "Top 20 por cola")}
          </p>
        </div>
        <div className="mt-4 space-y-6">
          {grouped.slice(0, 6).map(([queue, rows]) => {
            const divergenceCount = rows.filter((row) => row.divergente === 1).length;
            const silence = rows.reduce((acc, row) => acc + row.silence_ratio, 0) / rows.length;
            const engagement = rows.reduce((acc, row) => acc + row.customer_engagement_score, 0) / rows.length;
            return (
              <div key={queue} className="rounded-3xl border border-white/10 bg-white/5 p-4">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-100">
                      {t("Fila", "Cola")} • {queue}
                    </p>
                    <p className="text-xs text-slate-400">
                      {t(
                        `${formatNumber(rows.length)} chamadas · Divergência ${formatPercent(divergenceCount / rows.length)} · Silêncio médio ${formatPercent(silence)} · Engajamento médio ${engagement.toFixed(2)}`,
                        `${formatNumber(rows.length)} llamadas · Divergencia ${formatPercent(divergenceCount / rows.length)} · Silencio medio ${formatPercent(silence)} · Compromiso medio ${engagement.toFixed(2)}`,
                      )}
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {rows.slice(0, 4).map((row) => (
                    <div
                      key={row.call_id}
                      className={clsx(
                        "rounded-2xl border px-4 py-3 text-xs shadow-inner backdrop-blur",
                        row.divergente === 1
                          ? "border-rose-500/30 bg-rose-500/10 text-rose-100"
                          : "border-emerald-500/20 bg-emerald-500/5 text-emerald-100",
                      )}
                    >
                      <div className="flex justify-between">
                        <span className="font-semibold text-slate-50">{row.call_id}</span>
                        <span>{row.contact_type ?? "-"}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-slate-200/90">
                        <span>
                          {row.divergente === 1
                            ? t("Divergente", "Divergente")
                            : t("Confiável", "Confiable")}
                          · {row.status_real_detectado}
                        </span>
                        <span className="rounded-full bg-black/20 px-2 py-0.5">
                          {SENTIMENT_EMOJI[row.customer_sentiment_label] ?? "😐"} {translateSentiment(row.customer_sentiment_label, t)}
                        </span>
                        <span>
                          {t("Engajamento", "Compromiso")} {row.customer_engagement_score.toFixed(2)}
                        </span>
                        <span>
                          {t("Duração", "Duración")} {formatSeconds(row.duration_seconds_transcript)}
                        </span>
                      </div>
                      <p className="mt-2 text-slate-200/70">
                        {row.divergencia_motivo
                          ? translateReason(row.divergencia_motivo, t)
                          : t("Sem registro de divergência.", "Sin registro de divergencia.")}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Tendência diária de divergência", "Tendencia diaria de divergencia")}
            </h3>
            {delta >= 0 ? (
              <TrendingUp className="h-5 w-5 text-rose-300" />
            ) : (
              <TrendingDown className="h-5 w-5 text-emerald-300" />
            )}
          </div>
          <div className="mt-4 h-60">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={divergenceByDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="day" stroke="rgba(255,255,255,0.4)" />
                <YAxis domain={[0, 1]} stroke="rgba(255,255,255,0.4)" tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                <Tooltip
                  contentStyle={{
                    background: "rgba(8,10,18,0.95)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: "1rem",
                    color: "#f5f6fb",
                  }}
                  formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, t("Divergência", "Divergencia") ]}
                />
                <Line type="monotone" dataKey="rate" stroke="#f87171" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-3 text-xs text-slate-400">
            {delta >= 0
              ? t(
                  `A divergência aumentou ${formatPercent(delta)} desde o início da série.`,
                  `La divergencia aumentó ${formatPercent(delta)} desde el inicio de la serie.`,
                )
              : t(
                  `A divergência reduziu ${formatPercent(Math.abs(delta))} em relação ao primeiro dia registrado.`,
                  `La divergencia se redujo ${formatPercent(Math.abs(delta))} respecto al primer día registrado.`,
                )}
          </p>
        </Card>
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Palavras capturadas", "Palabras capturadas")}
            </h3>
            <MicVocal className="h-5 w-5 text-accent-soft" />
          </div>
          <p className="text-sm text-slate-300">
            {t(
              `Clientes já pronunciaram ${formatNumber(wordsCustomer)} palavras versus ${formatNumber(wordsAgent)} dos agentes nas chamadas filtradas.`,
              `Los clientes ya pronunciaron ${formatNumber(wordsCustomer)} palabras frente a ${formatNumber(wordsAgent)} de los agentes en las llamadas filtradas.`,
            )}
          </p>
          <div className="mt-6 grid gap-3">
            <ProgressLine label={t("Clientes", "Clientes")} value={talkShareCustomer} color="from-[#7dd3fc] to-[#38bdf8]" />
            <ProgressLine label={t("Agentes", "Agentes")} value={talkShareAgent} color="from-[#93c5fd] to-[#6366f1]" />
            <ProgressLine label={t("Silêncio", "Silencio")} value={talkShareSilence} color="from-[#c4b5fd] to-[#a855f7]" />
          </div>
        </Card>
      </div>

      {/* Matriz de Confusão */}
      <ComparativoTab data={data} filtered={filtered} />
    </div>
  );
}

const ProgressLine = ({ label, value, color }: { label: string; value: number; color: string }) => (
  <div>
    <div className="flex justify-between text-xs text-slate-400">
      <span>{label}</span>
      <span>{formatPercent(value || 0)}</span>
    </div>
    <div className="mt-2 h-2 rounded-full bg-white/10">
      <div
        className="h-full rounded-full"
        style={{
          width: `${Math.min(100, Math.max(0, (value || 0) * 100))}%`,
          backgroundImage: `linear-gradient(90deg, ${color})`,
        }}
      />
    </div>
  </div>
);

function ComparativoTab({ data, filtered }: { data: DashboardData; filtered: PerCallDetail[] }) {
  const t = useTranslate();
  const [selectedCell, setSelectedCell] = useState<{ izzi: string; real: string } | null>(null);

  const matrix = useMemo(() => {
    // Usar TODA a matriz de confusão (incluindo acertos e divergências)
    const allData = data.status_analysis.confusion_matrix;

    // Pegar todos os status únicos
    const statusesIzzi = Array.from(
      new Set(allData.map((item) => item.izzi_status)),
    ).sort();
    const statusesReal = Array.from(
      new Set(allData.map((item) => item.actual_status)),
    ).sort();

    // Criar grid completo
    const grid: Record<string, Record<string, number>> = {};
    statusesIzzi.forEach((izzi) => {
      grid[izzi] = {};
      statusesReal.forEach((real) => {
        grid[izzi][real] = 0;
      });
    });

    // Preencher com os dados
    allData.forEach((item) => {
      if (!grid[item.izzi_status]) grid[item.izzi_status] = {} as Record<string, number>;
      grid[item.izzi_status][item.actual_status] = item.count;
    });

    return { grid, statusesIzzi, statusesReal };
  }, [data]);

  const maxCell = useMemo(() => {
    return Math.max(
      ...data.status_analysis.confusion_matrix.map((item) => item.count),
      1,
    );
  }, [data]);

  const worst = useMemo(() => {
    return data.status_analysis.confusion_matrix
      .filter((item) => item.izzi_status !== item.actual_status)
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }, [data]);

  const detections = useMemo(() => {
    const map = new Map<string, number>();
    filtered.forEach((row) => {
      const key = `${row.izzi_status_normalizado}→${row.status_real_detectado}`;
      map.set(key, (map.get(key) ?? 0) + 1);
    });
    return Array.from(map.entries())
      .map(([pair, count]) => ({ pair, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
  }, [filtered]);

  const cellCalls = useMemo(() => {
    if (!selectedCell) return [];
    return filtered.filter(
      call => call.izzi_status_normalizado === selectedCell.izzi &&
              call.status_real_detectado === selectedCell.real
    );
  }, [filtered, selectedCell]);

  return (
    <div className="space-y-8">
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Matriz de Confusão: IZZI × Realidade", "Matriz de Confusión: IZZI × Realidad")}
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              {t("Verde = acertos na diagonal | Vermelho = erros de classificação | Clique para detalhes", "Verde = aciertos en la diagonal | Rojo = errores de clasificación | Clic para detalles")}
            </p>
          </div>
          <button
            onClick={() => {
              const csv = [
                ["IZZI Status", "Real Status", "Count", "Percentage"],
                ...data.status_analysis.confusion_matrix.map(row => [
                  row.izzi_status,
                  row.actual_status,
                  row.count,
                  ((row.count / data.dataset_summary.total_calls) * 100).toFixed(2) + "%"
                ])
              ].map(row => row.join(",")).join("\n");
              const blob = new Blob([csv], { type: "text/csv" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "confusion_matrix.csv";
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="flex items-center gap-2 rounded-2xl border border-accent-soft/30 bg-accent-soft/10 px-4 py-2 text-sm text-accent-soft hover:bg-accent-soft/20"
          >
            <Download className="h-4 w-4" />
            {t("Exportar CSV", "Exportar CSV")}
          </button>
        </div>
        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-2 text-sm">
            <thead>
              <tr>
                <th className="rounded-2xl bg-white/5 px-4 py-2 text-left text-xs uppercase tracking-[0.3em] text-slate-400">
                  {t("IZZI → Real", "IZZI → Real")}
                </th>
                {matrix.statusesReal.map((status) => (
                  <th
                    key={status}
                    className="rounded-2xl bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.25em] text-slate-300"
                  >
                    {status}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.statusesIzzi.map((izzi) => (
                <tr key={izzi}>
                  <td className="rounded-2xl bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-300">
                    {izzi}
                  </td>
                  {matrix.statusesReal.map((real) => {
                    const value = matrix.grid[izzi]?.[real] ?? 0;
                    const isCorrect = izzi === real; // Diagonal = acertos
                    const intensity = value / maxCell;

                    // Cores diferentes para acertos (verde) vs erros (vermelho/laranja)
                    let background: string;
                    if (value === 0) {
                      background = "rgba(12,16,24,0.4)";
                    } else if (isCorrect) {
                      // Diagonal: verde (acertos)
                      background = `linear-gradient(135deg, rgba(34,197,94,${intensity * 0.8}), rgba(22,163,74,${intensity * 0.6}))`;
                    } else {
                      // Fora da diagonal: vermelho/laranja (erros)
                      background = `linear-gradient(135deg, rgba(239,68,68,${intensity * 0.8}), rgba(220,38,38,${intensity * 0.6}))`;
                    }

                    return (
                      <td key={real} className="rounded-2xl text-center text-xs text-slate-50">
                        <button
                          onClick={() => value > 0 && setSelectedCell({ izzi, real })}
                          disabled={value === 0}
                          className={`group relative flex w-full flex-col items-center justify-center rounded-2xl px-4 py-4 ${
                            value > 0 ? "cursor-pointer transition-all hover:scale-105 hover:shadow-xl" : "cursor-default"
                          } ${isCorrect && value > 0 ? "ring-2 ring-green-400/30" : ""}`}
                          style={{ background, minWidth: "80px", minHeight: "80px" }}
                        >
                          <span className={`text-lg font-bold drop-shadow-[0_2px_6px_rgba(0,0,0,0.9)] ${
                            isCorrect ? "text-green-50" : "text-rose-50"
                          }`}>
                            {formatNumber(value)}
                          </span>
                          <span className={`mt-1 text-[10px] font-semibold uppercase tracking-wider drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] ${
                            isCorrect ? "text-green-100" : "text-rose-100"
                          }`}>
                            {formatPercent(value / data.dataset_summary.total_calls)}
                          </span>
                          {isCorrect && value > 0 && (
                            <div className="absolute top-1 right-1">
                              <div className="h-2 w-2 rounded-full bg-green-400 shadow-lg shadow-green-400/50" />
                            </div>
                          )}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Top erros de classificação", "Principales errores de clasificación")}
            </h3>
            <AlertTriangle className="h-5 w-5 text-rose-300" />
          </div>
          <ul className="mt-3 space-y-3 text-sm text-slate-200/80">
            {worst.map((item) => (
              <li key={`${item.izzi_status}-${item.actual_status}`} className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-rose-100">
                    {item.izzi_status} → {item.actual_status}
                  </span>
                  <span>{t(`${formatNumber(item.count)} casos`, `${formatNumber(item.count)} casos`)}</span>
                </div>
                <p className="mt-1 text-xs text-rose-100/70">
                  {t(
                    `${formatPercent(item.count / data.dataset_summary.total_calls)} do dataset completo.`,
                    `${formatPercent(item.count / data.dataset_summary.total_calls)} del dataset completo.`,
                  )}
                </p>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Pares destacados no filtro atual", "Pares destacados en el filtro actual")}
            </h3>
            <Target className="h-5 w-5 text-accent-soft" />
          </div>
          <ul className="mt-3 space-y-3 text-sm text-slate-200/80">
            {detections.map((item) => (
              <li key={item.pair} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <span className="font-semibold text-slate-100">{item.pair}</span>
                <span className="ml-2 text-xs text-slate-400">
                  {t(`${formatNumber(item.count)} chamadas`, `${formatNumber(item.count)} llamadas`)}
                </span>
              </li>
            ))}
            {detections.length === 0 && (
              <li className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-400">
                {t("Sem registros para os filtros atuais.", "Sin registros para los filtros actuales.")}
              </li>
            )}
          </ul>
        </Card>
      </div>

      {/* Modal de chamadas da célula */}
      <AnimatePresence>
        {selectedCell && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
            onClick={() => setSelectedCell(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-950 p-8 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setSelectedCell(null)}
                className="absolute right-6 top-6 text-slate-400 hover:text-slate-200"
              >
                <X className="h-6 w-6" />
              </button>

              <div className="mb-6">
                <h2 className="text-2xl font-semibold text-slate-50">
                  {t("Chamadas nesta célula", "Llamadas en esta celda")}
                </h2>
                <p className="mt-2 text-sm text-slate-400">
                  <span className="font-semibold text-cyan-400">{selectedCell.izzi}</span>
                  {" → "}
                  <span className="font-semibold text-blue-400">{selectedCell.real}</span>
                  {" • "}
                  {cellCalls.length} {t("chamadas", "llamadas")}
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-slate-400">
                      <th className="pb-3">{t("ID", "ID")}</th>
                      <th className="pb-3">{t("Data", "Fecha")}</th>
                      <th className="pb-3">{t("Duração", "Duración")}</th>
                      <th className="pb-3">{t("Agente", "Agente")}</th>
                      <th className="pb-3">{t("Status IZZI", "Estado IZZI")}</th>
                      <th className="pb-3">{t("Status Real", "Estado Real")}</th>
                      <th className="pb-3">{t("Motivo", "Motivo")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cellCalls.map((call) => (
                      <tr key={call.call_id} className="border-b border-white/5 hover:bg-white/5">
                        <td className="py-3 font-mono text-xs text-slate-300">{call.call_id.slice(0, 8)}</td>
                        <td className="py-3 text-slate-300">{call.call_datetime?.split(" ")[0]}</td>
                        <td className="py-3 text-slate-300">{Math.floor(call.duration_seconds_transcript)}s</td>
                        <td className="py-3 text-slate-300">{call.agent_name_detected || "-"}</td>
                        <td className="py-3 text-cyan-300">{call.izzi_status_normalizado}</td>
                        <td className="py-3 text-blue-300">{call.status_real_detectado}</td>
                        <td className="py-3 text-slate-400">{call.divergencia_motivo || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => {
                    const csv = [
                      ["Call ID", "Date", "Duration", "Agent", "IZZI Status", "Real Status", "Reason"],
                      ...cellCalls.map(call => [
                        call.call_id,
                        call.call_datetime || "",
                        call.duration_seconds_transcript,
                        call.agent_name_detected || "",
                        call.izzi_status_normalizado,
                        call.status_real_detectado,
                        call.divergencia_motivo || ""
                      ])
                    ].map(row => row.join(",")).join("\n");
                    const blob = new Blob([csv], { type: "text/csv" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `calls_${selectedCell.izzi}_${selectedCell.real}.csv`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="flex items-center gap-2 rounded-2xl border border-accent-soft/30 bg-accent-soft/10 px-4 py-2 text-sm text-accent-soft hover:bg-accent-soft/20"
                >
                  <Download className="h-4 w-4" />
                  {t("Exportar CSV", "Exportar CSV")}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function CorrelacoesTab({ filtered, controls }: {
  filtered: PerCallDetail[];
  controls: {
    product: string;
    setProduct: (value: string) => void;
    productOptions: string[];
    queue: string;
    setQueue: (value: string) => void;
    queueOptions: string[];
    contact: string;
    setContact: (value: string) => void;
    contactOptions: string[];
  };
}) {
  const t = useTranslate();
  const byFilters = filtered.filter((row) => {
    if (controls.product !== "all" && row.product_offer !== controls.product) return false;
    if (controls.queue !== "all" && row.queue !== controls.queue) return false;
    if (controls.contact !== "all" && row.contact_type !== controls.contact) return false;
    return true;
  });

  const silenceData = byFilters.map((row) => ({ x: row.silence_ratio * 100, y: row.divergente === 1 ? 100 : 0 }));
  const silenceRegression = regressionLine(silenceData.map((item) => ({ x: item.x, y: item.y })));

  const talkCustomer = byFilters.map((row) => ({
    x: row.talk_ratio_customer * 100,
    y: row.divergente === 1 ? 100 : 0,
    status: row.izzi_status_normalizado,
  }));

  const durationData = byFilters.map((row) => ({
    x: row.duration_seconds_transcript,
    y: row.divergente === 1 ? 100 : 0,
    status: row.status_real_detectado,
  }));

  const sentimentData = byFilters.map((row) => ({
    sentiment: row.customer_sentiment_label,
    divergent: row.divergente,
  }));

  const snrData = byFilters.map((row) => ({
    x: (1 - row.silence_ratio) * 100,
    y: row.divergente === 1 ? 100 : 0,
  }));
  const snrRegression = regressionLine(snrData);

  const sentimentDistribution = useMemo(() => {
    const map = new Map<string, { divergent: number; total: number }>();
    sentimentData.forEach((item) => {
      const bucket = map.get(item.sentiment) ?? { divergent: 0, total: 0 };
      bucket.total += 1;
      bucket.divergent += item.divergent;
      map.set(item.sentiment, bucket);
    });
    return Array.from(map.entries()).map(([sentiment, { divergent, total }]) => ({
      sentiment,
      rate: total ? divergent / total : 0,
      total,
    }));
  }, [sentimentData]);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <SelectionCard
          label={t("Produto", "Producto")}
          value={controls.product}
          options={controls.productOptions}
          onChange={controls.setProduct}
        />
        <SelectionCard
          label={t("Fila", "Cola")}
          value={controls.queue}
          options={controls.queueOptions}
          onChange={controls.setQueue}
        />
        <SelectionCard
          label={t("Tipo de Contato", "Tipo de contacto")}
          value={controls.contact}
          options={controls.contactOptions}
          onChange={controls.setContact}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Silêncio × Divergência", "Silencio × Divergencia")}
            </h3>
            <CloudMoon className="h-5 w-5 text-accent-soft" />
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid stroke="rgba(255,255,255,0.1)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={t("Silêncio", "Silencio")}
                  unit="%"
                  stroke="rgba(255,255,255,0.4)"
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name={t("Divergência", "Divergencia")}
                  unit="%"
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  formatter={(value: number) => `${value.toFixed(1)}%`}
                  labelFormatter={(label) => `${t("Silêncio", "Silencio")} ${label.toFixed(1)}%`}
                  contentStyle={{
                    background: "rgba(8,10,18,0.95)",
                    borderRadius: "1rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "#f5f6fb",
                  }}
                />
                <Scatter data={silenceData} fill="#f97316" />
                {silenceRegression.length === 2 && (
                  <Line type="monotone" dataKey="y" data={silenceRegression} stroke="#f97316" strokeDasharray="4 2" dot={false} />
                )}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Relação fala do cliente × divergência", "Relación habla del cliente × divergencia")}
            </h3>
            <ChartLine className="h-5 w-5 text-accent-soft" />
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid stroke="rgba(255,255,255,0.1)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={t("Cliente", "Cliente")}
                  unit="%"
                  stroke="rgba(255,255,255,0.4)"
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name={t("Divergência", "Divergencia")}
                  unit="%"
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip
                  formatter={(value: number, _name, payload) => [
                    `${value.toFixed(0)}%`,
                    (payload?.payload as { status?: string })?.status ?? "IZZI",
                  ]}
                  labelFormatter={(label) => `${t("Cliente", "Cliente")} ${label.toFixed(0)}%`}
                  contentStyle={{
                    background: "rgba(8,10,18,0.95)",
                    borderRadius: "1rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "#f5f6fb",
                  }}
                />
                <Scatter data={talkCustomer} fill="#38bdf8" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Duração × Status Real", "Duración × Estado Real")}
            </h3>
            <Radio className="h-5 w-5 text-accent-soft" />
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid stroke="rgba(255,255,255,0.1)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={t("Duração", "Duración")}
                  unit="s"
                  stroke="rgba(255,255,255,0.4)"
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name={t("Divergência", "Divergencia")}
                  unit="%"
                  domain={[0, 100]}
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip
                  formatter={(value: number, _name, payload) => [
                    `${value.toFixed(0)}%`,
                    (payload?.payload as { status?: string })?.status ?? t("Status", "Estado"),
                  ]}
                  labelFormatter={(label) => `${label.toFixed(0)}s`}
                  contentStyle={{
                    background: "rgba(8,10,18,0.95)",
                    borderRadius: "1rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "#f5f6fb",
                  }}
                />
                <Scatter data={durationData} fill="#a855f7" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Sentimento do cliente × Divergência", "Sentimiento del cliente × Divergencia")}
            </h3>
            <MicVocal className="h-5 w-5 text-accent-soft" />
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sentimentDistribution}>
                <CartesianGrid stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="sentiment" stroke="rgba(255,255,255,0.4)" />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(value) => `${Math.round(value * 100)}%`}
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip
                  formatter={(value: number, _name, payload) => [
                    `${(value * 100).toFixed(1)}%`,
                    `${(payload?.payload as { total: number })?.total ?? 0} ${t("chamadas", "llamadas")}`,
                  ]}
                  contentStyle={{
                    background: "rgba(8,10,18,0.95)",
                    borderRadius: "1rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "#f5f6fb",
                  }}
                />
                <Bar dataKey="rate" radius={[12, 12, 0, 0]}>
                  {sentimentDistribution.map((item) => (
                    <Cell key={item.sentiment} fill={SENTIMENT_COLOR[item.sentiment] ?? "#94a3b8"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="xl:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Correlação SNR (proxy) × Divergência", "Correlación SNR (proxy) × Divergencia")}
            </h3>
            <ChartLine className="h-5 w-5 text-accent-soft" />
          </div>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid stroke="rgba(255,255,255,0.1)" />
                <XAxis
                  type="number"
                  dataKey="x"
                  name={`${t("SNR", "SNR")} (1 - ${t("silêncio", "silencio")})`}
                  unit="%"
                  stroke="rgba(255,255,255,0.4)"
                />
                <YAxis
                  type="number"
                  dataKey="y"
                  name={t("Divergência", "Divergencia")}
                  unit="%"
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip
                  formatter={(value: number) => `${value.toFixed(1)}%`}
                  labelFormatter={(label) => `SNR ${label.toFixed(1)}%`}
                  contentStyle={{
                    background: "rgba(8,10,18,0.95)",
                    borderRadius: "1rem",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "#f5f6fb",
                  }}
                />
                <Scatter data={snrData} fill="#10b981" />
                {snrRegression.length === 2 && (
                  <Line type="monotone" dataKey="y" data={snrRegression} stroke="#10b981" strokeDasharray="4 2" dot={false} />
                )}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}

const SelectionCard = ({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) => {
  const t = useTranslate();

  return (
    <Card>
      <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{label}</p>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
      >
        <option value="all">{t("Todos", "Todos")}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </Card>
  );
};

function TemporalTab({ filtered, globalRate }: { filtered: PerCallDetail[]; globalRate: number }) {
  const [from, setFrom] = useState<string>("");
  const [to, setTo] = useState<string>("");
  const t = useTranslate();

  const data = useMemo(() => {
    const map = new Map<string, { total: number; divergent: number }>();
    filtered.forEach((row) => {
      if (!row.call_datetime) return;
      const [day, time] = row.call_datetime.split(" ");
      if (!time) return;
      const iso = day.split("/").reverse().join("-");
      if (from && iso < from) return;
      if (to && iso > to) return;
      const hour = time.slice(0, 2);
      const key = `${iso} ${hour}`;
      const entry = map.get(key) ?? { total: 0, divergent: 0 };
      entry.total += 1;
      entry.divergent += row.divergente === 1 ? 1 : 0;
      map.set(key, entry);
    });
    return Array.from(map.entries())
      .map(([key, { total, divergent }]) => {
        const [date, hour] = key.split(" ");
        const label = `${hour}h`;
        return {
          date,
          hour: label,
          calls: total,
          divergence: total ? divergent / total : 0,
          tooltip: `${hour}h (${date.split("-").reverse().join("/")})`,
        };
      })
      .sort((a, b) => {
        const timeA = new Date(`${a.date}T${a.hour.replace("h", "")}:00:00`).getTime();
        const timeB = new Date(`${b.date}T${b.hour.replace("h", "")}:00:00`).getTime();
        return timeA - timeB;
      });
  }, [filtered, from, to]);

  const criticalHours = data.filter((item) => item.divergence > globalRate);

  return (
    <div className="space-y-6">
      <Card>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{t("De", "Desde")}</p>
            <input
              type="date"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{t("Até", "Hasta")}</p>
            <input
              type="date"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
            />
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t(
              "Pulso horário com destaque de divergências críticas",
              "Pulso horario con destaque de divergencias críticas",
            )}
          </h3>
          <Clock3 className="h-5 w-5 text-accent-soft" />
        </div>
        <div className="mt-6 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="callsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#84b7ff" stopOpacity={0.8} />
                  <stop offset="100%" stopColor="#84b7ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="hour" stroke="rgba(255,255,255,0.4)" />
              <YAxis yAxisId="left" stroke="rgba(255,255,255,0.4)" allowDecimals={false} />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="rgba(239,68,68,0.6)"
                domain={[0, 1]}
                tickFormatter={(value) => `${Math.round(value * 100)}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(8,10,18,0.95)",
                  borderRadius: "1rem",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "#f5f6fb",
                }}
                formatter={(value: number, name) => {
                  if (name === "divergence") {
                    return [`${(value * 100).toFixed(1)}%`, t("Divergência", "Divergencia")];
                  }
                  return [`${value}`, t("Chamadas", "Llamadas")];
                }}
                labelFormatter={(label, payload) => {
                  const item = payload?.[0]?.payload as (typeof data)[number] | undefined;
                  return item ? `${item.tooltip}` : label;
                }}
              />
              <Area yAxisId="left" type="monotone" dataKey="calls" stroke="#84b7ff" fill="url(#callsGradient)" strokeWidth={2.5} />
              <Line yAxisId="right" type="monotone" dataKey="divergence" stroke="#fb7185" strokeWidth={2.5} dot={{ r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-4 text-xs text-slate-300">
          {criticalHours.length > 0
            ? t(
                `${criticalHours.length} horários apresentaram divergência acima da média global (${formatPercent(globalRate)}).`,
                `${criticalHours.length} horarios presentaron divergencia por encima del promedio global (${formatPercent(globalRate)}).`,
              )
            : t("Nenhum horário ultrapassou a média global de divergência.", "Ningún horario superó el promedio global de divergencia.")}
        </p>
      </Card>
    </div>
  );
}

function PrecisaoTab({ filtered }: { filtered: PerCallDetail[] }) {
  const silenceValues = filtered.map((row) => row.silence_ratio);
  const histogram = buildBins(silenceValues, 10);
  const noisy = [...filtered]
    .sort((a, b) => b.silence_ratio - a.silence_ratio)
    .slice(0, 10);
  const snrData = filtered.map((row) => ({
    x: (1 - row.silence_ratio) * 100,
    y: row.divergente === 1 ? 100 : 0,
    id: row.call_id,
  }));
  const regression = regressionLine(snrData);
  const t = useTranslate();

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Distribuição de silêncio (%)", "Distribución de silencio (%)")}
          </h3>
          <CloudMoon className="h-5 w-5 text-accent-soft" />
        </div>
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={histogram}>
              <CartesianGrid stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="range" stroke="rgba(255,255,255,0.4)" />
              <YAxis allowDecimals={false} stroke="rgba(255,255,255,0.4)" />
              <Tooltip
                contentStyle={{
                  background: "rgba(8,10,18,0.95)",
                  borderRadius: "1rem",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "#f5f6fb",
                }}
              />
              <Bar dataKey="count" radius={[12, 12, 0, 0]} fill="#38bdf8" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Top 10 chamadas com maior ruído (silêncio)", "Top 10 llamadas con mayor ruido (silencio)")}
          </h3>
          <Flame className="h-5 w-5 text-rose-300" />
        </div>
        <ul className="mt-3 space-y-3 text-sm text-slate-200/90">
          {noisy.map((row) => (
            <li key={row.call_id} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-100">{row.call_id}</span>
                <span>{formatPercent(row.silence_ratio)}</span>
              </div>
              <p className="text-xs text-slate-400">
                {row.izzi_status_normalizado} → {row.status_real_detectado} · {row.queue ?? t("Sem fila", "Sin cola asignada")}
              </p>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-50">
            {t("Correlação SNR (proxy) × Divergência", "Correlación SNR (proxy) × Divergencia")}
          </h3>
          <ChartLine className="h-5 w-5 text-accent-soft" />
        </div>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid stroke="rgba(255,255,255,0.08)" />
              <XAxis
                type="number"
                dataKey="x"
                name={`${t("SNR", "SNR")} (1 - ${t("silêncio", "silencio")})`}
                unit="%"
                stroke="rgba(255,255,255,0.4)"
              />
              <YAxis
                type="number"
                dataKey="y"
                name={t("Divergência", "Divergencia")}
                unit="%"
                stroke="rgba(255,255,255,0.4)"
              />
              <Tooltip
                formatter={(value: number, _name, payload) => [
                  `${value.toFixed(1)}%`,
                  (payload?.payload as { id: string })?.id ?? "",
                ]}
                labelFormatter={(label) => `SNR ${label.toFixed(1)}%`}
                contentStyle={{
                  background: "rgba(8,10,18,0.95)",
                  borderRadius: "1rem",
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "#f5f6fb",
                }}
              />
              <Scatter data={snrData} fill="#34d399" />
              {regression.length === 2 && (
                <Line type="monotone" dataKey="y" data={regression} stroke="#34d399" strokeDasharray="4 2" dot={false} />
              )}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

function AudioLibraryTab({
  rows,
  page,
  search,
  onSearchChange,
  onPageChange,
  onDownloadReport,
  onDownloadMetrics,
  downloadDisabled,
}: {
  rows: PerCallDetail[];
  page: number;
  search: string;
  onSearchChange: (value: string) => void;
  onPageChange: (next: number) => void;
  onDownloadReport: () => void;
  onDownloadMetrics: () => void;
  downloadDisabled: boolean;
}) {
  const pageSize = 12;
  const query = search.trim().toLowerCase();
  const t = useTranslate();
  const parseRange = (value: string) => {
    const [minStr, maxStr] = value.split("-", 2);
    const min = minStr ? Number(minStr) : Number.NEGATIVE_INFINITY;
    const max = maxStr ? Number(maxStr) : Number.POSITIVE_INFINITY;
    return {
      min: Number.isFinite(min) ? min : Number.NEGATIVE_INFINITY,
      max: Number.isFinite(max) ? max : Number.POSITIVE_INFINITY,
    };
  };

  const parsedTokens = useMemo(() => {
    if (!query) return { filters: [] as { key: string; value: string }[], terms: [] as string[] };
    const tokens = query.split(/\s+/).filter(Boolean);
    const filters = tokens
      .filter((token) => token.includes(":"))
      .map((token) => {
        const [rawKey, rawValue = ""] = token.split(":", 2);
        return { key: rawKey.toLowerCase(), value: rawValue.toLowerCase() };
      });
    const terms = tokens.filter((token) => !token.includes(":"));
    return { filters, terms };
  }, [query]);

  const searchedRows = useMemo(() => {
    const { filters, terms } = parsedTokens;
    if (filters.length === 0 && terms.length === 0) return rows;

    return rows.filter((row) => {
      if (terms.length) {
        const haystack = [
          row.call_id,
          row.product_offer ?? "",
          row.queue ?? "",
          row.contact_type ?? "",
          row.izzi_status_reportado ?? "",
          row.izzi_status_normalizado,
          row.status_real_detectado,
          row.divergencia_motivo ?? "",
          row.script_alignment_label ?? "",
          row.sales_pitch_label ?? "",
          row.sales_pitch_topics?.join(" ") ?? "",
          row.script_keywords_matched?.join(" ") ?? "",
          row.follow_up_actor ?? "",
          row.follow_up_commitment === 1 ? "followup" : "",
          row.operator_source_awareness === 1 ? "source-aware" : "",
          row.operator_source_awareness_level >= 2 ? "source-strong" : "",
          row.customer_anger_detected === 1 ? "cliente-irritado" : "",
        ]
          .join(" ")
          .toLowerCase();
        if (!terms.every((term) => haystack.includes(term))) return false;
      }

      for (const { key, value } of filters) {
        switch (key) {
          case "status":
          case "status_izzi":
            if (row.izzi_status_normalizado !== value) return false;
            break;
          case "real":
          case "status_real":
            if (row.status_real_detectado !== value) return false;
            break;
          case "sentimento":
          case "sentiment":
            if (row.customer_sentiment_label !== value) return false;
            break;
          case "sentimento_agente":
          case "agent":
            if (row.agent_sentiment_label !== value) return false;
            break;
          case "fila":
          case "queue":
            if ((row.queue ?? "").toLowerCase() !== value) return false;
            break;
          case "produto":
          case "product":
            if ((row.product_offer ?? "").toLowerCase() !== value) return false;
            break;
          case "contato":
          case "contact":
            if ((row.contact_type ?? "").toLowerCase() !== value) return false;
            break;
          case "divergente":
          case "divergence": {
            const positive = ["sim", "yes", "true", "1", "si", "sí"];
            const negative = ["nao", "não", "no", "false", "0"];
            if (positive.includes(value) && row.divergente !== 1) return false;
            if (negative.includes(value) && row.divergente === 1) return false;
            break;
          }
          case "duracao":
          case "duration": {
            const { min, max } = parseRange(value);
            const measured = row.duration_seconds_transcript;
            if (measured < min || measured > max) return false;
            break;
          }
          case "engajamento":
          case "engagement": {
            const { min, max } = parseRange(value);
            const measured = row.customer_engagement_score;
            if (measured < min || measured > max) return false;
            break;
          }
          case "silencio":
          case "silence": {
            const { min, max } = parseRange(value);
            const measured = row.silence_ratio;
            if (measured < min || measured > max) return false;
            break;
          }
          case "palavras":
          case "words": {
            const { min, max } = parseRange(value);
            const measured = row.words_customer + row.words_agent;
            if (measured < min || measured > max) return false;
            break;
          }
          case "motivo":
          case "reason":
            if (!(row.divergencia_motivo ?? "").toLowerCase().includes(value)) return false;
            break;
          case "script":
          case "script_alignment": {
            const label = (row.script_alignment_label ?? "unknown").toLowerCase();
            if (["aligned", "alinhado"].includes(value) && label !== "aligned") return false;
            if (["partial", "parcial"].includes(value) && label !== "partial") return false;
            if (["off", "fora", "desalinhado"].includes(value) && label !== "off_script") return false;
            if (["unknown", "indefinido", "sem"].includes(value) && label !== "unknown") return false;
            break;
          }
          case "origem":
          case "source":
          case "source_awareness": {
            const level = row.operator_source_awareness_level ?? 0;
            if (["sim", "yes", "detected"].includes(value) && level <= 0) return false;
            if (["forte", "strong", "bot"].includes(value) && level < 2) return false;
            if (["nao", "não", "no", "undetected"].includes(value) && level > 0) return false;
            break;
          }
          case "pitch":
          case "sales":
          case "vendas": {
            if (["satisfatorio", "satisfatória", "satisfactoria", "satisfactory"].includes(value) && row.sales_pitch_label !== "satisfactory") return false;
            if (["nominal", "parcial"].includes(value) && row.sales_pitch_label !== "nominal") return false;
            if (["fraco", "weak"].includes(value) && row.sales_pitch_label !== "weak") return false;
            break;
          }
          case "followup":
          case "follow_up":
          case "retorno": {
            if (["sim", "yes", "true", "1", "si", "sí"].includes(value) && row.follow_up_commitment !== 1)
              return false;
            if (["nao", "não", "no", "false", "0"].includes(value) && row.follow_up_commitment === 1) return false;
            if (["agente", "agent"].includes(value) && row.follow_up_actor !== "agent") return false;
            if (["cliente", "customer"].includes(value) && row.follow_up_actor !== "customer") return false;
            break;
          }
          case "obje":
          case "objection":
          case "objeção":
          case "objecao": {
            if (["sim", "yes", "true", "1", "si", "sí"].includes(value) && row.objection_handled !== 1) return false;
            if (["nao", "não", "no", "false", "0"].includes(value) && row.objection_handled === 1) return false;
            break;
          }
          case "anger":
          case "irritado":
          case "irritado_cliente": {
            if (["sim", "yes", "true", "1", "si", "sí"].includes(value) && row.customer_anger_detected !== 1)
              return false;
            if (["nao", "não", "no", "false", "0"].includes(value) && row.customer_anger_detected === 1) return false;
            break;
          }
          default:
            // ignore unknown filters
            break;
        }
      }

      return true;
    });
  }, [rows, parsedTokens]);

  const totalPages = Math.max(1, Math.ceil(searchedRows.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const start = safePage * pageSize;
  const current = searchedRows.slice(start, start + pageSize);

  const goTo = (target: number) => {
    const next = Math.max(0, Math.min(totalPages - 1, target));
    onPageChange(next);
  };

  const getCachedTranscript = useCallback((callId: string) => getCachedTranscriptSegments(callId), []);

  const loadTranscript = useCallback(async (callId: string) => {
    return loadTranscriptSegments(callId);
  }, []);

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
              {t("Biblioteca de chamadas", "Biblioteca de llamadas")}
            </p>
            <h3 className="text-lg font-semibold text-slate-50">
              {searchedRows.length > 0
                ? t(
                    `${formatNumber(searchedRows.length)} chamadas dentro dos filtros atuais`,
                    `${formatNumber(searchedRows.length)} llamadas dentro de los filtros actuales`,
                  )
                : t("Nenhuma chamada encontrada com os filtros atuais", "No se encontraron llamadas con los filtros actuales")}
            </h3>
            {searchedRows.length > 0 && (
              <p className="text-xs text-slate-400">
                {t(
                  "Navegue para investigar manualmente as transcrições e divergências mais relevantes.",
                  "Navega para investigar manualmente las transcripciones y divergencias más relevantes.",
                )}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end gap-3">
            <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2">
              <FilterIcon className="h-4 w-4 text-accent-soft" />
              <input
                value={search}
                onChange={(event) => {
                  onSearchChange(event.target.value);
                  onPageChange(0);
                }}
                className="border-0 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
                placeholder={t(
                  "Busca avançada · ex: status:dialogo script:aligned followup:sim",
                  "Búsqueda avanzada · ej: status:dialogo script:aligned followup:si",
                )}
              />
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={onDownloadReport}
                disabled={downloadDisabled}
                className={clsx(
                  "flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-sm transition",
                  downloadDisabled
                    ? "bg-black/20 text-slate-500 cursor-not-allowed"
                    : "bg-white/5 text-slate-100 hover:bg-white/10",
                )}
              >
                <Download className="h-4 w-4" />
                {t("Baixar planilha", "Descargar planilla")}
              </button>
              <button
                type="button"
                onClick={onDownloadMetrics}
                disabled={downloadDisabled}
                className={clsx(
                  "flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-sm transition",
                  downloadDisabled
                    ? "bg-black/20 text-slate-500 cursor-not-allowed"
                    : "bg-white/5 text-slate-100 hover:bg-white/10",
                )}
              >
                <FileBarChart className="h-4 w-4" />
                {t("Exportar métricas", "Exportar métricas")}
              </button>
            </div>
            <p className="text-right text-[11px] text-slate-500">
              {t(
                "Filtros disponíveis: status, status_real, produto, fila, contato, sentimento, engajamento, silêncio, duração, palavras, motivo, divergente. Combine com termos livres.",
                "Filtros disponibles: status, status_real, producto, fila, contacto, sentimiento, engagement, silencio, duración, palabras, motivo, divergente. Combina con términos libres.",
              )}
            </p>
            <div className="flex items-center gap-2">
            <button
              onClick={() => goTo(0)}
              disabled={safePage === 0}
              className={clsx(
                "flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10",
                safePage === 0 ? "text-slate-600" : "text-slate-100 hover:bg-white/10",
              )}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">
              {t("Página", "Página")}
              {` ${totalPages === 0 ? 0 : safePage + 1} ${t("de", "de")} ${totalPages}`}
            </div>
            <button
              onClick={() => goTo(totalPages - 1)}
              disabled={safePage === totalPages - 1 || totalPages === 0}
              className={clsx(
                "flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10",
                safePage === totalPages - 1 || totalPages === 0
                  ? "text-slate-600"
                  : "text-slate-100 hover:bg-white/10",
              )}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
          </div>
        </div>
      </Card>

      {current.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-300">
            {t(
              "Ajuste os filtros ou volte à primeira página para visualizar as chamadas disponíveis.",
              "Ajusta los filtros o vuelve a la primera página para visualizar las llamadas disponibles.",
            )}
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {current.map((row) => (
            <AudioLibraryCard
              key={row.call_id}
              row={row}
              getCachedTranscript={getCachedTranscript}
              loadTranscript={loadTranscript}
            />
          ))}
        </div>
      )}

      {searchedRows.length > 0 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => goTo(safePage - 1)}
            disabled={safePage === 0}
            className={clsx(
              "flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-sm",
              safePage === 0 ? "text-slate-600" : "text-slate-100 hover:bg-white/10",
            )}
          >
            <ChevronLeft className="h-4 w-4" /> {t("Página anterior", "Página anterior")}
          </button>
          <button
            onClick={() => goTo(safePage + 1)}
            disabled={safePage === totalPages - 1}
            className={clsx(
              "flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-sm",
              safePage === totalPages - 1 ? "text-slate-600" : "text-slate-100 hover:bg-white/10",
            )}
          >
            {t("Próxima página", "Página siguiente")} <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function AudioLibraryCard({
  row,
  loadTranscript,
  getCachedTranscript,
}: {
  row: PerCallDetail;
  loadTranscript: (callId: string) => Promise<TranscriptSegment[]>;
  getCachedTranscript: (callId: string) => TranscriptSegment[] | undefined;
}) {
  const t = useTranslate();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const [showTranscript, setShowTranscript] = useState(() => Boolean(getCachedTranscript(row.call_id)));
  const [segments, setSegments] = useState<TranscriptSegment[] | null>(() => getCachedTranscript(row.call_id) ?? null);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const ensureTranscript = useCallback(async () => {
    if (segments) return;
    setLoadingTranscript(true);
    const fetched = await loadTranscript(row.call_id);
    setSegments(fetched);
    setLoadingTranscript(false);
  }, [loadTranscript, row.call_id, segments]);

  const handlePlay = useCallback(() => {
    if (!showTranscript) {
      setShowTranscript(true);
    }
    void ensureTranscript();
  }, [ensureTranscript, showTranscript]);

  const handleToggleTranscript = () => {
    const next = !showTranscript;
    setShowTranscript(next);
    if (next && !segments) {
      void ensureTranscript();
    }
  };

  const handleSeek = (time: number) => {
    const audioEl = audioRef.current;
    if (!audioEl) return;
    audioEl.currentTime = time + 0.05;
    void audioEl.play().catch(() => undefined);
  };

  useEffect(() => {
    const audioEl = audioRef.current;
    if (!audioEl) return;
    const updateTime = () => setCurrentTime(audioEl.currentTime);
    const resetTime = () => setCurrentTime(0);
    audioEl.addEventListener("timeupdate", updateTime);
    audioEl.addEventListener("ended", resetTime);
    return () => {
      audioEl.removeEventListener("timeupdate", updateTime);
      audioEl.removeEventListener("ended", resetTime);
    };
  }, []);

  useEffect(() => {
    if (!showTranscript) return;
    if (!segments || segments.length === 0) return;
    const active = transcriptRef.current?.querySelector('[data-active="true"]') as HTMLElement | null;
    if (active) {
      active.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [currentTime, showTranscript, segments]);

  const activeSegmentId = segments?.find((segment) => currentTime >= segment.start && currentTime < segment.end)?.id ?? null;

  const segmentRangeLabel = (segment: TranscriptSegment, index: number) => {
    const startLabel = formatSeconds(segment.start);
    const rawEnd = Number.isFinite(segment.end) ? segment.end : segment.start;
    const hasRange = Number.isFinite(rawEnd) && rawEnd > segment.start;
    if (!hasRange) {
      return `${t("Trecho", "Tramo")} ${String(index + 1).padStart(2, "0")}`;
    }
    const endLabel = formatSeconds(rawEnd);
    return `${startLabel} → ${endLabel}`;
  };

  const segmentDurationLabel = (segment: TranscriptSegment) => {
    const duration = Math.max(0, (Number.isFinite(segment.end) ? segment.end : segment.start) - segment.start);
    return `Δ${formatSeconds(duration)}`;
  };

  const scriptLabel = (() => {
    switch (row.script_alignment_label) {
      case "aligned":
        return t("Script seguido", "Guion seguido");
      case "partial":
        return t("Script parcial", "Guion parcial");
      case "off_script":
        return t("Fora do script", "Fuera del guion");
      default:
        return t("Sem script", "Sin guion");
    }
  })();
  const scriptDetail =
    row.script_keyword_total > 0
      ? t(
          `${formatNumber(row.script_keyword_hits)} de ${formatNumber(row.script_keyword_total)} termos reconhecidos.`,
          `${formatNumber(row.script_keyword_hits)} de ${formatNumber(row.script_keyword_total)} términos reconocidos.`,
        )
      : t("Nenhum roteiro associado.", "Ningún libreto asociado.");
  const scriptKeywords = (row.script_keywords_matched ?? []).filter(Boolean);
  const scriptDetailRich =
    scriptKeywords.length > 0 ? `${scriptDetail} · ${scriptKeywords.join(" | ")}` : scriptDetail;

  const sourceLabel =
    row.operator_source_awareness === 1
      ? row.operator_source_awareness_level >= 2
        ? t("Origem reforçada", "Origen reforzada")
        : t("Origem reconhecida", "Origen reconocida")
      : t("Origem não citada", "Origen no mencionada");
  const sourceDetail =
    row.operator_source_awareness === 1
      ? row.operator_source_awareness_matches?.length
        ? row.operator_source_awareness_matches.join(" | ")
        : t("Menção ao bot ou interesse capturada.", "Se capturó mención al bot o al interés.")
      : t("Sem referência ao fluxo automatizado.", "Sin referencia al flujo automatizado.");

  const topicNames: Record<string, { pt: string; es: string }> = {
    price: { pt: "Preço", es: "Precio" },
    benefits: { pt: "Benefícios", es: "Beneficios" },
    loyalty: { pt: "Fidelização", es: "Fidelización" },
    differentials: { pt: "Diferenciais", es: "Diferenciales" },
  };
  const pitchTopics =
    row.sales_pitch_topics?.map((topic) => {
      const label = topicNames[topic];
      return label ? t(label.pt, label.es) : topic;
    }) ?? [];
  const salesLabel =
    row.sales_pitch_label === "satisfactory"
      ? t("Pitch completo", "Pitch completo")
      : row.sales_pitch_label === "nominal"
        ? t("Pitch parcial", "Pitch parcial")
        : t("Pitch fraco", "Pitch débil");
  const salesDetail =
    pitchTopics.length > 0
      ? pitchTopics.join(", ")
      : t("Argumentos comerciais não detectados.", "No se detectaron argumentos comerciales.");
  const salesTopicsRaw = (row.sales_pitch_topics ?? []).filter(Boolean);
  const salesDetailRich =
    salesTopicsRaw.length > 0 ? `${salesDetail} · ${salesTopicsRaw.join(" | ")}` : salesDetail;

  const followUpLabel =
    row.follow_up_commitment === 1
      ? t("Follow-up combinado", "Seguimiento pactado")
      : t("Sem follow-up", "Sin seguimiento");
  const followUpDetail =
    row.follow_up_commitment === 1
      ? row.follow_up_actor === "agent"
        ? t("Promessa emitida pelo agente.", "Promesa emitida por el agente.")
        : row.follow_up_actor === "customer"
          ? t("Solicitação do cliente registrada.", "Solicitud del cliente registrada.")
          : t("Follow-up citado na conversa.", "Seguimiento citado en la conversación.")
      : t("Nenhuma referência a retorno ou visita.", "Sin referencia a retorno o visita.");
  const followUpMatches = (row.follow_up_matches ?? []).filter(Boolean);
  const followUpDetailRich =
    row.follow_up_commitment === 1 && followUpMatches.length > 0
      ? `${followUpDetail} · ${followUpMatches.join(" | ")}`
      : followUpDetail;

  const objectionLabel =
    row.objection_handled === 1
      ? t("Objeção tratada", "Objeción tratada")
      : t("Sem contra-argumento", "Sin contraargumento");
  const objectionDetail =
    row.objection_handled === 1
      ? t(
          `${formatNumber(row.objection_handled_count)} resposta(s) direta(s) às objeções do cliente.`,
          `${formatNumber(row.objection_handled_count)} respuesta(s) directa(s) a las objeciones del cliente.`,
        )
      : t("Nenhum contraponto após objeções do cliente.", "Sin contrapunto tras objeciones del cliente.");

  const angerLabel =
    row.customer_anger_detected === 1
      ? t("Cliente irritado", "Cliente molesto")
      : t("Cliente estável", "Cliente estable");
  const angerMatch = row.customer_anger_matches?.[0];
  const angerDetail =
    row.customer_anger_detected === 1
      ? angerMatch
        ? `"${angerMatch}"`
        : t("Sentimento negativo consistente na chamada.", "Sentimiento negativo consistente en la llamada.")
      : t("Sem pedidos para interromper as ligações.", "Sin pedidos para detener las llamadas.");

  const identityLabel =
    row.agent_name_detected || row.customer_name_detected
      ? t("Identidades detectadas", "Identidades detectadas")
      : t("Identidades indefinidas", "Identidades indefinidas");
  const identityParts: string[] = [];
  if (row.agent_name_detected) {
    identityParts.push(
      `${t("Agente", "Agente")}: ${row.agent_name_detected}${row.agent_name_confidence ? ` (${formatNumber(row.agent_name_confidence, 2)})` : ""}`,
    );
  }
  if (row.customer_name_detected) {
    identityParts.push(
      `${t("Cliente", "Cliente")}: ${row.customer_name_detected}${row.customer_name_confidence ? ` (${formatNumber(row.customer_name_confidence, 2)})` : ""}`,
    );
  }
  const identityDetail = identityParts.length > 0 ? identityParts.join(" · ") : t("Nomes não identificados.", "Nombres no identificados.");
  const llmNotes = row.llm_notes;

  const infoBoxes = [
    {
      key: "script",
      icon: <Target className="h-4 w-4 text-emerald-200" />,
      label: scriptLabel,
      detail: scriptDetailRich,
      emphasis: row.script_alignment_label === "aligned" ? "positive" : row.script_alignment_label === "off_script" ? "critical" : row.script_alignment_label === "partial" ? "warning" : "neutral",
    },
    {
      key: "source",
      icon: <Bot className="h-4 w-4 text-sky-200" />,
      label: sourceLabel,
      detail: sourceDetail,
      emphasis: row.operator_source_awareness === 1 ? "positive" : "warning",
    },
    {
      key: "sales",
      icon: <Megaphone className="h-4 w-4 text-amber-200" />,
      label: salesLabel,
      detail: salesDetailRich,
      emphasis: row.sales_pitch_label === "satisfactory" ? "positive" : row.sales_pitch_label === "nominal" ? "neutral" : "warning",
    },
    {
      key: "followup",
      icon: <CalendarClock className="h-4 w-4 text-cyan-200" />,
      label: followUpLabel,
      detail: followUpDetailRich,
      emphasis: row.follow_up_commitment === 1 ? "positive" : "warning",
    },
    {
      key: "objection",
      icon: <ShieldCheck className="h-4 w-4 text-emerald-200" />,
      label: objectionLabel,
      detail: objectionDetail,
      emphasis: row.objection_handled === 1 ? "positive" : "warning",
    },
    {
      key: "anger",
      icon: <PhoneOff className="h-4 w-4 text-rose-200" />,
      label: angerLabel,
      detail: angerDetail,
      emphasis: row.customer_anger_detected === 1 ? "critical" : "neutral",
    },
  ];
  if (identityParts.length > 0) {
    infoBoxes.push({
      key: "identity",
      icon: <User className="h-4 w-4 text-indigo-200" />,
      label: identityLabel,
      detail: identityDetail,
      emphasis: "neutral",
    });
  }
  if (llmNotes) {
    infoBoxes.push({
      key: "llm-notes",
      icon: <Sparkles className="h-4 w-4 text-fuchsia-200" />,
      label: t("Resumo do LLM", "Resumen del LLM"),
      detail: llmNotes,
      emphasis: "neutral",
    });
  }


  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-100">{row.call_id}</span>
        <span
          className={clsx(
            "rounded-full px-3 py-1 text-xs font-semibold",
            row.divergente === 1 ? "bg-rose-500/20 text-rose-100" : "bg-emerald-500/20 text-emerald-100",
          )}
        >
          {row.divergente === 1 ? t("Divergente", "Divergente") : t("Confiável", "Confiable")}
        </span>
      </div>
      <div className="mt-3 space-y-2 text-xs text-slate-300">
        <div className="flex items-center justify-between">
          <span>{t("Status IZZI", "Estado IZZI")}</span>
          <span className="font-semibold text-slate-100">{row.izzi_status_normalizado}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>{t("Status Real", "Estado Real")}</span>
          <span className="font-semibold text-slate-100">{row.status_real_detectado}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>{t("Duração", "Duración")}</span>
          <span>{formatSeconds(row.duration_seconds_transcript)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>{t("Engajamento cliente", "Compromiso del cliente")}</span>
          <span>{row.customer_engagement_score.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>{t("Silêncio", "Silencio")}</span>
          <span>{formatPercent(row.silence_ratio)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>{t("Sentimento cliente", "Sentimiento del cliente")}</span>
          <span className="font-semibold" style={{ color: SENTIMENT_COLOR[row.customer_sentiment_label] ?? "#a5b4fc" }}>
            {SENTIMENT_EMOJI[row.customer_sentiment_label] ?? "😐"} {translateSentiment(row.customer_sentiment_label, t)}
          </span>
      </div>
      <div className="flex items-center justify-between">
        <span>{t("Fila", "Cola")} · {t("Tipo", "Tipo")}</span>
        <span className="text-right text-slate-200">
          {row.queue ?? "—"} · {row.contact_type ?? "—"}
        </span>
      </div>
    </div>

    <div className="mt-3 grid gap-2 text-xs text-slate-200 sm:grid-cols-2">
      {infoBoxes.map((box) => (
        <div
          key={box.key}
          className="flex items-start gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2"
        >
          <div className="mt-0.5 rounded-2xl border border-white/10 bg-white/10 p-1.5">{box.icon}</div>
          <div className="flex-1">
            <p
              className={clsx(
                "font-semibold",
                box.emphasis === "positive" && "text-emerald-200",
                box.emphasis === "neutral" && "text-slate-100",
                box.emphasis === "warning" && "text-amber-200",
                box.emphasis === "critical" && "text-rose-200",
              )}
            >
              {box.label}
            </p>
            <p className="text-[11px] text-slate-400">{box.detail}</p>
          </div>
        </div>
      ))}
      </div>

      <div className="mt-4 flex flex-col gap-2">
      <audio
        ref={audioRef}
        controls
        preload="none"
          onPlay={handlePlay}
          className="w-full rounded-2xl bg-black/20"
          src={`${import.meta.env.BASE_URL ?? "/"}audio/${row.call_id}.WAV`}
        >
          {t("Seu navegador não suporta áudio embutido.", "Tu navegador no soporta audio embebido.")}
        </audio>
        <button
          type="button"
          onClick={handleToggleTranscript}
          className="self-end text-xs font-semibold text-slate-200 transition hover:text-white"
        >
          {showTranscript ? t("Ocultar transcrição", "Ocultar transcripción") : t("Mostrar transcrição", "Mostrar transcripción")}
        </button>
      </div>

      {showTranscript && (
        <div className="mt-3 rounded-2xl border border-white/10 bg-white/5 p-3">
          {loadingTranscript && !segments && (
            <p className="text-xs text-slate-300">{t("Carregando transcrição...", "Cargando transcripción...")}</p>
          )}
          {!loadingTranscript && segments && segments.length === 0 && (
            <p className="text-xs text-slate-300">{t("Transcrição indisponível para esta chamada.", "Transcripción no disponible para esta llamada.")}</p>
          )}
          {segments && segments.length > 0 && (
            <div ref={transcriptRef} className="max-h-64 space-y-2 overflow-y-auto pr-1 text-sm leading-relaxed">
              {segments.map((segment, index) => {
                const active = activeSegmentId === segment.id;
                return (
                  <button
                    key={segment.id}
                    type="button"
                    data-active={active ? "true" : "false"}
                    onClick={() => handleSeek(segment.start)}
                    className={clsx(
                      "flex w-full items-start gap-3 rounded-xl border px-3 py-2 text-left transition",
                      active
                        ? "border-sky-400/40 bg-white/15 text-slate-50 shadow-glow"
                        : "border-transparent bg-transparent text-slate-200 hover:border-white/10 hover:bg-white/5",
                    )}
                  >
                    <span className="mt-1 rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-100">
                      {segmentRangeLabel(segment, index)}
                    </span>
                    <span className="flex-1 text-sm">{segment.text}</span>
                    <span className="whitespace-nowrap text-[11px] text-slate-400">{segmentDurationLabel(segment)}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {row.divergencia_motivo && (
        <p className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200">
          {translateReason(row.divergencia_motivo, t)}
        </p>
      )}
    </Card>
  );
}

function ReportTab({
  rows,
  onDownloadReport,
}: {
  rows: PerCallDetail[];
  onDownloadReport: () => void;
}) {
  const t = useTranslate();
  const [statusFilter, setStatusFilter] = useState("all");
  const [izziFilter, setIzziFilter] = useState("all");
  const [islandFilter, setIslandFilter] = useState("all");
  const [divergenceFilter, setDivergenceFilter] = useState<"all" | "divergent" | "matched">("all");
  const [scriptFilter, setScriptFilter] = useState("all");
  const [pitchFilter, setPitchFilter] = useState("all");
  const [sentimentFilter, setSentimentFilter] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const uniqueValues = useMemo(() => {
    const statuses = new Set<string>();
    const izziStatuses = new Set<string>();
    const islands = new Set<string>();
    const scripts = new Set<string>();
    const pitches = new Set<string>();
    const sentiments = new Set<string>();
    rows.forEach((row) => {
      if (row.status_real_detectado) statuses.add(row.status_real_detectado);
      if (row.izzi_status_normalizado) izziStatuses.add(row.izzi_status_normalizado);
      if (row.island || row.queue) islands.add(row.island ?? row.queue ?? "");
      if (row.script_alignment_label) scripts.add(row.script_alignment_label);
      if (row.sales_pitch_label) pitches.add(row.sales_pitch_label);
      if (row.customer_sentiment_label) sentiments.add(row.customer_sentiment_label);
    });
    return {
      statuses: Array.from(statuses).sort(),
      izziStatuses: Array.from(izziStatuses).sort(),
      islands: Array.from(islands).filter(Boolean).sort(),
      scripts: Array.from(scripts).sort(),
      pitches: Array.from(pitches).sort(),
      sentiments: Array.from(sentiments).sort(),
    };
  }, [rows]);

  const normalizedSearch = searchTerm.trim().toLowerCase();

  const filteredRows = useMemo(
    () =>
      rows.filter((row) => {
        if (statusFilter !== "all" && row.status_real_detectado !== statusFilter) return false;
        if (izziFilter !== "all" && row.izzi_status_normalizado !== izziFilter) return false;
        if (islandFilter !== "all" && (row.island ?? row.queue ?? "") !== islandFilter) return false;
        if (divergenceFilter === "divergent" && row.divergente !== 1) return false;
        if (divergenceFilter === "matched" && row.divergente === 1) return false;
        if (scriptFilter !== "all" && row.script_alignment_label !== scriptFilter) return false;
        if (pitchFilter !== "all" && row.sales_pitch_label !== pitchFilter) return false;
        if (sentimentFilter !== "all" && row.customer_sentiment_label !== sentimentFilter) return false;
        if (normalizedSearch) {
          const haystack = [
            row.call_id,
            row.phone_number,
            row.exec_id,
            row.island,
            row.queue,
            row.izzi_status_reportado,
            row.status_real_detectado,
            row.llm_notes,
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(normalizedSearch)) return false;
        }
        return true;
      }),
    [
      rows,
      statusFilter,
      izziFilter,
      islandFilter,
      divergenceFilter,
      scriptFilter,
      pitchFilter,
      sentimentFilter,
      normalizedSearch,
    ],
  );

  const executiveMetrics = useMemo(() => calculateExecutiveMetrics(filteredRows), [filteredRows]);

  const scriptLabel = useCallback(
    (label: string) => {
      switch (label) {
        case "aligned":
          return t("Alinhado", "Alineado");
        case "partial":
          return t("Parcial", "Parcial");
        case "off_script":
          return t("Fora do script", "Fuera del guion");
        default:
          return t("Sem avaliação", "Sin evaluación");
      }
    },
    [t],
  );

  const boolLabel = (flag: number | boolean | null | undefined) => (flag ? t("Sim", "Sí") : t("Não", "No"));

  const pitchLabel = useCallback(
    (row: PerCallDetail) => {
      const map: Record<string, string> = {
        weak: t("Fraco", "Débil"),
        nominal: t("Nominal", "Nominal"),
        satisfactory: t("Satisfatório", "Satisfactorio"),
        unknown: t("Indeterminado", "Indeterminado"),
      };
      const base = map[row.sales_pitch_label] ?? row.sales_pitch_label ?? "";
      return row.sales_pitch_score ? `${base} (${row.sales_pitch_score.toFixed(2)})` : base;
    },
    [t],
  );

  const origemResumo = useCallback(
    (row: PerCallDetail) => {
      if (!row.operator_source_awareness) return boolLabel(0);
      const evidencias = row.operator_source_awareness_matches?.length ? ` · ${row.operator_source_awareness_matches.join(" | ")}` : "";
      return `${boolLabel(1)} · ${t("nível", "nivel")} ${row.operator_source_awareness_level ?? 0}${evidencias}`;
    },
    [t],
  );

  const followUpResumo = useCallback(
    (row: PerCallDetail) => {
      if (!row.follow_up_commitment) return boolLabel(0);
      const owner = row.follow_up_actor ? ` (${row.follow_up_actor})` : "";
      const notes = row.follow_up_matches?.length ? ` · ${row.follow_up_matches.join(" | ")}` : "";
      return `${boolLabel(1)}${owner}${notes}`;
    },
    [t],
  );

  const objectionsResumo = (row: PerCallDetail) => {
    if (!row.objection_handled) return boolLabel(0);
    return `${boolLabel(1)} (${row.objection_handled_count ?? 0})`;
  };

  const angerResumo = (row: PerCallDetail) => {
    if (!row.customer_anger_detected) return boolLabel(0);
    const notes = row.customer_anger_matches?.length ? ` · ${row.customer_anger_matches.join(" | ")}` : "";
    return `${boolLabel(1)}${notes}`;
  };

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder={t("Buscar por ID, telefone, anotações...", "Buscar por ID, teléfono, notas...")}
            className="w-full max-w-xs rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          />
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Status real (todos)", "Estado real (todos)")}</option>
            {uniqueValues.statuses.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select
            value={izziFilter}
            onChange={(event) => setIzziFilter(event.target.value)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Status IZZI (todos)", "Estado IZZI (todos)")}</option>
            {uniqueValues.izziStatuses.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select
            value={islandFilter}
            onChange={(event) => setIslandFilter(event.target.value)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Ilha/Fila (todas)", "Isla/Cola (todas)")}</option>
            {uniqueValues.islands.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select
            value={divergenceFilter}
            onChange={(event) => setDivergenceFilter(event.target.value as "all" | "divergent" | "matched")}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Divergência (todas)", "Divergencia (todas)")}</option>
            <option value="divergent">{t("Somente divergentes", "Solo divergentes")}</option>
            <option value="matched">{t("Somente corretas", "Solo correctas")}</option>
          </select>
          <select
            value={scriptFilter}
            onChange={(event) => setScriptFilter(event.target.value)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Script (todos)", "Guion (todos)")}</option>
            {uniqueValues.scripts.map((value) => (
              <option key={value} value={value}>
                {scriptLabel(value)}
              </option>
            ))}
          </select>
          <select
            value={pitchFilter}
            onChange={(event) => setPitchFilter(event.target.value)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Pitch (todos)", "Pitch (todos)")}</option>
            {uniqueValues.pitches.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select
            value={sentimentFilter}
            onChange={(event) => setSentimentFilter(event.target.value)}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
          >
            <option value="all">{t("Sentimento (todos)", "Sentimiento (todos)")}</option>
            {uniqueValues.sentiments.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onDownloadReport}
            className="ml-auto flex items-center gap-2 rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-sm text-slate-100 transition hover:bg-white/20"
          >
            <Download className="h-4 w-4" />
            {t("Exportar CSV", "Exportar CSV")}
          </button>
        </div>
      </Card>

      <Card>
        <ExecutiveMetrics data={executiveMetrics.summary} />
      </Card>

      <Card>
        <QualityIndicators data={executiveMetrics.quality} />
      </Card>

      <Card>
        <AlertsSummary alerts={executiveMetrics.alerts} />
        <div className="mt-4">
          <AISummary text={executiveMetrics.aiSummary} />
        </div>
      </Card>

      <Card>
        <ExecutiveCharts
          statusDistribution={executiveMetrics.statusDistribution}
          divergenceDonut={executiveMetrics.divergenceDonut}
          timeline={executiveMetrics.timeline}
          heatmap={executiveMetrics.heatmap}
        />
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs uppercase tracking-[0.3em] text-slate-400">{t("Tabela executiva", "Tabla ejecutiva")}</span>
            <h3 className="text-lg font-semibold text-slate-50">
              {t("Resultados consolidados", "Resultados consolidados")} · {formatNumber(filteredRows.length)} {t("linhas", "filas")}
            </h3>
          </div>
          <button
            type="button"
            onClick={onDownloadReport}
            className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm text-slate-100 transition hover:bg-white/20"
          >
            <FileSpreadsheet className="h-4 w-4" />
            {t("Exportar CSV", "Exportar CSV")}
          </button>
        </div>
        <div className="mt-4 max-h-[520px] overflow-auto rounded-2xl border border-white/10">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="sticky top-0 bg-slate-950/90 text-xs uppercase tracking-[0.3em] text-slate-400">
              <tr>
                <th className="px-3 py-2">{t("Telefone", "Teléfono")}</th>
                <th className="px-3 py-2">{t("Ilha", "Isla")}</th>
                <th className="px-3 py-2">{t("Data", "Fecha")}</th>
                <th className="px-3 py-2">{t("Classificacao Chamada Izzi", "Clasificación llamada Izzi")}</th>
                <th className="px-3 py-2">{t("Status Real", "Estado Real")}</th>
                <th className="px-3 py-2">{t("Status Divergente/Nao divergente", "Estado divergente/no divergente")}</th>
                <th className="px-3 py-2">{t("Script Seguido (Abordagem vendedor)", "Guion seguido (abordaje vendedor)")}</th>
                <th className="px-3 py-2">{t("Origem Reconhecida", "Origen reconocida")}</th>
                <th className="px-3 py-2">{t("Pitch Vendas", "Pitch ventas")}</th>
                <th className="px-3 py-2">{t("FollowUp/Retorno", "Follow-up/Retorno")}</th>
                <th className="px-3 py-2">{t("ContraArgumentos", "Contraargumentos")}</th>
                <th className="px-3 py-2">{t("Clientes Irritados", "Clientes irritados")}</th>
                <th className="px-3 py-2">{t("Engajamento", "Engagement")}</th>
                <th className="px-3 py-2">{t("Silencio", "Silencio")}</th>
                <th className="px-3 py-2">{t("Sentimento", "Sentimiento")}</th>
                <th className="px-3 py-2">{t("Resumo/Analise Chamada", "Resumen/Análisis llamada")}</th>
                <th className="px-3 py-2">{t("Exec", "Exec")}</th>
                <th className="px-3 py-2">{t("Duracao", "Duración")}</th>
                <th className="px-3 py-2">{t("Tipo Chamada", "Tipo llamada")}</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.call_id} className="border-t border-white/5">
                  <td className="px-3 py-2 font-mono text-xs text-slate-300">{row.phone_number ?? ""}</td>
                  <td className="px-3 py-2">{row.island ?? row.queue ?? ""}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{row.call_datetime ?? ""}</td>
                  <td className="px-3 py-2">{row.izzi_status_reportado ?? ""}</td>
                  <td className="px-3 py-2 text-slate-50">{row.status_real_detectado}</td>
                  <td className={clsx("px-3 py-2", row.divergente === 1 ? "text-rose-300" : "text-emerald-300")}>
                    {row.divergente === 1 ? t("Divergente", "Divergente") : t("Não divergente", "No divergente")}
                  </td>
                  <td className="px-3 py-2">{scriptLabel(row.script_alignment_label)}</td>
                  <td className="px-3 py-2 text-xs text-slate-300">{origemResumo(row)}</td>
                  <td className="px-3 py-2 text-xs text-slate-300">{pitchLabel(row)}</td>
                  <td className="px-3 py-2 text-xs text-slate-300">{followUpResumo(row)}</td>
                  <td className="px-3 py-2 text-xs text-slate-300">{objectionsResumo(row)}</td>
                  <td className="px-3 py-2 text-xs text-slate-300">{angerResumo(row)}</td>
                  <td className="px-3 py-2">{row.customer_engagement_score.toFixed(3)}</td>
                  <td className="px-3 py-2">{formatPercent(row.silence_ratio, 1)}</td>
                  <td className="px-3 py-2">{`${row.customer_sentiment_label} (${row.customer_sentiment_score.toFixed(2)})`}</td>
                  <td className="px-3 py-2 text-xs text-slate-300">{row.llm_notes ?? t("Sem observações", "Sin observaciones")}</td>
                  <td className="px-3 py-2">{row.exec_id ?? ""}</td>
                  <td className="px-3 py-2">{formatSeconds(row.duration_seconds_transcript)}</td>
                  <td className="px-3 py-2">{row.contact_type ?? ""}</td>
                </tr>
              ))}
              {filteredRows.length === 0 && (
                <tr>
                  <td colSpan={19} className="px-3 py-10 text-center text-sm text-slate-400">
                    {t("Nenhuma chamada encontrada com os filtros atuais.", "No se encontraron llamadas con los filtros actuales.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}


function DashboardApp() {
  const { data, loading, error } = useDashboardData();
  const [filters, setFilters] = useState<DashboardFilters>(() => loadFilters());
  const [activeTab, setActiveTab] = useState("library");
  const [audioPage, setAudioPage] = useState(0);
  const [librarySearch, setLibrarySearch] = useState("");
  const [isFilterAnimating, setIsFilterAnimating] = useState(false);
  const filterAnimationTimeout = useRef<number | null>(null);
  const t = useTranslate();

  const handleDownloadReport = useCallback(() => {
    if (!data || !data.per_call_details?.length) {
      return;
    }

    const headers = [
      "Telefone",
      "Ilha",
      "Data",
      "Classificacao Chamada Izzi",
      "Status Real",
      "Status Divergente/Nao divergente",
      "Script Seguido (Abordagem vendedor)",
      "Origem Reconhecida",
      "Pitch Vendas",
      "FollowUp/Retorno",
      "ContraArgumentos",
      "Clientes Irritados",
      "Engajamento",
      "Silencio",
      "Sentimento",
      "Resumo/Analise Chamada",
      "Exec",
      "Duracao",
      "Tipo Chamada",
    ];

    const csvEscape = (raw: unknown) => {
      if (raw === null || raw === undefined) return "";
      const text = String(raw).replace(/\r?\n+/g, " ").trim();
      return `"${text.replace(/"/g, '""')}"`;
    };

    const toFixedString = (raw: unknown, digits = 2) => {
      const num = Number(raw);
      if (!Number.isFinite(num)) return "";
      return num.toFixed(digits);
    };

    const percentString = (raw: unknown, digits = 2) => {
      const num = Number(raw);
      if (!Number.isFinite(num)) return "";
      return `${(num * 100).toFixed(digits)}%`;
    };

    const scriptMap: Record<string, string> = {
      aligned: "Alinhado",
      partial: "Parcial",
      off_script: "Fora do script",
      unknown: "Sem avaliação",
    };
    const pitchMap: Record<string, string> = {
      weak: "Fraco",
      nominal: "Nominal",
      satisfactory: "Satisfatório",
      unknown: "Indeterminado",
    };
    const sentimentMap: Record<string, string> = {
      positive: "Positivo",
      neutral: "Neutro",
      negative: "Negativo",
      ausente: "Ausente",
      desconhecido: "Desconhecido",
    };

    const rows = data.per_call_details.map((row) => {
      const pitchLabel = pitchMap[row.sales_pitch_label as keyof typeof pitchMap] ?? row.sales_pitch_label ?? "";
      const pitchSummary = row.sales_pitch_score
        ? `${pitchLabel} (${toFixedString(row.sales_pitch_score, 2)})${row.sales_pitch_topics?.length ? ` - tópicos: ${row.sales_pitch_topics.join(", ")}` : ""}`
        : pitchLabel;
      const followUpSummary = row.follow_up_commitment
        ? `Sim${row.follow_up_actor ? ` (${row.follow_up_actor})` : ""}${row.follow_up_matches?.length ? ` - ${row.follow_up_matches.join(" | ")}` : ""}`
        : "Não";
      const objectionSummary = row.objection_handled
        ? `Sim (qtd: ${row.objection_handled_count ?? 0})`
        : "Não";
      const angerSummary = row.customer_anger_detected
        ? `Sim${row.customer_anger_matches?.length ? ` - ${row.customer_anger_matches.join(" | ")}` : ""}`
        : "Não";
      const origemSummary = row.operator_source_awareness
        ? `Sim (nível ${row.operator_source_awareness_level ?? 0}${row.operator_source_awareness_matches?.length ? `; evidências: ${row.operator_source_awareness_matches.join(" | ")}` : ""})`
        : "Não";
      const sentimentoSummary = `${sentimentMap[row.customer_sentiment_label as keyof typeof sentimentMap] ?? row.customer_sentiment_label ?? ""}${Number.isFinite(Number(row.customer_sentiment_score)) ? ` (${toFixedString(row.customer_sentiment_score, 2)})` : ""}`;

      const record = [
        row.phone_number ?? "",
        row.island ?? row.queue ?? "",
        row.call_datetime ?? "",
        row.izzi_status_reportado ?? "",
        row.status_real_detectado ?? "",
        row.divergente === 1 ? "Divergente" : "Não divergente",
        scriptMap[row.script_alignment_label as keyof typeof scriptMap] ?? row.script_alignment_label ?? "",
        origemSummary,
        pitchSummary,
        followUpSummary,
        objectionSummary,
        angerSummary,
        toFixedString(row.customer_engagement_score, 3),
        percentString(row.silence_ratio, 2),
        sentimentoSummary,
        row.llm_notes ?? "",
        row.exec_id ?? "",
        toFixedString(row.duration_seconds_transcript, 2),
        row.contact_type ?? "",
      ];

      return record.map(csvEscape).join(";");
    });

    const csvContent = [headers.join(";"), ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const dateSuffix = new Date().toISOString().slice(0, 10);
    link.download = `izzi_intelligence_dashboard_${dateSuffix}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }, [data]);

  const handleDownloadMetrics = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!data || !data.per_call_details?.length) {
      return;
    }

    const allRows = data.per_call_details;
    const divergenceRows = allRows.filter((row) => row.divergente === 1);
    const scopedRows = divergenceRows.length > 0 ? divergenceRows : allRows;
    const scopeTotal = scopedRows.length;

    if (scopeTotal === 0) {
      return;
    }

    const sanitizeStatus = (raw: string | null | undefined) => {
      if (!raw) return "Indefinido";
      const trimmed = raw.trim();
      return trimmed.length > 0 ? trimmed : "Indefinido";
    };

    const totalByIzzi = new Map<string, number>();
    const totalByReal = new Map<string, number>();

    allRows.forEach((row) => {
      const izzi = sanitizeStatus(row.izzi_status_normalizado ?? row.izzi_status_reportado);
      const real = sanitizeStatus(row.status_real_detectado);
      totalByIzzi.set(izzi, (totalByIzzi.get(izzi) ?? 0) + 1);
      totalByReal.set(real, (totalByReal.get(real) ?? 0) + 1);
    });

    type Aggregate = {
      izziStatus: string;
      realStatus: string;
      count: number;
      durationSum: number;
      engagementSum: number;
      silenceSum: number;
    };

    const aggregates = new Map<string, Aggregate>();

    scopedRows.forEach((row) => {
      const izzi = sanitizeStatus(row.izzi_status_normalizado ?? row.izzi_status_reportado);
      const real = sanitizeStatus(row.status_real_detectado);
      const key = `${izzi}||${real}`;
      let aggregate = aggregates.get(key);
      if (!aggregate) {
        aggregate = {
          izziStatus: izzi,
          realStatus: real,
          count: 0,
          durationSum: 0,
          engagementSum: 0,
          silenceSum: 0,
        };
        aggregates.set(key, aggregate);
      }
      aggregate.count += 1;
      if (Number.isFinite(row.duration_seconds_transcript)) {
        aggregate.durationSum += row.duration_seconds_transcript;
      }
      if (Number.isFinite(row.customer_engagement_score)) {
        aggregate.engagementSum += row.customer_engagement_score;
      }
      if (Number.isFinite(row.silence_ratio)) {
        aggregate.silenceSum += row.silence_ratio;
      }
    });

    if (aggregates.size === 0) {
      return;
    }

    const csvEscape = (raw: unknown) => {
      if (raw === null || raw === undefined) return "";
      const text = String(raw).replace(/\r?\n+/g, " ").trim();
      return `"${text.replace(/"/g, '""')}"`;
    };

    const toFixedString = (raw: number, digits = 2) => {
      if (!Number.isFinite(raw)) return "";
      return raw.toFixed(digits);
    };

    const percentString = (raw: number, digits = 2) => {
      if (!Number.isFinite(raw)) return "";
      return `${(raw * 100).toFixed(digits)}%`;
    };

    const shareWithin = (count: number, base: number) => {
      if (!Number.isFinite(count) || !Number.isFinite(base) || base <= 0) return "";
      return percentString(count / base);
    };

    const entries = Array.from(aggregates.values()).sort((a, b) => b.count - a.count);

    const totalDuration = entries.reduce((acc, entry) => acc + entry.durationSum, 0);
    const totalEngagement = entries.reduce((acc, entry) => acc + entry.engagementSum, 0);
    const totalSilence = entries.reduce((acc, entry) => acc + entry.silenceSum, 0);

    const scopeLabel =
      divergenceRows.length > 0
        ? "Divergências (status IZZI × status real)"
        : "Todas as chamadas (sem divergências marcadas)";

    const header = [
      "Escopo",
      "Status IZZI",
      "Status Real",
      "Chamadas (escopo)",
      "% dentro do escopo",
      "Chamadas com Status IZZI (total)",
      "% erro dentro do Status IZZI",
      "Chamadas com Status Real (total)",
      "Duração média (s)",
      "Engajamento médio",
      "Silêncio médio (%)",
    ];

    const rows = entries.map((entry) => {
      const averageDuration = entry.durationSum / entry.count;
      const averageEngagement = entry.engagementSum / entry.count;
      const averageSilence = entry.silenceSum / entry.count;
      const izziTotal = totalByIzzi.get(entry.izziStatus) ?? 0;
      const realTotal = totalByReal.get(entry.realStatus) ?? 0;
      return [
        scopeLabel,
        entry.izziStatus,
        entry.realStatus,
        String(entry.count),
        shareWithin(entry.count, scopeTotal),
        String(izziTotal),
        shareWithin(entry.count, izziTotal),
        String(realTotal),
        toFixedString(averageDuration),
        toFixedString(averageEngagement, 3),
        percentString(averageSilence),
      ]
        .map(csvEscape)
        .join(";");
    });

    const overallRow = [
      scopeLabel,
      "TOTAL",
      "-",
      String(scopeTotal),
      percentString(1),
      "",
      "",
      "",
      toFixedString(totalDuration / scopeTotal),
      toFixedString(totalEngagement / scopeTotal, 3),
      percentString(totalSilence / scopeTotal),
    ]
      .map(csvEscape)
      .join(";");

    const csvContent = [header.join(";"), ...rows, overallRow].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const dateSuffix = new Date().toISOString().slice(0, 10);
    link.download = `izzi_intelligence_metricas_${dateSuffix}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  }, [data]);

  const canDownloadReport = Boolean(data?.per_call_details?.length);

  const triggerFilterAnimation = useCallback(() => {
    if (typeof window === "undefined") return;
    if (filterAnimationTimeout.current !== null) {
      window.clearTimeout(filterAnimationTimeout.current);
    }
    setIsFilterAnimating(true);
    filterAnimationTimeout.current = window.setTimeout(() => {
      setIsFilterAnimating(false);
      filterAnimationTimeout.current = null;
    }, 1500);
  }, []);

  useEffect(() => {
    return () => {
      if (filterAnimationTimeout.current !== null) {
        window.clearTimeout(filterAnimationTimeout.current);
      }
    };
  }, []);

  useEffect(() => {
    saveFilters(filters);
  }, [filters]);

  useEffect(() => {
    const stored = loadFilters();
    setFilters(stored);
  }, []);

  const setFilter = useCallback(
    <K extends keyof DashboardFilters>(key: K, value: DashboardFilters[K]) => {
      triggerFilterAnimation();
      setFilters((prev) => ({ ...prev, [key]: value }));
    },
    [triggerFilterAnimation],
  );

  const resetFilters = useCallback(() => {
    triggerFilterAnimation();
    setFilters(initialFilters);
  }, [triggerFilterAnimation]);

  useEffect(() => {
    setAudioPage(0);
  }, [filters, librarySearch]);

  const filtered = useMemo(() => {
    if (!data) return [] as PerCallDetail[];
    // Add likely_sale calculated field
    const dataWithSales = data.per_call_details.map(row => ({
      ...row,
      likely_sale: row.follow_up_commitment === 1 && isSatisfactoryPitch(row.sales_pitch_label) ? 1 : 0
    }));
    return applyFilters(dataWithSales, filters);
  }, [data, filters]);

  const insights = useMemo(() => (data ? buildInsights(data, t) : []), [data, t]);

  const productOptions = useMemo(() => {
    if (!data) return [] as string[];
    return Array.from(new Set(data.per_call_details.map((row) => row.product_offer).filter(Boolean))) as string[];
  }, [data]);

  const queueOptions = useMemo(() => {
    if (!data) return [] as string[];
    return Array.from(new Set(data.per_call_details.map((row) => row.queue).filter(Boolean))) as string[];
  }, [data]);

  const contactOptions = useMemo(() => {
    if (!data) return [] as string[];
    return Array.from(new Set(data.per_call_details.map((row) => row.contact_type).filter(Boolean))) as string[];
  }, [data]);

  const monthOptions = useMemo(() => {
    if (!data) return [] as { value: string; label: string; count: number }[];
    const monthCounts = new Map<string, number>();
    data.per_call_details.forEach((row) => {
      const month = row.call_datetime?.split(" ")[0]?.split("/")[1];
      const year = row.call_datetime?.split(" ")[0]?.split("/")[2];
      if (month && year) {
        const key = `${month}/${year}`;
        monthCounts.set(key, (monthCounts.get(key) || 0) + 1);
      }
    });
    return Array.from(monthCounts.entries())
      .map(([key, count]) => ({
        value: key.split("/")[0],
        label: key,
        count,
      }))
      .sort((a, b) => {
        const [aMonth, aYear] = a.label.split("/").map(Number);
        const [bMonth, bYear] = b.label.split("/").map(Number);
        return aYear !== bYear ? aYear - bYear : aMonth - bMonth;
      });
  }, [data]);

  const applySevereDetection = useCallback(() => {
    triggerFilterAnimation();
    setFilters((prev) => ({
      ...prev,
      divergence: "divergent",
      izziStatus: "all",
      realStatus: "all",
      silence: [0.2, 1],
      engagement: [0, 1],
    }));
  }, [triggerFilterAnimation]);

  const handleLibrarySearchChange = useCallback(
    (value: string) => {
      triggerFilterAnimation();
      setLibrarySearch(value);
    },
    [triggerFilterAnimation],
  );

  const handleAudioPageChange = useCallback(
    (pageIndex: number) => {
      triggerFilterAnimation();
      setAudioPage(pageIndex);
    },
    [triggerFilterAnimation],
  );

  if (loading || !data) {
    return (
      <div className="flex h-screen w-full items-center justify-center text-slate-200">
        {error ? (
          <div className="rounded-3xl border border-rose-500/50 bg-rose-500/10 px-10 py-8 text-center">
            <p className="text-base font-semibold text-rose-100">{error}</p>
            <p className="mt-2 text-sm text-rose-200/70">
              {t(
                "Confira se o arquivo full_analysis.json está acessível em /data/full_analysis.json",
                "Verifica si el archivo full_analysis.json está accesible en /data/full_analysis.json",
              )}
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-3xl border border-white/10 bg-white/5 px-8 py-6 shadow-glow backdrop-blur">
            <Loader2 className="h-5 w-5 animate-spin text-accent-soft" />
            <span className="text-sm font-medium text-slate-200">
              {t(
                "Curando 600 chamadas com inteligência de IA...",
                "Curando 600 llamadas con inteligencia de IA...",
              )}
            </span>
          </div>
        )}
      </div>
    );
  }

  const tabs = [
    { key: "library", label: t("Biblioteca de áudios", "Biblioteca de audios"), icon: <Radio className="h-4 w-4" /> },
    {
      key: "report",
      label: t("Visão executiva", "Visión ejecutiva"),
      icon: <FileSpreadsheet className="h-4 w-4" />,
    },
    {
      key: "monthly",
      label: t("Evolução Mensal", "Evolución Mensual"),
      icon: <TrendingUp className="h-4 w-4" />,
    },
    {
      key: "agents",
      label: t("Performance por Agente", "Rendimiento por Agente"),
      icon: <User className="h-4 w-4" />,
    },
    {
      key: "risk",
      label: t("Reincidências e Riscos", "Reincidencias y Riesgos"),
      icon: <ShieldAlert className="h-4 w-4" />,
    },
  ];

  return (
    <div className="relative min-h-screen w-full overflow-x-hidden text-canvas-foreground">
      <AnimatePresence>
        {isFilterAnimating && (
          <motion.div
            key="filter-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/40 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="flex items-center gap-3 rounded-3xl border border-white/10 bg-slate-900/80 px-6 py-4 text-sm text-slate-200 shadow-lg"
            >
              <Loader2 className="h-5 w-5 animate-spin text-accent-soft" />
              <span>{t("Atualizando visualizações...", "Actualizando visualizaciones...")}</span>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-10 px-6 py-12">
        <div className="flex items-center justify-end">
          <LanguageToggle />
        </div>

        <div className="rounded-3xl border border-white/15 bg-white/5 p-3 shadow-glow backdrop-blur-xl">
          <Tabs options={tabs} value={activeTab} onChange={setActiveTab} />
        </div>

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2">
                <FilterIcon className="h-4 w-4 text-accent-soft" />
                <input
                    value={filters.search}
                    onChange={(event) => setFilter("search", event.target.value)}
                    className="border-0 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
                    placeholder={t("ID, produto, fila, motivo...", "ID, producto, fila, motivo...")}
                  />
                </div>
                <select
                  value={filters.month}
                  onChange={(event) => setFilter("month", event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
                >
                  <option value="all">{t("Mês (todos)", "Mes (todos)")}</option>
                  {monthOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label} ({opt.count})
                    </option>
                  ))}
                </select>
                <select
                  value={filters.izziStatus}
                  onChange={(event) => setFilter("izziStatus", event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
                >
                  <option value="all">{t("Status IZZI (todos)", "Estado IZZI (todos)")}</option>
                  {Array.from(new Set(data.per_call_details.map((row) => row.izzi_status_normalizado))).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <select
                  value={filters.realStatus}
                  onChange={(event) => setFilter("realStatus", event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
                >
                  <option value="all">{t("Status Real (todos)", "Estado Real (todos)")}</option>
                  {Array.from(new Set(data.per_call_details.map((row) => row.status_real_detectado))).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <select
                  value={filters.divergence}
                  onChange={(event) => setFilter("divergence", event.target.value as DashboardFilters["divergence"])}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
                >
                  <option value="all">{t("Divergência (todas)", "Divergencia (todas)")}</option>
                  <option value="divergent">{t("Somente divergentes", "Solo divergentes")}</option>
                  <option value="matched">{t("Somente confiáveis", "Solo confiables")}</option>
                </select>
                <button
                  onClick={resetFilters}
                  className="rounded-2xl border border-white/10 bg-transparent px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10"
                >
                  {t("Resetar filtros", "Restablecer filtros")}
                </button>
              </div>
          </div>
        </Card>

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="space-y-8"
          >
            {activeTab === "overview" && (
              <OverviewTab
                filtered={filtered}
                data={data}
                insights={insights}
                applyDetection={applySevereDetection}
              />
            )}
            {activeTab === "comparativo" && <ComparativoTab data={data} filtered={filtered} />}
            {activeTab === "correlacoes" && (
              <CorrelacoesTab
                filtered={filtered}
                controls={{
                  product: filters.product,
                  setProduct: (value) => setFilter("product", value),
                  productOptions,
                  queue: filters.queue,
                  setQueue: (value) => setFilter("queue", value),
                  queueOptions,
                  contact: filters.contactType,
                  setContact: (value) => setFilter("contactType", value),
                  contactOptions,
                }}
              />
            )}
            {activeTab === "temporal" && (
              <TemporalTab filtered={filtered} globalRate={data.dataset_summary.divergence_rate} />
            )}
            {activeTab === "precisao" && <PrecisaoTab filtered={filtered} />}
            {activeTab === "report" && (
              <ReportTab
                rows={filtered}
                onDownloadReport={handleDownloadReport}
              />
            )}
            {activeTab === "risk" && <ReincidenciasTab rows={filtered} />}
            {activeTab === "monthly" && <MonthlyComparisonTab filtered={filtered} data={data} />}
            {activeTab === "agents" && <AgentPerformanceTab filtered={filtered} />}
            {activeTab === "library" && (
              <AudioLibraryTab
                rows={filtered}
                page={audioPage}
                search={librarySearch}
                onSearchChange={handleLibrarySearchChange}
                onPageChange={handleAudioPageChange}
                onDownloadReport={handleDownloadReport}
                onDownloadMetrics={handleDownloadMetrics}
                downloadDisabled={!canDownloadReport}
              />
            )}
          </motion.div>
        </AnimatePresence>

        <footer className="pb-8 text-center text-xs text-slate-500">
          <span>{t("Paneas © 2025. Todos os direitos reservados.", "Paneas © 2025. Todos los derechos reservados.")}</span>
        </footer>
      </div>
    </div>
  );
}

function AppContent() {
  const [authenticated, setAuthenticated] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return sessionStorage.getItem("izzi-auth") === "1";
  });

  const handleLoginSuccess = () => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("izzi-auth", "1");
    }
    setAuthenticated(true);
  };

  if (!authenticated) {
    return <LoginPortal onSuccess={handleLoginSuccess} />;
  }

  return <DashboardApp />;
}

function App() {
  return (
    <LanguageProvider>
      <AppContent />
    </LanguageProvider>
  );
}

export default App;
