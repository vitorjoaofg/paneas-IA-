import { TrendingUp, AlertTriangle, Users, Timer, Activity } from "lucide-react";
import clsx from "clsx";
import type { SummaryMetrics } from "../../utils/executiveMetrics";
import { useTranslate } from "../../i18n";
import { formatNumber, formatPercent } from "../../utils/numberFormat";

interface ExecutiveMetricsProps {
  data: SummaryMetrics;
}

interface MetricItem {
  key: string;
  label: string;
  value: string;
  helper?: string;
  accent: "primary" | "warning" | "success" | "danger" | "neutral";
  icon: React.ReactNode;
}

const accentClasses: Record<MetricItem["accent"], string> = {
  primary: "border-accent-soft/40 bg-accent-soft/10 text-slate-100",
  warning: "border-amber-400/40 bg-amber-400/10 text-amber-100",
  success: "border-emerald-400/40 bg-emerald-400/10 text-emerald-100",
  danger: "border-rose-400/40 bg-rose-400/10 text-rose-100",
  neutral: "border-white/10 bg-white/5 text-slate-200",
};

const iconWrapperClasses: Record<MetricItem["accent"], string> = {
  primary: "bg-accent-soft/20 text-accent-soft",
  warning: "bg-amber-400/20 text-amber-300",
  success: "bg-emerald-400/20 text-emerald-200",
  danger: "bg-rose-400/20 text-rose-200",
  neutral: "bg-white/10 text-slate-200",
};

export const ExecutiveMetrics = ({ data }: ExecutiveMetricsProps) => {
  const t = useTranslate();

  const metrics: MetricItem[] = [
    {
      key: "total",
      label: t("Total de chamadas", "Total de llamadas"),
      value: formatNumber(data.totalCalls),
      helper: t("Base analisada no recorte atual.", "Base analizada en el recorte actual."),
      accent: "primary",
      icon: <Users className="h-4 w-4" />,
    },
    {
      key: "divergence",
      label: t("Divergências", "Divergencias"),
      value: formatPercent(data.divergenceRate, 1),
      helper: t("Comparativo Izzi × Realidade.", "Comparativo Izzi × Realidad."),
      accent: data.divergenceRate > 0.5 ? "danger" : "neutral",
      icon: <AlertTriangle className="h-4 w-4" />,
    },
    {
      key: "follow-up",
      label: t("Follow-up efetivado", "Seguimiento comprometido"),
      value: formatPercent(data.followUpRate, 1),
      accent: "success",
      helper: t("Chamadas que terminaram com compromisso ativo.", "Llamadas que terminaron con compromiso activo."),
      icon: <TrendingUp className="h-4 w-4" />,
    },
    {
      key: "anger",
      label: t("Clientes irritados", "Clientes irritados"),
      value: formatPercent(data.angryRate, 1),
      accent: data.angryRate > 0.1 ? "warning" : "neutral",
      helper: t("Detecções com palavras-chave críticas.", "Detecciones con palabras clave críticas."),
      icon: <AlertTriangle className="h-4 w-4" />,
    },
    {
      key: "duration",
      label: t("Tempo médio", "Tiempo medio"),
      value: `${formatNumber(data.averageDurationMinutes, 2)} ${t("min", "min")}`,
      helper: t("Média da duração transcrita.", "Promedio de duración transcrita."),
      accent: "neutral",
      icon: <Timer className="h-4 w-4" />,
    },
    {
      key: "engagement",
      label: t("Engajamento médio", "Compromiso medio"),
      value: formatNumber(data.averageEngagement, 2),
      helper: t("Fala do cliente / tempo total.", "Habla del cliente / tiempo total."),
      accent: data.averageEngagement < 0.4 ? "warning" : "success",
      icon: <Activity className="h-4 w-4" />,
    },
    {
      key: "sentiment",
      label: t("Sentimento médio", "Sentimiento medio"),
      value: formatNumber(data.averageSentiment, 2),
      helper: t("Escala -1 a 1 (negativo / positivo).", "Escala -1 a 1 (negativo / positivo)."),
      accent: data.averageSentiment < 0 ? "danger" : "primary",
      icon: <TrendingUp className="h-4 w-4" />,
    },
  ];

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div
          key={metric.key}
          className={clsx(
            "flex flex-col gap-3 rounded-2xl border px-4 py-4 shadow-inner backdrop-blur",
            accentClasses[metric.accent],
          )}
        >
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-300">{metric.label}</p>
            <span
              className={clsx(
                "flex h-9 w-9 items-center justify-center rounded-2xl border",
                iconWrapperClasses[metric.accent],
              )}
            >
              {metric.icon}
            </span>
          </div>
          <p className="text-2xl font-semibold">{metric.value}</p>
          {metric.helper && <p className="text-xs text-slate-300">{metric.helper}</p>}
        </div>
      ))}
    </div>
  );
};
