import { useMemo } from "react";
import { TrendingUp, TrendingDown, Minus, Calendar } from "lucide-react";
import type { PerCallDetail, DashboardData } from "../types";
import { useTranslate } from "../i18n";
import { formatNumber, formatPercent } from "../utils/numberFormat";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from "recharts";

interface MonthlyComparisonTabProps {
  filtered: PerCallDetail[];
  data: DashboardData | null;
}

interface MonthMetrics {
  month: string;
  monthLabel: string;
  totalCalls: number;
  connectedCalls: number;
  connectedRate: number;
  divergentCalls: number;
  divergenceRate: number;
  avgDuration: number;
  avgEngagement: number;
  avgSentimentCustomer: number;
  avgSentimentAgent: number;
  scriptAlignedRate: number;
  sourceAwareRate: number;
  pitchSatisfactoryRate: number;
  followUpRate: number;
  likelySalesRate: number;
  objectionHandledRate: number;
  angerRate: number;
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-white/5 to-white/[0.02] p-6 shadow-2xl backdrop-blur-xl">
      {children}
    </div>
  );
}

export function MonthlyComparisonTab({ filtered, data }: MonthlyComparisonTabProps) {
  const t = useTranslate();

  const monthlyMetrics = useMemo<MonthMetrics[]>(() => {
    if (!data) return [];

    // Group calls by month
    const monthGroups = new Map<string, PerCallDetail[]>();

    filtered.forEach((row) => {
      const dateParts = row.call_datetime?.split(" ")[0]?.split("/");
      if (dateParts && dateParts.length === 3) {
        const month = dateParts[1];
        const year = dateParts[2];
        const key = `${month}/${year}`;

        if (!monthGroups.has(key)) {
          monthGroups.set(key, []);
        }
        monthGroups.get(key)!.push(row);
      }
    });

    // Calculate metrics for each month
    const metrics: MonthMetrics[] = [];

    monthGroups.forEach((calls, key) => {
      const [month, year] = key.split("/");
      const monthNames = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
      const monthLabel = `${monthNames[parseInt(month) - 1]}/${year}`;

      const totalCalls = calls.length;
      const connectedCalls = calls.filter(c => c.status_real_detectado === "dialogo_conectado").length;
      const divergentCalls = calls.filter(c => c.divergente === 1).length;

      const avgDuration = calls.reduce((acc, c) => acc + c.duration_seconds_transcript, 0) / totalCalls;
      const avgEngagement = calls.reduce((acc, c) => acc + c.customer_engagement_score, 0) / totalCalls;
      const avgSentimentCustomer = calls.reduce((acc, c) => acc + c.customer_sentiment_score, 0) / totalCalls;
      const avgSentimentAgent = calls.reduce((acc, c) => acc + c.agent_sentiment_score, 0) / totalCalls;

      const scriptApplicable = calls.filter(c => c.script_keyword_total > 0).length;
      const scriptAligned = calls.filter(c => c.script_alignment_label === "aligned").length;

      const sourceAware = calls.filter(c => c.operator_source_awareness === 1).length;
      const pitchSatisfactory = calls.filter(c => {
        const label = c.sales_pitch_label?.toLowerCase();
        return label === "satisfactory" || label === "satisfatório" || label === "satisfatorio";
      }).length;
      const followUp = calls.filter(c => c.follow_up_commitment === 1).length;
      const likelySales = calls.filter(c => c.likely_sale === 1).length;
      const objectionHandled = calls.filter(c => c.objection_handled === 1).length;
      const anger = calls.filter(c => c.customer_anger_detected === 1).length;

      metrics.push({
        month: key,
        monthLabel,
        totalCalls,
        connectedCalls,
        connectedRate: totalCalls > 0 ? connectedCalls / totalCalls : 0,
        divergentCalls,
        divergenceRate: totalCalls > 0 ? divergentCalls / totalCalls : 0,
        avgDuration,
        avgEngagement,
        avgSentimentCustomer,
        avgSentimentAgent,
        scriptAlignedRate: scriptApplicable > 0 ? scriptAligned / scriptApplicable : 0,
        sourceAwareRate: connectedCalls > 0 ? sourceAware / connectedCalls : 0,
        pitchSatisfactoryRate: connectedCalls > 0 ? pitchSatisfactory / connectedCalls : 0,
        followUpRate: connectedCalls > 0 ? followUp / connectedCalls : 0,
        likelySalesRate: connectedCalls > 0 ? likelySales / connectedCalls : 0,
        objectionHandledRate: connectedCalls > 0 ? objectionHandled / connectedCalls : 0,
        angerRate: connectedCalls > 0 ? anger / connectedCalls : 0,
      });
    });

    // Sort by year/month
    metrics.sort((a, b) => {
      const [aMonth, aYear] = a.month.split("/").map(Number);
      const [bMonth, bYear] = b.month.split("/").map(Number);
      return aYear !== bYear ? aYear - bYear : aMonth - bMonth;
    });

    return metrics;
  }, [data, filtered]);

  const comparisonCards = useMemo(() => {
    if (monthlyMetrics.length < 2) return [];

    const latest = monthlyMetrics[monthlyMetrics.length - 1];
    const previous = monthlyMetrics[monthlyMetrics.length - 2];

    const calculateChange = (current: number, prev: number) => {
      if (prev === 0) return 0;
      return ((current - prev) / prev);
    };

    return [
      {
        label: t("Chamadas Conectadas", "Llamadas Conectadas"),
        current: formatPercent(latest.connectedRate),
        change: calculateChange(latest.connectedRate, previous.connectedRate),
        isPercentage: true,
      },
      {
        label: t("Taxa de Divergência", "Tasa de Divergencia"),
        current: formatPercent(latest.divergenceRate),
        change: calculateChange(latest.divergenceRate, previous.divergenceRate),
        isPercentage: true,
        inverse: true, // Lower is better
      },
      {
        label: t("Engajamento Médio", "Compromiso Promedio"),
        current: latest.avgEngagement.toFixed(2),
        change: calculateChange(latest.avgEngagement, previous.avgEngagement),
        isPercentage: false,
      },
      {
        label: t("Pitch Satisfatório", "Pitch Satisfactorio"),
        current: formatPercent(latest.pitchSatisfactoryRate),
        change: calculateChange(latest.pitchSatisfactoryRate, previous.pitchSatisfactoryRate),
        isPercentage: true,
      },
      {
        label: t("Follow-up Agendado", "Seguimiento Programado"),
        current: formatPercent(latest.followUpRate),
        change: calculateChange(latest.followUpRate, previous.followUpRate),
        isPercentage: true,
      },
      {
        label: t("Provável Venda", "Venta Probable"),
        current: formatPercent(latest.likelySalesRate),
        change: calculateChange(latest.likelySalesRate, previous.likelySalesRate),
        isPercentage: true,
      },
    ];
  }, [monthlyMetrics, t]);

  if (!data || monthlyMetrics.length === 0) {
    return (
      <div className="space-y-8">
        <Card>
          <p className="text-center text-slate-400">
            {t("Sem dados suficientes para comparação mensal.", "No hay datos suficientes para comparación mensual.")}
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <Card>
        <div className="flex items-center gap-3">
          <Calendar className="h-6 w-6 text-accent-soft" />
          <div>
            <h2 className="text-2xl font-semibold text-slate-50">
              {t("Evolução Mensal", "Evolución Mensual")}
            </h2>
            <p className="text-sm text-slate-400">
              {t(
                `Comparação de métricas entre ${monthlyMetrics.length} mês(es) analisado(s)`,
                `Comparación de métricas entre ${monthlyMetrics.length} mes(es) analizados`
              )}
            </p>
          </div>
        </div>
      </Card>

      {/* Comparison Cards */}
      {monthlyMetrics.length >= 2 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {comparisonCards.map((card, idx) => {
            const isPositive = card.inverse ? card.change < 0 : card.change > 0;
            const isNeutral = Math.abs(card.change) < 0.01;

            return (
              <Card key={idx}>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{card.label}</p>
                <div className="mt-2 flex items-end justify-between">
                  <span className="text-3xl font-semibold text-slate-50">{card.current}</span>
                  <div className="flex items-center gap-1">
                    {isNeutral ? (
                      <Minus className="h-4 w-4 text-slate-400" />
                    ) : isPositive ? (
                      <TrendingUp className="h-4 w-4 text-green-400" />
                    ) : (
                      <TrendingDown className="h-4 w-4 text-rose-400" />
                    )}
                    <span
                      className={`text-sm font-medium ${
                        isNeutral ? "text-slate-400" : isPositive ? "text-green-400" : "text-rose-400"
                      }`}
                    >
                      {isNeutral ? "0%" : formatPercent(Math.abs(card.change))}
                    </span>
                  </div>
                </div>
                <p className="mt-1 text-xs text-slate-400">
                  {t("vs. mês anterior", "vs. mes anterior")}
                </p>
              </Card>
            );
          })}
        </div>
      )}

      {/* Volume Chart */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-50">
          {t("Volume de Chamadas por Mês", "Volumen de Llamadas por Mes")}
        </h3>
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlyMetrics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
              <XAxis dataKey="monthLabel" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}
                labelStyle={{ color: "#f1f5f9" }}
              />
              <Legend />
              <Bar dataKey="totalCalls" fill="#60a5fa" name={t("Total", "Total")} />
              <Bar dataKey="connectedCalls" fill="#34d399" name={t("Conectadas", "Conectadas")} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Quality Metrics Chart */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-50">
          {t("Evolução de Métricas de Qualidade", "Evolución de Métricas de Calidad")}
        </h3>
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={monthlyMetrics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
              <XAxis dataKey="monthLabel" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" tickFormatter={(value) => formatPercent(value)} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}
                labelStyle={{ color: "#f1f5f9" }}
                formatter={(value: number) => formatPercent(value)}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="connectedRate"
                stroke="#34d399"
                strokeWidth={2}
                name={t("Taxa Conexão", "Tasa Conexión")}
              />
              <Line
                type="monotone"
                dataKey="divergenceRate"
                stroke="#f87171"
                strokeWidth={2}
                name={t("Taxa Divergência", "Tasa Divergencia")}
              />
              <Line
                type="monotone"
                dataKey="pitchSatisfactoryRate"
                stroke="#60a5fa"
                strokeWidth={2}
                name={t("Pitch Satisfatório", "Pitch Satisfactorio")}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Sales Funnel Evolution */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-50">
          {t("Evolução do Funil de Vendas", "Evolución del Embudo de Ventas")}
        </h3>
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={monthlyMetrics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
              <XAxis dataKey="monthLabel" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" tickFormatter={(value) => formatPercent(value)} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px" }}
                labelStyle={{ color: "#f1f5f9" }}
                formatter={(value: number) => formatPercent(value)}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="pitchSatisfactoryRate"
                stroke="#22d3ee"
                strokeWidth={2}
                name={t("Pitch Satisfatório", "Pitch Satisfactorio")}
              />
              <Line
                type="monotone"
                dataKey="followUpRate"
                stroke="#60a5fa"
                strokeWidth={2}
                name={t("Follow-up", "Seguimiento")}
              />
              <Line
                type="monotone"
                dataKey="likelySalesRate"
                stroke="#4ade80"
                strokeWidth={3}
                name={t("Provável Venda", "Venta Probable")}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Detailed Table */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-50">
          {t("Tabela Detalhada por Mês", "Tabla Detallada por Mes")}
        </h3>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-slate-400">
                <th className="pb-3">{t("Mês", "Mes")}</th>
                <th className="pb-3 text-right">{t("Total", "Total")}</th>
                <th className="pb-3 text-right">{t("Conectadas", "Conectadas")}</th>
                <th className="pb-3 text-right">{t("Divergência", "Divergencia")}</th>
                <th className="pb-3 text-right">{t("Engajamento", "Compromiso")}</th>
                <th className="pb-3 text-right">{t("Pitch OK", "Pitch OK")}</th>
                <th className="pb-3 text-right">{t("Follow-up", "Seguimiento")}</th>
                <th className="pb-3 text-right">{t("Venda Provável", "Venta Probable")}</th>
              </tr>
            </thead>
            <tbody>
              {monthlyMetrics.map((month) => (
                <tr key={month.month} className="border-b border-white/5">
                  <td className="py-3 font-medium text-slate-50">{month.monthLabel}</td>
                  <td className="py-3 text-right text-slate-300">{formatNumber(month.totalCalls)}</td>
                  <td className="py-3 text-right text-slate-300">{formatPercent(month.connectedRate)}</td>
                  <td className="py-3 text-right text-rose-300">{formatPercent(month.divergenceRate)}</td>
                  <td className="py-3 text-right text-slate-300">{month.avgEngagement.toFixed(2)}</td>
                  <td className="py-3 text-right text-cyan-300">{formatPercent(month.pitchSatisfactoryRate)}</td>
                  <td className="py-3 text-right text-blue-300">{formatPercent(month.followUpRate)}</td>
                  <td className="py-3 text-right text-green-400">{formatPercent(month.likelySalesRate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
