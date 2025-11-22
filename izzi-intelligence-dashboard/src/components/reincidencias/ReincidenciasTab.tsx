import {
  useMemo,
  useState,
  useCallback,
} from "react";
import {
  AlertTriangle,
  BarChart3,
  Brain,
  Clock3,
  Download,
  Flame,
  Layers,
  Link2,
  PhoneCall,
  RefreshCcw,
  ShieldAlert,
  UserCheck,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTranslate } from "../../i18n";
import type { PerCallDetail } from "../../types";
import {
  buildPhoneTimelines,
  getFollowUpPendente,
  getReincidencias,
  getRiscoChurn,
  getTempoResolucao,
  parseCallDate,
  type ReincidenteClient,
} from "../../utils/reincidencias";
import { formatNumber, formatPercent, getLocale } from "../../utils/numberFormat";

interface Filters {
  island: string;
  status: string;
  pitch: string;
  startDate: string;
  endDate: string;
}

interface ReincidenciasTabProps {
  rows: PerCallDetail[];
}

const DEFAULT_FILTERS: Filters = {
  island: "all",
  status: "all",
  pitch: "all",
  startDate: "",
  endDate: "",
};

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-card-border/70 bg-card/80 p-6 shadow-glow backdrop-blur-xl">
      <div className="pointer-events-none absolute inset-0 opacity-40" />
      <div className="relative z-10 flex flex-col gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
          {description ? <p className="mt-1 text-sm text-slate-400">{description}</p> : null}
        </div>
        {children}
      </div>
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  primary,
  secondary,
  tone = "default",
}: {
  icon: React.ReactNode;
  label: string;
  primary: string;
  secondary?: string;
  tone?: "default" | "warning" | "critical" | "success";
}) {
  const toneClass =
    tone === "critical"
      ? "bg-rose-500/15 text-rose-100"
      : tone === "warning"
        ? "bg-amber-500/15 text-amber-100"
        : tone === "success"
          ? "bg-emerald-500/15 text-emerald-100"
          : "bg-white/10 text-slate-100";

  return (
    <div className="flex flex-1 flex-col gap-3 rounded-3xl border border-white/10 bg-white/5 p-4">
      <div className={`flex h-10 w-10 items-center justify-center rounded-2xl ${toneClass}`}>{icon}</div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-slate-200">{label}</p>
        <p className="text-2xl font-bold text-white">{primary}</p>
        {secondary ? <p className="text-xs text-slate-400">{secondary}</p> : null}
      </div>
    </div>
  );
}

function MetricItem({
  icon,
  label,
  value,
  helper,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  helper?: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-white/10 bg-white/5 p-3">
      <div className="mt-1 flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
        {icon}
      </div>
      <div className="flex-1">
        <p className="text-sm font-semibold text-slate-100">{label}</p>
        <p className="text-lg font-bold text-white">{value}</p>
        {helper ? <p className="text-xs text-slate-400">{helper}</p> : null}
      </div>
    </div>
  );
}

const numberFormatter = new Intl.DateTimeFormat(getLocale(), {
  dateStyle: "short",
  timeStyle: "short",
});

function formatDate(date: Date | null | undefined) {
  if (!date || Number.isNaN(date.getTime())) return "-";
  return numberFormatter.format(date);
}

function parseInputDate(value: string): Date | null {
  if (!value) return null;
  const [yearStr, monthStr, dayStr] = value.split("-");
  if (!yearStr || !monthStr || !dayStr) return null;
  const year = Number(yearStr);
  const month = Number(monthStr);
  const day = Number(dayStr);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  return new Date(Date.UTC(year, month - 1, day));
}

function getDivergenceLabel(value: number, t: ReturnType<typeof useTranslate>) {
  return value === 1
    ? t("Divergente", "Divergente")
    : t("Não divergente", "No divergente");
}

function getSentimentLabel(value: number | null) {
  if (value === null || Number.isNaN(value)) return "-";
  return value.toFixed(2);
}

function formatSigned(value: number) {
  if (value > 0) {
    return `+${formatNumber(value, 0)}`;
  }
  return formatNumber(value, 0);
}

