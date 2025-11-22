import clsx from "clsx";
import type { ConversationEvent, TranscriptSegment } from "../../types";

interface ConversationTimelineProps {
  segments: TranscriptSegment[];
  events: ConversationEvent[];
  selectedId?: string | null;
  onSelect: (event: ConversationEvent) => void;
}

const SPEAKER_COLOR: Record<string, string> = {
  agent: "bg-sky-400/70",
  customer: "bg-emerald-400/70",
  ivr: "bg-slate-500/60",
  other: "bg-slate-500/40",
};

const EVENT_COLOR: Record<ConversationEvent["tone"], string> = {
  positive: "bg-emerald-400",
  negative: "bg-rose-500",
  neutral: "bg-slate-300",
};

const EVENT_SHADOW: Record<ConversationEvent["tone"], string> = {
  positive: "shadow-[0_0_12px_rgba(52,211,153,0.7)]",
  negative: "shadow-[0_0_12px_rgba(248,113,113,0.7)]",
  neutral: "shadow-[0_0_10px_rgba(148,163,184,0.6)]",
};

function classifySpeaker(raw: string): keyof typeof SPEAKER_COLOR {
  const value = raw.toLowerCase();
  if (value.includes("agent") || value.includes("agente")) return "agent";
  if (value.includes("customer") || value.includes("cliente")) return "customer";
  if (value.includes("ivr")) return "ivr";
  return "other";
}

export function ConversationTimeline({ segments, events, selectedId, onSelect }: ConversationTimelineProps) {
  const duration = Math.max(
    ...segments.map((segment) => Number.isFinite(segment.end) ? segment.end : segment.start + 1),
    ...events.map((event) => event.time + 1),
    60,
  );

  const lineLabels = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="relative flex flex-col gap-3">
      <div className="relative h-28 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/40">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-white/10" />
        {segments.map((segment) => {
          const start = Math.max(0, Number.isFinite(segment.start) ? segment.start : 0);
          const end = Math.max(start + 0.1, Number.isFinite(segment.end) ? segment.end : start + 0.1);
          const left = (start / duration) * 100;
          const width = Math.max(1.5, ((end - start) / duration) * 100);
          const speaker = classifySpeaker(segment.speaker);
          return (
            <div
              key={`${segment.id}-${start}`}
              className={clsx(
                "absolute top-3 h-6 rounded-full bg-gradient-to-r from-transparent via-current to-transparent",
                SPEAKER_COLOR[speaker],
              )}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`${speaker} · ${segment.text.slice(0, 120)}`}
            />
          );
        })}

        {events.map((event) => {
          const position = Math.min(100, Math.max(0, (event.time / duration) * 100));
          const isActive = selectedId === event.id;
          return (
            <button
              key={event.id}
              type="button"
              onClick={() => onSelect(event)}
              className={clsx(
                "absolute top-1/2 flex -translate-y-1/2 flex-col items-center gap-2",
                isActive && EVENT_SHADOW[event.tone],
              )}
              style={{ left: `${position}%` }}
            >
              <span
                className={clsx(
                  "h-10 w-[3px] rounded-full",
                  EVENT_COLOR[event.tone],
                  isActive ? "opacity-100" : "opacity-70",
                )}
              />
              <span
                className={clsx(
                  "whitespace-nowrap rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide",
                  EVENT_COLOR[event.tone],
                  "bg-opacity-90 text-slate-900 shadow-sm",
                )}
              >
                {event.tone === "positive" ? "positivo" : event.tone === "negative" ? "negativo" : "neutro"}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-400">
        {lineLabels.map((value) => (
          <span key={value}>{Math.round(value * duration)}s</span>
        ))}
      </div>
    </div>
  );
}
