import { AlertCircle, AlertTriangle, Flame } from "lucide-react";
import type { JSX } from "react";
import type { ConversationAlert } from "../../types";
import { SectionCard } from "./SectionCard";

interface AlertsPanelProps {
  alerts: ConversationAlert[];
}

const ICON_BY_LEVEL: Record<ConversationAlert["level"], JSX.Element> = {
  critical: <Flame className="h-4 w-4" />,
  warning: <AlertTriangle className="h-4 w-4" />,
  info: <AlertCircle className="h-4 w-4" />,
};

const COLOR_BY_LEVEL: Record<ConversationAlert["level"], string> = {
  critical: "border-rose-500/40 bg-rose-500/10 text-rose-100",
  warning: "border-amber-400/40 bg-amber-500/10 text-amber-100",
  info: "border-sky-400/40 bg-sky-500/10 text-sky-100",
};

export function AlertsPanel({ alerts }: AlertsPanelProps) {
  return (
    <SectionCard
      title="Alertas inteligentes"
      subtitle="Detecções automáticas criadas a partir da chamada e histórico recente"
    >
      {alerts.length === 0 ? (
        <p className="text-sm text-slate-400">Nenhum alerta relevante para esta chamada.</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`flex items-start gap-3 rounded-2xl border px-3 py-2 text-xs ${COLOR_BY_LEVEL[alert.level]}`}
            >
              <span className="mt-1 opacity-80">{ICON_BY_LEVEL[alert.level]}</span>
              <div className="flex-1 space-y-1">
                <p className="font-semibold leading-tight text-slate-50">{alert.message}</p>
                {alert.hint && <p className="text-[11px] text-slate-200/80">{alert.hint}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
