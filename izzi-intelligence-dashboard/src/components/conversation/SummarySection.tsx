import type { PerCallDetail } from "../../types";
import { SectionCard } from "./SectionCard";

interface SummarySectionProps {
  call: PerCallDetail | null;
  summary: string[];
  options: { value: string; label: string }[];
  onSelectCall: (callId: string) => void;
}

export function SummarySection({ call, summary, options, onSelectCall }: SummarySectionProps) {
  if (!call) {
    return (
      <SectionCard title="Resumo automático" subtitle="Selecione uma chamada para visualizar o resumo gerado">
        <p className="text-sm text-slate-400">Nenhuma chamada selecionada.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title="Resumo automático da conversa"
      subtitle={`Chamada ${call.call_id} · ${call.call_datetime ?? "data não informada"}`}
      actions={
        <select
          value={call.call_id}
          onChange={(event) => onSelectCall(event.target.value)}
          className="rounded-2xl border border-white/10 bg-black/30 px-3 py-1 text-xs text-slate-100"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      }
      className="space-y-4"
    >
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="flex flex-col gap-1 text-sm text-slate-300">
          <span className="font-semibold text-slate-100">Telefone</span>
          <span>{call.phone_number ?? "—"}</span>
          <span className="font-semibold text-slate-100">Ilha / Exec</span>
          <span>
            {call.island ?? "—"} · {call.exec_id ?? "sem exec"}
          </span>
          <span className="font-semibold text-slate-100">Atendente</span>
          <span>{call.operator ?? "não identificado"}</span>
        </div>
        <div className="flex flex-col gap-1 text-sm text-slate-300">
          <span className="font-semibold text-slate-100">Sentimento cliente</span>
          <span>
            {call.customer_sentiment_label} · score {call.customer_sentiment_score.toFixed(2)}
          </span>
          <span className="font-semibold text-slate-100">Engajamento</span>
          <span>{call.customer_engagement_score.toFixed(2)}</span>
          <span className="font-semibold text-slate-100">Silêncio</span>
          <span>{(call.silence_ratio * 100).toFixed(1)}%</span>
        </div>
      </div>
      <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
        <ul className="list-disc space-y-2 pl-5">
          {summary.map((line, index) => (
            <li key={index}>{line}</li>
          ))}
        </ul>
      </div>
    </SectionCard>
  );
}
