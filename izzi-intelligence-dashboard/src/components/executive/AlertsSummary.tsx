import type { AlertInfo } from "../../utils/executiveMetrics";
import { useTranslate } from "../../i18n";
import { AlertTriangle, ShieldAlert, Info } from "lucide-react";
import clsx from "clsx";

interface AlertsSummaryProps {
  alerts: AlertInfo[];
}

const iconBySeverity: Record<AlertInfo["severity"], React.ReactNode> = {
  critical: <ShieldAlert className="h-4 w-4" />,
  warning: <AlertTriangle className="h-4 w-4" />,
  info: <Info className="h-4 w-4" />,
};

const colorBySeverity: Record<AlertInfo["severity"], string> = {
  critical: "border-rose-500/40 bg-rose-500/10 text-rose-100",
  warning: "border-amber-400/40 bg-amber-400/10 text-amber-100",
  info: "border-sky-400/40 bg-sky-400/10 text-sky-100",
};

export const AlertsSummary = ({ alerts }: AlertsSummaryProps) => {
  const t = useTranslate();

  if (!alerts.length) {
    return (
      <div className="rounded-2xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-4 text-sm text-emerald-100 shadow-inner">
        {t("Nenhum alerta crítico encontrado no recorte atual.", "No se encontraron alertas críticas en este recorte.")}
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={clsx(
            "flex items-start gap-3 rounded-2xl border px-4 py-4 text-sm shadow-inner backdrop-blur",
            colorBySeverity[alert.severity],
          )}
        >
          <span className="mt-1 rounded-full border border-white/10 bg-white/10 p-2 text-current">
            {iconBySeverity[alert.severity]}
          </span>
          <p>{alert.message}</p>
        </div>
      ))}
    </div>
  );
};
