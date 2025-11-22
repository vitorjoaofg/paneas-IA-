import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { AgentScore } from "../../types";
import { SectionCard } from "./SectionCard";

interface AgentsRankingProps {
  scores: AgentScore[];
  months: string[];
}

const TOOLTIP_STYLE = {
  background: "rgba(8,10,18,0.95)",
  borderRadius: "1rem",
  border: "1px solid rgba(255,255,255,0.06)",
  color: "#e2e8f0",
  fontSize: "12px",
};

const COLOR_SCALE = (score: number) => {
  if (score >= 0.75) return "#34d399";
  if (score >= 0.6) return "#a3e635";
  if (score >= 0.45) return "#facc15";
  if (score >= 0.3) return "#f97316";
  return "#ef4444";
};

function formatMonth(month: string) {
  if (!month) return "—";
  const [year, mon] = month.split("-");
  return `${mon}/${year}`;
}

export function AgentsRanking({ scores, months }: AgentsRankingProps) {
  const [currentIndex, setCurrentIndex] = useState(Math.max(months.length - 1, 0));
  const [comparisonIndex, setComparisonIndex] = useState(Math.max(months.length - 2, 0));

  useEffect(() => {
    setCurrentIndex(Math.max(months.length - 1, 0));
    setComparisonIndex(Math.max(months.length - 2, 0));
  }, [months]);

  const currentMonth = months[currentIndex];
  const comparisonMonth = months[comparisonIndex];

  const currentScores = useMemo(() => scores.filter((item) => item.month === currentMonth), [scores, currentMonth]);
  const comparisonMap = useMemo(() => {
    const entries = scores.filter((item) => item.month === comparisonMonth);
    return new Map(entries.map((entry) => [entry.agent, entry]));
  }, [scores, comparisonMonth]);

  const { bestData, worstData, improved, worsened, summary } = useMemo(() => {
    const sorted = [...currentScores].sort((a, b) => b.score - a.score);
    const best = sorted.slice(0, 10);
    const worst = [...sorted].reverse().slice(0, 10);

    const deltas = currentScores.map((item) => {
      const previous = comparisonMap.get(item.agent);
      const delta = previous ? item.score - previous.score : 0;
      return { ...item, delta };
    });

    const improvedList = deltas
      .filter((item) => item.delta > 0.0001)
      .sort((a, b) => b.delta - a.delta)
      .slice(0, 10);
    const worsenedList = deltas
      .filter((item) => item.delta < -0.0001)
      .sort((a, b) => a.delta - b.delta)
      .slice(0, 10);

    const avgCurrent = currentScores.reduce((acc, item) => acc + item.score, 0) / (currentScores.length || 1);
    const avgPrevious = comparisonMap.size
      ? Array.from(comparisonMap.values()).reduce((acc, item) => acc + item.score, 0) / comparisonMap.size
      : avgCurrent;

    return {
      bestData: best,
      worstData: worst,
      improved: improvedList,
      worsened: worsenedList,
      summary: {
        current: avgCurrent,
        previous: avgPrevious,
        delta: avgCurrent - avgPrevious,
      },
    };
  }, [currentScores, comparisonMap]);

  const formatScore = (value: number) => `${Math.round(value * 100)} pts`;

  return (
    <SectionCard
      title="Pontuação de atendentes"
      subtitle="Ranking ponderado por sentimento, engajamento, silêncio e pitch de vendas"
      className="space-y-6"
      actions={
        <div className="flex items-center gap-2 text-xs text-slate-200">
          <button
            type="button"
            onClick={() => setCurrentIndex((index) => Math.max(0, index - 1))}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 hover:bg-white/10"
            disabled={currentIndex <= 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="rounded-full border border-white/10 px-3 py-1">
            Mês foco: {formatMonth(currentMonth)}
          </span>
          <button
            type="button"
            onClick={() => setCurrentIndex((index) => Math.min(months.length - 1, index + 1))}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 hover:bg-white/10"
            disabled={currentIndex >= months.length - 1}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <select
            value={comparisonIndex}
            onChange={(event) => setComparisonIndex(Number(event.target.value))}
            className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs"
          >
            {months.map((month, index) => (
              <option key={month} value={index}>
                Comparar com {formatMonth(month)}
              </option>
            ))}
          </select>
        </div>
      }
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-slate-200">Top 10 melhores</h4>
          <div className="h-72">
            {bestData.length === 0 ? (
              <p className="text-sm text-slate-400">Sem dados suficientes para o mês selecionado.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bestData} layout="vertical" margin={{ left: 40, right: 16, top: 16, bottom: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis type="number" domain={[0, 1]} tickFormatter={(value) => `${Math.round(value * 100)}%`} stroke="rgba(148,163,184,0.6)" />
                  <YAxis dataKey="agent" type="category" width={120} stroke="rgba(148,163,184,0.6)" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(value: number) => [formatScore(value), "Score"]}
                  />
                  <Bar dataKey="score" radius={[0, 12, 12, 0]}>
                    {bestData.map((entry) => (
                      <Cell key={entry.agent} fill={COLOR_SCALE(entry.score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-slate-200">Top 10 piores</h4>
          <div className="h-72">
            {worstData.length === 0 ? (
              <p className="text-sm text-slate-400">Sem dados suficientes para o mês selecionado.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={worstData} layout="vertical" margin={{ left: 40, right: 16, top: 16, bottom: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis type="number" domain={[0, 1]} tickFormatter={(value) => `${Math.round(value * 100)}%`} stroke="rgba(148,163,184,0.6)" />
                  <YAxis dataKey="agent" type="category" width={120} stroke="rgba(148,163,184,0.6)" tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value: number) => [formatScore(value), "Score"]} />
                  <Bar dataKey="score" radius={[0, 12, 12, 0]}>
                    {worstData.map((entry) => (
                      <Cell key={entry.agent} fill={COLOR_SCALE(entry.score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
          <h4 className="text-sm font-semibold text-slate-100">Quem mais evoluiu</h4>
          <ul className="mt-2 space-y-1 text-xs text-emerald-200">
            {improved.length === 0 ? (
              <li className="text-slate-400">Nenhuma evolução registrada.</li>
            ) : (
              improved.map((item) => (
                <li key={item.agent}>
                  {item.agent} · +{Math.round(item.delta * 100)} pts
                </li>
              ))
            )}
          </ul>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-200">
          <h4 className="text-sm font-semibold text-slate-100">Quem mais piorou</h4>
          <ul className="mt-2 space-y-1 text-xs text-rose-200">
            {worsened.length === 0 ? (
              <li className="text-slate-400">Nenhuma queda relevante registrada.</li>
            ) : (
              worsened.map((item) => (
                <li key={item.agent}>
                  {item.agent} · {Math.round(item.delta * 100)} pts
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
        <p>
          Média geral do mês selecionado: <span className="font-semibold text-slate-50">{(summary.current * 100).toFixed(1)} pts</span>
        </p>
        <p>
          Variação vs {formatMonth(comparisonMonth)}: {summary.delta >= 0 ? "+" : ""}
          {(summary.delta * 100).toFixed(1)} pts
        </p>
      </div>
    </SectionCard>
  );
}
