import { useEffect, useMemo, useState } from "react";
import type { ConversationEvent, TranscriptSegment } from "../../types";
import { SectionCard } from "./SectionCard";
import { ConversationTimeline } from "./ConversationTimeline";

interface TimelineSectionProps {
  segments: TranscriptSegment[];
  events: ConversationEvent[];
  loading?: boolean;
}

export function TimelineSection({ segments, events, loading }: TimelineSectionProps) {
  const [selected, setSelected] = useState<ConversationEvent | null>(null);

  useEffect(() => {
    if (events.length === 0) {
      setSelected(null);
    } else if (!selected || !events.some((event) => event.id === selected.id)) {
      setSelected(events[0]);
    }
  }, [events, selected]);

  const toneLabel = useMemo(() => {
    if (!selected) return "";
    if (selected.tone === "positive") return "Evento positivo";
    if (selected.tone === "negative") return "Evento crítico";
    return "Evento neutro";
  }, [selected]);

  return (
    <SectionCard
      title="Linha do tempo da conversa"
      subtitle="Eventos críticos destacados a partir do sentimento, engajamento e transcrição"
      className="space-y-4"
    >
      {loading ? (
        <p className="text-sm text-slate-400">Carregando segmentos da chamada...</p>
      ) : segments.length === 0 ? (
        <p className="text-sm text-slate-400">Nenhum segmento disponível para esta chamada.</p>
      ) : (
        <ConversationTimeline
          segments={segments}
          events={events}
          selectedId={selected?.id}
          onSelect={setSelected}
        />
      )}

      {selected && (
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-400">{toneLabel}</p>
          <h4 className="mt-1 text-base font-semibold text-slate-50">{selected.title}</h4>
          <p className="mt-1 text-sm text-slate-300">{selected.description}</p>
          {selected.excerpt && (
            <blockquote className="mt-3 rounded-xl border-l-4 border-white/20 bg-white/5 p-3 text-[13px] italic text-slate-200">
              “{selected.excerpt}”
            </blockquote>
          )}
        </div>
      )}
    </SectionCard>
  );
}
