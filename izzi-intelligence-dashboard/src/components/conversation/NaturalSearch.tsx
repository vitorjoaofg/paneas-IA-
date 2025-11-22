import { useCallback, useMemo, useState } from "react";
import { Loader2, Search } from "lucide-react";
import type { PerCallDetail, TranscriptSegment } from "../../types";
import { SectionCard } from "./SectionCard";

interface NaturalSearchProps {
  rows: PerCallDetail[];
  onSelectCall: (callId: string) => void;
  loadTranscript: (callId: string) => Promise<TranscriptSegment[]>;
}

interface SearchResult {
  call: PerCallDetail;
  snippet: string;
  score: number;
  matchedTerms: string[];
}

const STRUCTURED_RULES = [
  {
    pattern: /(sentimento|sentiment).*(negativ|ruim|crític)/,
    predicate: (row: PerCallDetail) => row.customer_sentiment_label === "negative" || row.customer_sentiment_score < 0.2,
    description: "sentimento negativo",
  },
  {
    pattern: /(engajamento|engagement).*(baixo|low|menor)/,
    predicate: (row: PerCallDetail) => row.customer_engagement_score <= 0.35,
    description: "engajamento baixo",
  },
  {
    pattern: /(follow[- ]?up|retorno|prometeu).*não (foi )?cumprido/,
    predicate: (row: PerCallDetail) => row.follow_up_commitment !== 1,
    description: "follow-up ausente",
  },
  {
    pattern: /(não|no) (foi )?resolvido|sem solução|não solucionado/,
    predicate: (row: PerCallDetail) => !/resolvid|solucionad/.test((row.status_real_detectado ?? "").toLowerCase()),
    description: "problema não resolvido",
  },
];

function sanitizeQuery(query: string) {
  return query
    .toLowerCase()
    .replace(/["'’]/g, "")
    .replace(/[,.;:!?]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildMetadataString(row: PerCallDetail): string {
  return [
    row.llm_notes,
    row.divergencia_motivo,
    row.izzi_status_normalizado,
    row.status_real_detectado,
    row.sales_pitch_topics?.join(" "),
    row.follow_up_matches?.join(" "),
    row.customer_anger_matches?.join(" "),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

async function findSnippetInSegments(segments: TranscriptSegment[], tokens: string[]): Promise<string> {
  if (tokens.length === 0) {
    const first = segments[0]?.text?.trim() ?? "";
    return first.slice(0, 180);
  }
  for (const segment of segments) {
    const lower = segment.text?.toLowerCase() ?? "";
    if (tokens.some((token) => lower.includes(token))) {
      return segment.text.trim().slice(0, 220);
    }
  }
  return segments[0]?.text?.trim().slice(0, 220) ?? "";
}

export function NaturalSearch({ rows, onSelectCall, loadTranscript }: NaturalSearchProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);

  const recognizedRules = useMemo(() => {
    const sanitized = sanitizeQuery(query);
    return STRUCTURED_RULES.filter((rule) => rule.pattern.test(sanitized)).map((rule) => rule.description);
  }, [query]);

  const executeSearch = useCallback(async () => {
    const sanitized = sanitizeQuery(query);
    if (!sanitized) {
      setResults([]);
      return;
    }

    setLoading(true);
    const structuredMatches = STRUCTURED_RULES.filter((rule) => rule.pattern.test(sanitized));
    const tokens = sanitized
      .split(" ")
      .filter((token) => token.length > 2 && !structuredMatches.some((rule) => rule.description.includes(token)));

    const found: SearchResult[] = [];
    const maxResults = 40;

    for (const row of rows) {
      if (structuredMatches.some((rule) => !rule.predicate(row))) {
        continue;
      }

      const metadata = buildMetadataString(row);
      const missingTokens = tokens.filter((token) => !metadata.includes(token));
      let segments: TranscriptSegment[] | null = null;
      let snippet = "";
      if (missingTokens.length > 0) {
        segments = await loadTranscript(row.call_id);
        if (segments.length === 0) {
          continue;
        }
        const passes = missingTokens.every((token) =>
          segments!.some((segment) => segment.text?.toLowerCase().includes(token)),
        );
        if (!passes) {
          continue;
        }
        snippet = await findSnippetInSegments(segments, tokens);
      } else {
        snippet = row.llm_notes?.slice(0, 200) ?? "Resumo indisponível.";
      }

      const matchedTerms = tokens.filter((token) => metadata.includes(token));
      const derivedScore = matchedTerms.length + structuredMatches.length * 2 + (row.customer_anger_detected === 1 ? 1 : 0);
      found.push({ call: row, snippet, score: derivedScore, matchedTerms });

      if (found.length >= maxResults) {
        break;
      }
    }

    found.sort((a, b) => b.score - a.score);
    setResults(found);
    setLoading(false);
  }, [query, rows, loadTranscript]);

  return (
    <SectionCard
      title="Busca por linguagem natural"
      subtitle="Pesquise por temas, intenções ou sinais específicos em todo o acervo de transcrições"
      className="space-y-4"
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-2xl border border-white/10 bg-black/30 px-4 py-2">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void executeSearch();
                }
              }}
              className="flex-1 border-0 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
              placeholder="Ex.: conversas com sentimento negativo e engajamento baixo"
            />
          </div>
          <button
            type="button"
            onClick={() => void executeSearch()}
            className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 transition hover:bg-white/10"
            disabled={loading}
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Buscar
          </button>
        </div>
        {recognizedRules.length > 0 && (
          <p className="text-xs text-slate-400">
            Filtros reconhecidos automaticamente: {recognizedRules.join(", ")}.
          </p>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-slate-400">Executando varredura nas transcrições...</p>
      ) : results.length === 0 ? (
        <p className="text-sm text-slate-400">Nenhum resultado. Combine palavras-chave com um contexto mais específico.</p>
      ) : (
        <div className="space-y-3">
          {results.map((result) => (
            <button
              key={result.call.call_id}
              type="button"
              onClick={() => onSelectCall(result.call.call_id)}
              className="w-full rounded-2xl border border-white/10 bg-white/5 p-4 text-left transition hover:bg-white/10"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <span className="font-semibold text-slate-200">{result.call.call_id}</span>
                <span>
                  {result.call.call_datetime ?? "data não informada"} · Sentimento {result.call.customer_sentiment_label} ·
                  Engajamento {result.call.customer_engagement_score.toFixed(2)}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-200">{result.snippet}</p>
              {result.matchedTerms.length > 0 && (
                <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">
                  Termos encontrados: {result.matchedTerms.join(", ")}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