function combineWeeklySeries(
  recurrence: ReturnType<typeof getReincidencias>["weeklySeries"],
  followUps: ReturnType<typeof getFollowUpPendente>["weeklySeries"],
) {
  const map = new Map<
    string,
    { label: string; weekStart: Date; reincidentes: number; followUps: number }
  >();

  for (const entry of recurrence) {
    const label = `${entry.week}`;
    map.set(entry.week, {
      label,
      weekStart: entry.weekStart,
      reincidentes: entry.count,
      followUps: 0,
    });
  }

  for (const entry of followUps) {
    if (!map.has(entry.week)) {
      map.set(entry.week, {
        label: `${entry.week}`,
        weekStart: entry.weekStart,
        reincidentes: 0,
        followUps: entry.pending,
      });
    } else {
      const current = map.get(entry.week)!;
      current.followUps = entry.pending;
    }
  }

  return Array.from(map.values()).sort((a, b) => a.weekStart.getTime() - b.weekStart.getTime());
}

function enrichClientsWithFollowUp(
  clients: ReincidenteClient[],
  pendingPhones: string[],
) {
  const pendingSet = new Set(pendingPhones);
  return clients.map((client) => ({
    ...client,
    followUpPending: pendingSet.has(client.phone),
  }));
}

export function ReincidenciasTab({ rows }: ReincidenciasTabProps) {
  const t = useTranslate();
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  const handleFilterChange = useCallback(<K extends keyof Filters>(key: K, value: Filters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const islands = useMemo(() => {
    const set = new Set<string>();
    for (const row of rows) {
      const value = (row.island ?? row.queue ?? "").trim();
      if (value) set.add(value);
    }
    return Array.from(set).sort();
  }, [rows]);

  const statuses = useMemo(() => {
    const set = new Set<string>();
    for (const row of rows) {
      const value = (row.status_real_detectado ?? "").trim();
      if (value) set.add(value);
    }
    return Array.from(set).sort();
  }, [rows]);

  const pitches = useMemo(() => {
    const set = new Set<string>();
    for (const row of rows) {
      const value = (row.sales_pitch_label ?? "").trim();
      if (value) set.add(value);
    }
    return Array.from(set)
      .filter((value) => value && value !== "unknown")
      .sort();
  }, [rows]);

  const filteredRows = useMemo(() => {
    if (!rows.length) return [];
    const startDate = filters.startDate ? parseInputDate(filters.startDate) : null;
    const endDate = filters.endDate ? parseInputDate(filters.endDate) : null;
    if (endDate) {
      endDate.setUTCHours(23, 59, 59, 999);
    }

    return rows.filter((row) => {
      if (!row.phone_number) return false;
      if (filters.island !== "all") {
        const island = (row.island ?? row.queue ?? "").trim();
        if (island !== filters.island) return false;
      }
      if (filters.status !== "all") {
        if ((row.status_real_detectado ?? "").trim() !== filters.status) return false;
      }
      if (filters.pitch !== "all") {
        if ((row.sales_pitch_label ?? "").trim() !== filters.pitch) return false;
      }
      if (startDate || endDate) {
        const date = parseCallDate(row.call_datetime ?? null);
        if (!date) return false;
        if (startDate && date.getTime() < startDate.getTime()) return false;
        if (endDate && date.getTime() > endDate.getTime()) return false;
      }
      return true;
    });
  }, [rows, filters]);

  const timelines = useMemo(() => buildPhoneTimelines(filteredRows), [filteredRows]);
  const reincidencias = useMemo(() => getReincidencias(filteredRows, timelines), [filteredRows, timelines]);
  const followUps = useMemo(() => getFollowUpPendente(filteredRows, timelines), [filteredRows, timelines]);
  const churn = useMemo(() => getRiscoChurn(filteredRows, timelines), [filteredRows, timelines]);
  const resolucao = useMemo(() => getTempoResolucao(filteredRows, timelines), [filteredRows, timelines]);

  const enrichedClients = useMemo(
    () => enrichClientsWithFollowUp(reincidencias.clients, followUps.pendingPhones),
    [reincidencias.clients, followUps.pendingPhones],
  );

  const weeklyTrend = useMemo(
    () => combineWeeklySeries(reincidencias.weeklySeries, followUps.weeklySeries),
    [reincidencias.weeklySeries, followUps.weeklySeries],
  );

  const insights = useMemo(() => {
    const items: string[] = [];
    if (reincidencias.recurrentCount > 0) {
      const base = reincidencias.totalPhones ? reincidencias.recurrentCount / reincidencias.totalPhones : 0;
      items.push(
        t(
          `${reincidencias.recurrentCount} clientes ligaram ao menos 3 vezes em 7 dias (${formatPercent(base, 1)}) nos filtros aplicados.`,
          `${reincidencias.recurrentCount} clientes llamaron al menos 3 veces en 7 días (${formatPercent(base, 1)}) con los filtros aplicados.`,
        ),
      );
    } else {
      items.push(
        t(
          "Nenhum telefone apresenta três ligações em 7 dias com os filtros atuais.",
          "Ningún teléfono presenta tres llamadas en 7 días con los filtros actuales.",
        ),
      );
    }
    if (reincidencias.unresolvedComplaintCount > 0) {
      items.push(
        t(
          `${reincidencias.unresolvedComplaintCount} clientes seguem sem resolução após sentimento negativo, exigindo ação imediata.`,
          `${reincidencias.unresolvedComplaintCount} clientes siguen sin resolución tras sentimiento negativo; requieren acción inmediata.`,
        ),
      );
    }
    if (reincidencias.islandStats.length > 0) {
      const top = reincidencias.islandStats[0];
      items.push(
        t(
          `A ilha ${top.island} concentra ${formatNumber(top.recurrentCount)} reincidências (${formatPercent(top.percent, 1)} da base local).`,
          `La isla ${top.island} concentra ${formatNumber(top.recurrentCount)} reincidencias (${formatPercent(top.percent, 1)} de la base local).`,
        ),
      );
    }
    if (resolucao.averageDays && Number.isFinite(resolucao.averageDays)) {
      items.push(
        t(
          `O tempo médio até resolução está em ${resolucao.averageDays.toFixed(1)} dias.`,
          `El tiempo medio hasta la resolución está en ${resolucao.averageDays.toFixed(1)} días.`,
        ),
      );
    }
    if (reincidencias.angryRecurringCount > 0) {
      const variationLabel = formatSigned(reincidencias.angryRecurringVariation);
      items.push(
        t(
          `${reincidencias.angryRecurringCount} clientes apresentaram irritação recorrente; variação semanal de ${variationLabel} casos.`,
          `${reincidencias.angryRecurringCount} clientes mostraron irritación recurrente; variación semanal de ${variationLabel} casos.`,
        ),
      );
    }
    return items.slice(0, 5);
  }, [
    reincidencias.recurrentCount,
    reincidencias.totalPhones,
    reincidencias.unresolvedComplaintCount,
    reincidencias.islandStats,
    resolucao.averageDays,
    reincidencias.angryRecurringCount,
    reincidencias.angryRecurringVariation,
    t,
  ]);

  const handleExport = useCallback(() => {
    if (!enrichedClients.length) {
      return;
    }
    const headers = [
      "Telefone",
      "Qtde de ligacoes",
      "Primeira ligacao",
      "Ultima ligacao",
      "Sentimento medio",
      "Divergencia atual",
      "Follow-up pendente",
      "Ilha principal",
      "Reclamacao persistente",
      "Risco churn consecutivo",
    ];

    const csvEscape = (raw: unknown) => {
      if (raw === null || raw === undefined) return "";
      const text = String(raw).replace(/\r?\n+/g, " ").trim();
      return `"${text.replace(/"/g, '""')}"`;
    };

    const churnSet = new Set(churn.details.map((item) => item.phone));

    const rowsCsv = enrichedClients.map((client) => {
      const data = [
        client.phone,
        client.totalCalls,
        formatDate(client.firstDate),
        formatDate(client.lastDate),
        getSentimentLabel(client.averageSentiment),
        client.currentDivergence === 1 ? "Divergente" : "Nao divergente",
        client.followUpPending ? "Sim" : "Nao",
        client.primaryIsland,
        client.persistentComplaint ? "Sim" : "Nao",
        churnSet.has(client.phone) ? "Sim" : "Nao",
      ];
      return data.map(csvEscape).join(",");
    });

    const content = [headers.map(csvEscape).join(","), ...rowsCsv].join("\n");
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `reincidencias_riscos_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [enrichedClients, churn.details]);

  return (
    <div className="space-y-8">
      <SectionCard
        title={t("Reincidências e Riscos", "Reincidencias y Riesgos")}
        description={t(
          "Monitore padrões críticos de reincidência, follow-up, churn e riscos operacionais com filtros dedicados.",
          "Monitorea patrones críticos de reincidencia, follow-up, churn y riesgos operativos con filtros dedicados.",
        )}
      >
        <div className="grid gap-3 lg:grid-cols-5">
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300">
              {t("Ilha", "Isla")}
            </label>
            <select
              value={filters.island}
              onChange={(event) => handleFilterChange("island", event.target.value)}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
            >
              <option value="all">{t("Todas", "Todas")}</option>
              {islands.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300">
              {t("Status Real", "Estado Real")}
            </label>
            <select
              value={filters.status}
              onChange={(event) => handleFilterChange("status", event.target.value)}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
            >
              <option value="all">{t("Todos", "Todos")}</option>
              {statuses.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300">Pitch</label>
            <select
              value={filters.pitch}
              onChange={(event) => handleFilterChange("pitch", event.target.value)}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
            >
              <option value="all">{t("Todos", "Todos")}</option>
              {pitches.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300">{t("Data inicial", "Fecha inicial")}</label>
            <input
              type="date"
              value={filters.startDate}
              onChange={(event) => handleFilterChange("startDate", event.target.value)}
              className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-300">{t("Data final", "Fecha final")}</label>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={filters.endDate}
                onChange={(event) => handleFilterChange("endDate", event.target.value)}
                className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-accent-soft"
              />
              <button
                type="button"
                onClick={() => setFilters(DEFAULT_FILTERS)}
                className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-slate-200 transition hover:text-white"
                title={t("Limpar filtros", "Limpiar filtros")}
              >
                <RefreshCcw className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-400">
            {t(
              `${formatNumber(filteredRows.length)} chamadas consideradas após filtros`,
              `${formatNumber(filteredRows.length)} llamadas consideradas tras filtros`,
            )}
          </p>
          <button
            type="button"
            onClick={handleExport}
            className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/20"
          >
            <Download className="h-4 w-4" />
            {t("Exportar CSV", "Exportar CSV")}
          </button>
        </div>
      </SectionCard>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <SummaryCard
          icon={<PhoneCall className="h-4 w-4" />}
          label={t("Clientes reincidentes", "Clientes reincidentes")}
          primary={formatNumber(reincidencias.recurrentCount)}
          secondary={
            reincidencias.totalPhones
              ? t(
                  `${formatPercent(reincidencias.recurrentCount / Math.max(reincidencias.totalPhones, 1), 1)} da base monitorada.`,
                  `${formatPercent(reincidencias.recurrentCount / Math.max(reincidencias.totalPhones, 1), 1)} de la base monitoreada.`,
                )
              : undefined
          }
          tone={reincidencias.recurrentCount > 0 ? "warning" : "default"}
        />
        <SummaryCard
          icon={<ShieldAlert className="h-4 w-4" />}
          label={t("Reclamações não resolvidas", "Reclamaciones no resueltas")}
          primary={formatNumber(reincidencias.unresolvedComplaintCount)}
          secondary={t("Sentimento negativo + divergência mantida.", "Sentimiento negativo + divergencia mantenida.")}
          tone={reincidencias.unresolvedComplaintCount > 0 ? "critical" : "default"}
        />
        <SummaryCard
          icon={<UserCheck className="h-4 w-4" />}
          label={t("Follow-ups não cumpridos", "Follow-ups no cumplidos")}
          primary={formatNumber(followUps.pendingCases)}
          secondary={
            followUps.totalFollowUps
              ? t(
                  `${formatPercent(followUps.pendingPercent, 1)} dos follow-ups seguem em aberto.`,
                  `${formatPercent(followUps.pendingPercent, 1)} de los follow-ups siguen abiertos.`,
                )
              : undefined
          }
          tone={followUps.pendingCases > 0 ? "warning" : "default"}
        />
        <SummaryCard
          icon={<AlertTriangle className="h-4 w-4" />}
          label={t("Risco de churn alto", "Riesgo alto de churn")}
          primary={formatNumber(churn.totalHighRisk)}
          secondary={t("3 chamadas seguidas com sentimento negativo.", "3 llamadas seguidas con sentimiento negativo.")}
          tone={churn.totalHighRisk > 0 ? "critical" : "default"}
        />
        <SummaryCard
          icon={<Clock3 className="h-4 w-4" />}
          label={t("Tempo médio até resolução", "Tiempo medio hasta resolución")}
          primary={
            resolucao.averageDays && Number.isFinite(resolucao.averageDays)
              ? `${resolucao.averageDays.toFixed(1)} ${t("dias", "días")}`
              : "-"
          }
          secondary={t("Entre primeira ligação divergente e resolução.", "Entre la primera llamada divergente y la resolución.")}
        />
      </div>

      <SectionCard
        title={t("Indicadores críticos", "Indicadores críticos")}
        description={t(
          "Acompanhe reincidências, follow-ups improdutivos, pitch e script para priorizar planos de ação.",
          "Acompaña reincidencias, follow-ups improductivos, pitch y script para priorizar planes de acción.",
        )}
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <MetricItem
            icon={<Layers className="h-5 w-5 text-accent-soft" />}
            label={t("Clientes reincidentes por ilha", "Clientes reincidentes por isla")}
            value={reincidencias.islandStats.length ? formatNumber(reincidencias.islandStats[0].recurrentCount) : "-"}
            helper={
              reincidencias.islandStats.length
                ? t(
                    `${reincidencias.islandStats[0].island}: ${formatPercent(reincidencias.islandStats[0].percent, 1)} da base.`,
                    `${reincidencias.islandStats[0].island}: ${formatPercent(reincidencias.islandStats[0].percent, 1)} de la base.`,
                  )
                : t("Nenhuma ilha com reincidências dentro dos filtros.", "Ninguna isla con reincidencias en los filtros.")
            }
          />
          <MetricItem
            icon={<ShieldAlert className="h-5 w-5 text-rose-300" />}
            label={t("Reclamações persistentes", "Reclamaciones persistentes")}
            value={formatNumber(reincidencias.persistentComplaintCount)}
            helper={
              reincidencias.persistentComplaintCount
                ? t(
                    `${formatPercent(reincidencias.persistentComplaintPercent, 1)} dos diálogos conectados.`,
                    `${formatPercent(reincidencias.persistentComplaintPercent, 1)} de los diálogos conectados.`,
                  )
                : t("Sem casos persistentes com sentimento crítico.", "Sin casos persistentes con sentimiento crítico.")
            }
          />
          <MetricItem
            icon={<Link2 className="h-5 w-5 text-amber-200" />}
            label={t("Follow-up improdutivo", "Follow-up improductivo")}
            value={formatNumber(followUps.improductiveCases)}
            helper={
              followUps.totalFollowUps
                ? t(
                    `${formatPercent(followUps.improductivePercent, 1)} retornaram antes de 5 dias.`,
                    `${formatPercent(followUps.improductivePercent, 1)} regresaron antes de 5 días.`,
                  )
                : t("Nenhum follow-up agendado neste recorte.", "No hay follow-ups agendados en este recorte.")
            }
          />
          <MetricItem
            icon={<Flame className="h-5 w-5 text-rose-200" />}
            label={t("Clientes irritados recorrentes", "Clientes irritados recurrentes")}
            value={formatNumber(reincidencias.angryRecurringCount)}
            helper={t(
              `Variação semanal: ${formatSigned(reincidencias.angryRecurringVariation)} casos.`,
              `Variación semanal: ${formatSigned(reincidencias.angryRecurringVariation)} casos.`,
            )}
          />
          <MetricItem
            icon={<BarChart3 className="h-5 w-5 text-emerald-200" />}
            label={t("Pitch inconsistente", "Pitch inconsistente")}
            value={formatNumber(reincidencias.pitchInconsistentCount)}
            helper={
              reincidencias.pitchInconsistentCount
                ? t(
                    "Clientes receberam abordagens diferentes entre ligações.",
                    "Clientes recibieron abordajes diferentes entre llamadas.",
                  )
                : t("Pitch consistente para todos os reincidentes.", "Pitch consistente para todos los reincidentes.")
            }
          />
          <MetricItem
            icon={<Brain className="h-5 w-5 text-sky-200" />}
            label={t("Script não seguido em reincidências", "Script no seguido en reincidencias")}
            value={formatNumber(reincidencias.scriptNeverAlignedCount)}
            helper={
              reincidencias.scriptNeverAlignedCount
                ? t(
                    "Nenhuma das ligações do cliente ficou alinhada ao script.",
                    "Ninguna de las llamadas del cliente se alineó al script.",
                  )
                : t("Há pelo menos uma ligação alinhada ao script para cada reincidente.", "Existe al menos una llamada alineada al script por reincidente.")
            }
          />
        </div>
      </SectionCard>

      <SectionCard
        title={t("Resumo inteligente", "Resumen inteligente")}
        description={t(
          "Insights gerados automaticamente com base nas métricas do recorte atual.",
          "Insights generados automáticamente con base en las métricas del recorte actual.",
        )}
      >
        <ul className="space-y-2 text-sm text-slate-200">
          {insights.map((insight, index) => (
            <li key={index} className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 rounded-full bg-accent-soft" />
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard
          title={t("Reincidências por ilha", "Reincidencias por isla")}
          description={t(
            "Distribuição de clientes que ligaram 3+ vezes em 7 dias por ilha operacional.",
            "Distribución de clientes que llamaron 3+ veces en 7 días por isla operativa.",
          )}
        >
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reincidencias.islandStats.filter((item) => item.recurrentCount > 0)}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,232,240,0.1)" />
                <XAxis dataKey="island" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip
                  contentStyle={{
                    background: "#020617",
                    borderRadius: "12px",
                    border: "1px solid rgba(148,163,184,0.2)",
                    color: "#e2e8f0",
                  }}
                  labelFormatter={(label) => `${t("Ilha", "Isla")}: ${label}`}
                  formatter={(value: number) => [formatNumber(value), t("Reincidências", "Reincidencias")]}
                />
                <Bar dataKey="recurrentCount" fill="url(#reincidenceGradient)" radius={[12, 12, 0, 0]} />
                <defs>
                  <linearGradient id="reincidenceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.9} />
                    <stop offset="100%" stopColor="#1e293b" stopOpacity={0.4} />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard
          title={t("Evolução semanal", "Evolución semanal")}
          description={t(
            "Volume de reincidências e follow-ups pendentes em cada semana.",
            "Volumen de reincidencias y follow-ups pendientes en cada semana.",
          )}
        >
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={weeklyTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(226,232,240,0.1)" />
                <XAxis
                  dataKey="label"
                  stroke="#94a3b8"
                  tickFormatter={(value: string) => value.replace("W", " W")}
                />
                <YAxis stroke="#94a3b8" />
                <Legend />
                <Tooltip
                  contentStyle={{
                    background: "#020617",
                    borderRadius: "12px",
                    border: "1px solid rgba(148,163,184,0.2)",
                    color: "#e2e8f0",
                  }}
                  formatter={(value: number, name: string) => [formatNumber(value), name]}
                />
                <Line type="monotone" dataKey="reincidentes" name={t("Reincidências", "Reincidencias")} stroke="#38bdf8" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="followUps" name={t("Follow-ups pendentes", "Follow-ups pendientes")} stroke="#f97316" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title={t("Clientes reincidentes (detalhe)", "Clientes reincidentes (detalle)")}
        description={t(
          "Lista consolidada de telefones reincidentes com sentimento médio, follow-up e status de divergência.",
          "Lista consolidada de teléfonos reincidentes con sentimiento medio, follow-up y estado de divergencia.",
        )}
      >
        <div className="overflow-hidden rounded-3xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-sm text-slate-200">
            <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3 text-left">{t("Telefone", "Teléfono")}</th>
                <th className="px-4 py-3 text-left">{t("Qtde ligações", "Cantidad de llamadas")}</th>
                <th className="px-4 py-3 text-left">{t("Última data", "Última fecha")}</th>
                <th className="px-4 py-3 text-left">{t("Sentimento médio", "Sentimiento medio")}</th>
                <th className="px-4 py-3 text-left">{t("Divergência atual", "Divergencia actual")}</th>
                <th className="px-4 py-3 text-left">{t("Follow-up pendente", "Follow-up pendiente")}</th>
                <th className="px-4 py-3 text-left">{t("Ilha", "Isla")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 bg-white/0">
              {enrichedClients.map((client) => (
                <tr key={client.phone}>
                  <td className="px-4 py-3 font-semibold text-white">{client.phone}</td>
                  <td className="px-4 py-3">{formatNumber(client.totalCalls)}</td>
                  <td className="px-4 py-3 text-slate-300">{formatDate(client.lastDate)}</td>
                  <td className="px-4 py-3">{getSentimentLabel(client.averageSentiment)}</td>
                  <td className="px-4 py-3">
                    {getDivergenceLabel(client.currentDivergence, t)}
                  </td>
                  <td className="px-4 py-3">
                    {client.followUpPending ? t("Sim", "Sí") : t("Não", "No")}
                  </td>
                  <td className="px-4 py-3 text-slate-300">{client.primaryIsland}</td>
                </tr>
              ))}
              {enrichedClients.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-400">
                    {t("Nenhum cliente reincidente encontrado com os filtros atuais.", "No se encontraron clientes reincidentes con los filtros actuales.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

export default ReincidenciasTab;
