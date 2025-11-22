import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import type { DashboardData, PerCallDetail, TranscriptSegment } from "../../types";
import { loadTranscript as loadTranscriptSegments, getCachedTranscript as getCachedTranscriptSegments } from "../../utils/transcriptLoader";
import {
  computeWordFrequencies,
  buildConversationSummary,
  buildTimelineEvents,
  buildAlerts,
  computeAgentScores,
  type WordDatum,
} from "../../utils/conversationAnalytics";
import { formatPercent } from "../../utils/numberFormat";
import { CloudWordsSection } from "./CloudWordsSection";
import { SummarySection } from "./SummarySection";
import { TimelineSection } from "./TimelineSection";
import { AlertsPanel } from "./AlertsPanel";
import { NaturalSearch } from "./NaturalSearch";
import { AgentsRanking } from "./AgentsRanking";
import { SectionCard } from "./SectionCard";

interface ConversationAnalysisTabProps {
  data: DashboardData;
  filtered: PerCallDetail[];
}

interface CloudState {
  customer: WordDatum[];
  agent: WordDatum[];
  filtered: WordDatum[];
}

const INITIAL_CLOUD: CloudState = { customer: [], agent: [], filtered: [] };

const TABLE_HEADERS = [
  "Telefone",
  "Ilha",
  "Data",
  "Classificação Izzi",
  "Status Real",
  "Divergência",
  "Script",
  "Origem",
  "Pitch",
  "Follow-up",
  "Contra-argumentos",
  "Clientes irritados",
  "Engajamento",
  "Silêncio",
  "Sentimento",
  "Resumo",
  "Exec",
  "Duração",
  "Tipo",
];

