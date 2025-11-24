import {
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";
import type { StatusDistributionItem, DivergenceDonutItem, TimelinePoint } from "../../utils/executiveMetrics";
import { useTranslate } from "../../i18n";
import { formatNumber, formatPercent } from "../../utils/numberFormat";

interface ExecutiveChartsProps {
  statusDistribution: StatusDistributionItem[];
  divergenceDonut: DivergenceDonutItem[];
  timeline: TimelinePoint[];
}

const donutColors = {
  divergent: "#fda4af",
  aligned: "#34d399",
};

export const ExecutiveCharts = ({
  statusDistribution,
  divergenceDonut,
  timeline,
}: ExecutiveChartsProps) => {
  const t = useTranslate();

  const donutData = divergenceDonut.map((item) => ({ label: item.label, value: item.value }));

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner backdrop-blur">
        <h4 className="text-sm font-semibold text-slate-100">{t("Distribuição por status real", "Distribución por estado real")}</h4>
        <p className="text-xs text-slate-400">{t("Quantas chamadas terminam em cada classificação real detectada.", "Cuántas llamadas terminan en cada clasificación real detectada.")}</p>
        <div className="mt-3 h-60">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={statusDistribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="status" stroke="#cbd5f5" tick={{ fontSize: 11 }} />
              <YAxis stroke="#cbd5f5" tickFormatter={(value: number) => formatNumber(value)} />
              <Tooltip
                contentStyle={{
                  background: "rgba(12,16,26,0.9)",
                  border: "1px solid rgba(148,163,184,0.4)",
                  borderRadius: 12,
                  color: "#E2E8F0",
                }}
                formatter={(value: number, _name, payload) => [
                  `${formatNumber(value)} (${formatPercent(payload?.payload?.percent ?? 0, 1)})`,
                  t("Chamadas", "Llamadas"),
                ]}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} fill="rgba(79, 70, 229, 0.85)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner backdrop-blur">
        <h4 className="text-sm font-semibold text-slate-100">{t("Divergente vs não divergente", "Divergente vs no divergente")}</h4>
        <p className="text-xs text-slate-400">{t("Proporção geral do recorte analisado.", "Proporción general del recorte analizado.")}</p>
        <div className="mt-3 h-60">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={donutData} dataKey="value" nameKey="label" innerRadius={60} outerRadius={90} paddingAngle={4}>
                {donutData.map((entry) => (
                  <Cell
                    key={entry.label}
                    fill={entry.label === "divergent" ? donutColors.divergent : donutColors.aligned}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "rgba(12,16,26,0.9)",
                  border: "1px solid rgba(148,163,184,0.4)",
                  borderRadius: 12,
                  color: "#E2E8F0",
                }}
                formatter={(value: number, name: string) => [
                  formatNumber(value),
                  name === "divergent" ? t("Divergente", "Divergente") : t("Não divergente", "No divergente"),
                ]}
              />
              <Legend
                formatter={(value: string) =>
                  value === "divergent" ? t("Divergente", "Divergente") : t("Não divergente", "No divergente")
                }
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner backdrop-blur lg:col-span-2">
        <h4 className="text-sm font-semibold text-slate-100">{t("Evolução de divergência e follow-up", "Evolución de divergencia y seguimiento")}</h4>
        <p className="text-xs text-slate-400">
          {t("Linha do tempo diária com taxa de divergência e follow-up.", "Línea temporal diaria con tasa de divergencia y seguimiento.")}
        </p>
        <div className="mt-3 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="date" stroke="#cbd5f5" tick={{ fontSize: 11 }} />
              <YAxis
                stroke="#cbd5f5"
                tickFormatter={(value: number) => formatPercent(value, 0)}
                domain={[0, 1]}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(12,16,26,0.9)",
                  border: "1px solid rgba(148,163,184,0.4)",
                  borderRadius: 12,
                  color: "#E2E8F0",
                }}
                formatter={(value: number, name: string) => [
                  formatPercent(value, 1),
                  name === "divergenceRate" ? t("Divergência", "Divergencia") : t("Follow-up", "Seguimiento"),
                ]}
              />
              <Legend
                formatter={(value: string) =>
                  value === "divergenceRate" ? t("Divergência", "Divergencia") : t("Follow-up", "Seguimiento")
                }
              />
              <Line type="monotone" dataKey="divergenceRate" stroke="#f472b6" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="followUpRate" stroke="#38bdf8" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