function formatSeconds(value: number): string {
  if (!Number.isFinite(value)) return "0m00s";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}m${seconds}s`;
}

function buildCallLabel(call: PerCallDetail): string {
  return `${call.call_id} · ${call.call_datetime ?? "data desconhecida"}`;
}

function buildStatusLabel(row: PerCallDetail): string {
  switch (row.script_alignment_label) {
    case "aligned":
      return "Script seguido";
    case "partial":
      return "Parcial";
    case "off_script":
      return "Fora";
    default:
      return "Indefinido";
  }
}

export function ConversationAnalysisTab({ data, filtered }: ConversationAnalysisTabProps) {
  const [segmentsMap, setSegmentsMap] = useState<Map<string, TranscriptSegment[]>>(new Map());
  const [cloudData, setCloudData] = useState<CloudState>(INITIAL_CLOUD);
  const [cloudLoading, setCloudLoading] = useState(false);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [selectedSegments, setSelectedSegments] = useState<TranscriptSegment[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);

  useEffect(() => {
    let active = true;
    async function preloadSegments() {
      if (!data?.per_call_details?.length) {
        setSegmentsMap(new Map());
        return;
      }
      setCloudLoading(true);
      const map = new Map<string, TranscriptSegment[]>();
      try {
        await Promise.all(
          data.per_call_details.map(async (row) => {
            const cached = getCachedTranscriptSegments(row.call_id);
            if (cached?.length) {
              map.set(row.call_id, cached);
              return;
            }
            const segments = await loadTranscriptSegments(row.call_id);
            if (segments.length) {
              map.set(row.call_id, segments);
            }
          }),
        );
      } finally {
        if (active) {
          setSegmentsMap(map);
          setCloudLoading(false);
        }
      }
    }
    void preloadSegments();
    return () => {
      active = false;
    };
  }, [data]);

  const filteredIds = useMemo(() => filtered.map((row) => row.call_id), [filtered]);

  useEffect(() => {
    if (filteredIds.length === 0) {
      if (selectedCallId !== null) setSelectedCallId(null);
      return;
    }
    if (!selectedCallId || !filteredIds.includes(selectedCallId)) {
      setSelectedCallId(filteredIds[0]);
    }
  }, [filteredIds, selectedCallId]);

  useEffect(() => {
    let cancelled = false;
    async function ensureSelectedSegments() {
      if (!selectedCallId) {
        setSelectedSegments([]);
        return;
      }
      setTimelineLoading(true);
      const cached = getCachedTranscriptSegments(selectedCallId);
      const segments = cached ?? (await loadTranscriptSegments(selectedCallId));
      if (!cancelled) {
        setSelectedSegments(segments);
        setTimelineLoading(false);
      }
    }
    void ensureSelectedSegments();
    return () => {
      cancelled = true;
    };
  }, [selectedCallId]);

  useEffect(() => {
    const subset = new Map<string, TranscriptSegment[]>();
    segmentsMap.forEach((segments, callId) => subset.set(callId, segments));
    const customer = computeWordFrequencies(subset, {
      role: "customer",
      limit: 80,
      fallbackRows: data.per_call_details,
    });
    const agent = computeWordFrequencies(subset, {
      role: "agent",
      limit: 80,
      fallbackRows: data.per_call_details,
    });
    const filteredMap = new Map<string, TranscriptSegment[]>();
    filteredIds.forEach((id) => {
      const segments = segmentsMap.get(id);
      if (segments?.length) filteredMap.set(id, segments);
    });
    const filteredWords = computeWordFrequencies(filteredMap, {
      role: "all",
      limit: 80,
      fallbackRows: filtered,
    });
    setCloudData({ customer, agent, filtered: filteredWords });
  }, [segmentsMap, filteredIds, data, filtered]);

  const selectedCall = useMemo(() => {
    if (!selectedCallId) return null;
    return data.per_call_details.find((row) => row.call_id === selectedCallId) ?? null;
  }, [data, selectedCallId]);

  const summaryLines = useMemo(
    () => (selectedCall ? buildConversationSummary(selectedCall, { segments: selectedSegments }) : []),
    [selectedCall, selectedSegments],
  );

  const timelineEvents = useMemo(
    () => (selectedCall ? buildTimelineEvents(selectedCall, selectedSegments) : []),
    [selectedCall, selectedSegments],
  );

  const alerts = useMemo(
    () => (selectedCall ? buildAlerts(selectedCall, data.per_call_details, selectedSegments) : []),
    [selectedCall, data, selectedSegments],
  );

  const callOptions = useMemo(
    () => filtered.map((row) => ({ value: row.call_id, label: buildCallLabel(row) })),
    [filtered],
  );

  const metrics = useMemo(() => {
    const total = filtered.length;
    if (total === 0) {
      return {
        total,
        avgSentiment: 0,
        avgEngagement: 0,
        avgSilence: 0,
        divergent: 0,
      };
    }
    const sumSentiment = filtered.reduce((acc, row) => acc + row.customer_sentiment_score, 0);
    const sumEngagement = filtered.reduce((acc, row) => acc + row.customer_engagement_score, 0);
    const sumSilence = filtered.reduce((acc, row) => acc + row.silence_ratio, 0);
    const divergent = filtered.filter((row) => row.divergente === 1).length;
    return {
      total,
      avgSentiment: sumSentiment / total,
      avgEngagement: sumEngagement / total,
      avgSilence: sumSilence / total,
      divergent,
    };
  }, [filtered]);

  const agentScoreData = useMemo(() => computeAgentScores(data.per_call_details), [data]);

  const handleExportCsv = useCallback(() => {
    const now = new Date().toISOString().slice(0, 10);
    const lines: string[][] = [];
    lines.push(["Métrica", "Valor"]);
    lines.push(["Total de chamadas", String(metrics.total)]);
    lines.push(["Sentimento médio", metrics.total ? metrics.avgSentiment.toFixed(3) : "0"]);
    lines.push(["Engajamento médio", metrics.total ? metrics.avgEngagement.toFixed(3) : "0"]);
    lines.push(["Silêncio médio", metrics.total ? metrics.avgSilence.toFixed(3) : "0"]);
    lines.push(["Chamadas divergentes", String(metrics.divergent)]);
    lines.push([
      "Top palavras clientes",
      cloudData.customer
        .slice(0, 12)
        .map((word) => `${word.text}(${word.value})`)
        .join(" "),
    ]);
    lines.push([
      "Top palavras atendentes",
      cloudData.agent
        .slice(0, 12)
        .map((word) => `${word.text}(${word.value})`)
        .join(" "),
    ]);
    lines.push([]);
    lines.push(TABLE_HEADERS);

    filtered.forEach((row) => {
      lines.push([
        row.phone_number ? String(row.phone_number) : "—",
        row.island ?? "—",
        row.call_datetime ?? "—",
        row.izzi_status_normalizado ?? "—",
        row.status_real_detectado ?? "—",
        row.divergente === 1 ? "Divergente" : "Confiável",
        buildStatusLabel(row),
        row.operator_source_awareness === 1 ? "Reconhecida" : "Não citada",
        row.sales_pitch_label ?? "—",
        row.follow_up_commitment === 1 ? `Sim (${row.follow_up_actor ?? "indefinido"})` : "Não",
        row.objection_handled === 1 ? "Sim" : "Não",
        row.customer_anger_detected === 1 ? "Sim" : "Não",
        row.customer_engagement_score.toFixed(2),
        formatPercent(row.silence_ratio),
        `${row.customer_sentiment_label} (${row.customer_sentiment_score.toFixed(2)})`,
        row.llm_notes?.replace(/\s+/g, " ") ?? "—",
        row.exec_id ?? "—",
        formatSeconds(row.duration_seconds_transcript),
        row.contact_type ?? "—",
      ]);
    });

    const csv = lines
      .map((line) => line.map((value) => `"${String(value ?? "").replace(/"/g, '""')}"`).join(";"))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `analise_conversas_${now}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }, [metrics, cloudData, filtered]);

  return (
    <div className="space-y-6">
      <CloudWordsSection
        customerWords={cloudData.customer}
        agentWords={cloudData.agent}
        filteredWords={cloudData.filtered}
        loading={cloudLoading}
      />

      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <SummarySection
            call={selectedCall}
            summary={summaryLines}
            options={callOptions}
            onSelectCall={setSelectedCallId}
          />
          <TimelineSection segments={selectedSegments} events={timelineEvents} loading={timelineLoading} />
        </div>
        <div className="space-y-4">
          <AlertsPanel alerts={alerts} />
        </div>
      </div>

      <NaturalSearch rows={data.per_call_details} onSelectCall={setSelectedCallId} loadTranscript={loadTranscriptSegments} />

      <AgentsRanking scores={agentScoreData.scores} months={agentScoreData.months} />

      <SectionCard
        title="Tabela executiva de chamadas"
        subtitle="Detalhamento dos indicadores principais para o conjunto filtrado"
        actions={
          <button
            type="button"
            onClick={handleExportCsv}
            className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 transition hover:bg-white/10"
            disabled={filtered.length === 0}
          >
            Exportar CSV
          </button>
        }
      >
        {filtered.length === 0 ? (
          <p className="text-sm text-slate-400">Nenhuma chamada disponível com os filtros atuais.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs text-slate-200">
              <thead>
                <tr className="border-b border-white/10 text-[11px] uppercase tracking-[0.2em] text-slate-400">
                  {TABLE_HEADERS.map((header) => (
                    <th key={header} className="px-3 py-3">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.call_id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="px-3 py-2 font-semibold text-slate-100">{row.phone_number ?? "—"}</td>
                    <td className="px-3 py-2">{row.island ?? "—"}</td>
                    <td className="px-3 py-2">{row.call_datetime ?? "—"}</td>
                    <td className="px-3 py-2">{row.izzi_status_normalizado ?? "—"}</td>
                    <td className="px-3 py-2">{row.status_real_detectado ?? "—"}</td>
                    <td className="px-3 py-2">
                      <span
                        className={clsx(
                          "rounded-full px-2 py-1 text-[11px] font-semibold",
                          row.divergente === 1 ? "bg-rose-500/20 text-rose-200" : "bg-emerald-500/20 text-emerald-200",
                        )}
                      >
                        {row.divergente === 1 ? "Divergente" : "Confiável"}
                      </span>
                    </td>
                    <td className="px-3 py-2">{buildStatusLabel(row)}</td>
                    <td className="px-3 py-2">{row.operator_source_awareness === 1 ? "Reconhecida" : "Não citada"}</td>
                    <td className="px-3 py-2">{row.sales_pitch_label ?? "—"}</td>
                    <td className="px-3 py-2">{row.follow_up_commitment === 1 ? "Sim" : "Não"}</td>
                    <td className="px-3 py-2">{row.objection_handled === 1 ? "Sim" : "Não"}</td>
                    <td className="px-3 py-2">{row.customer_anger_detected === 1 ? "Sim" : "Não"}</td>
                    <td className="px-3 py-2">{row.customer_engagement_score.toFixed(2)}</td>
                    <td className="px-3 py-2">{formatPercent(row.silence_ratio)}</td>
                    <td className="px-3 py-2">{`${row.customer_sentiment_label} (${row.customer_sentiment_score.toFixed(2)})`}</td>
                    <td className="px-3 py-2 text-slate-300">{row.llm_notes?.slice(0, 180) ?? "—"}</td>
                    <td className="px-3 py-2">{row.exec_id ?? "—"}</td>
                    <td className="px-3 py-2">{formatSeconds(row.duration_seconds_transcript)}</td>
                    <td className="px-3 py-2">{row.contact_type ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
