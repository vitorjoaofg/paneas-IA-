import { useMemo, useRef } from "react";
import { Download, Sparkles } from "lucide-react";
import clsx from "clsx";
import { SectionCard } from "./SectionCard";
import type { WordDatum } from "../../utils/conversationAnalytics";
import { downloadSvgAsPng } from "../../utils/exportSvg";

interface CloudWordsSectionProps {
  customerWords: WordDatum[];
  agentWords: WordDatum[];
  filteredWords: WordDatum[];
  loading?: boolean;
}

interface LayoutWord extends WordDatum {
  x: number;
  y: number;
  fontSize: number;
}

function generateWordLayout(words: WordDatum[], width: number, height: number): LayoutWord[] {
  if (words.length === 0) return [];
  const sorted = [...words].sort((a, b) => b.value - a.value).slice(0, 80);
  const max = sorted[0]?.value ?? 1;
  const min = sorted[sorted.length - 1]?.value ?? 0;
  const centerX = width / 2;
  const centerY = height / 2;
  const placed: LayoutWord[] = [];

  function estimateWidth(word: string, fontSize: number) {
    return fontSize * (Math.min(word.length, 12) * 0.55 + Math.max(word.length - 12, 0) * 0.3);
  }

  function intersects(x: number, y: number, w: number, h: number): boolean {
    const x1 = x - w / 2 - 6;
    const y1 = y - h / 2 - 4;
    const x2 = x + w / 2 + 6;
    const y2 = y + h / 2 + 4;
    return placed.some((other) => {
      const otherW = estimateWidth(other.text, other.fontSize);
      const otherH = other.fontSize;
      const ox1 = other.x - otherW / 2 - 4;
      const oy1 = other.y - otherH / 2 - 4;
      const ox2 = other.x + otherW / 2 + 4;
      const oy2 = other.y + otherH / 2 + 4;
      return !(x2 < ox1 || x1 > ox2 || y2 < oy1 || y1 > oy2);
    });
  }

  sorted.forEach((word, index) => {
    const normalized = max === min ? 1 : (word.value - min) / (max - min);
    const fontSize = Math.max(14, Math.min(60, 18 + normalized * 38));
    const wordWidth = estimateWidth(word.text, fontSize);
    const wordHeight = fontSize;
    const maxRadius = Math.max(width, height);
    let placedWord: LayoutWord | null = null;
    for (let theta = 0; theta < 3000; theta += 0.6) {
      const radius = 4 + theta * 1.1;
      const x = centerX + radius * Math.cos(theta + index * 0.5);
      const y = centerY + radius * Math.sin(theta + index * 0.5);
      if (x - wordWidth / 2 < 0 || x + wordWidth / 2 > width) continue;
      if (y - wordHeight / 2 < 0 || y + wordHeight / 2 > height) continue;
      if (!intersects(x, y, wordWidth, wordHeight)) {
        placedWord = { ...word, x, y, fontSize };
        break;
      }
      if (radius > maxRadius) break;
    }
    if (placedWord) {
      placed.push(placedWord);
    }
  });

  return placed;
}

function WordCloudCard({
  title,
  subtitle,
  words,
  emptyMessage,
  exportName,
  loading,
}: {
  title: string;
  subtitle: string;
  words: WordDatum[];
  emptyMessage: string;
  exportName: string;
  loading?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const layout = useMemo(() => generateWordLayout(words, 520, 220), [words]);

  const handleExport = () => {
    const svg = containerRef.current?.querySelector("svg");
    if (svg) {
      downloadSvgAsPng(svg as SVGSVGElement, exportName);
    }
  };

  return (
    <SectionCard
      title={title}
      subtitle={subtitle}
      actions={
        <button
          type="button"
          onClick={handleExport}
          disabled={!layout.length || loading}
          className={clsx(
            "flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold transition",
            layout.length && !loading ? "bg-white/5 text-slate-100 hover:bg-white/10" : "bg-slate-900/40 text-slate-500",
          )}
        >
          <Download className="h-4 w-4" /> Exportar PNG
        </button>
      }
      className="min-h-[280px]"
    >
      <div ref={containerRef} className="h-48 w-full">
        {loading ? (
          <div className="flex h-full items-center justify-center gap-2 text-slate-300">
            <Sparkles className="h-4 w-4 animate-spin" />
            <span className="text-sm">Preparando palavras-chave...</span>
          </div>
        ) : layout.length ? (
          <svg viewBox="0 0 520 220" className="h-full w-full">
            {layout.map((word) => (
              <text
                key={`${word.text}-${word.value}`}
                x={word.x}
                y={word.y}
                fontSize={word.fontSize}
                textAnchor="middle"
                fill="rgba(160,200,255,0.9)"
                style={{ fontWeight: 500 }}
              >
                {word.text}
              </text>
            ))}
          </svg>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-slate-400">
            {emptyMessage}
          </div>
        )}
      </div>
    </SectionCard>
  );
}

export function CloudWordsSection({ customerWords, agentWords, filteredWords, loading }: CloudWordsSectionProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <WordCloudCard
        title="CloudWords de Clientes"
        subtitle="Vocabulário mais recorrente nas falas dos clientes"
        words={customerWords}
        emptyMessage="Nenhuma transcrição de cliente disponível nas chamadas carregadas."
        exportName="izzi-cloud-clientes"
        loading={loading}
      />
      <WordCloudCard
        title="CloudWords de Atendentes"
        subtitle="Principais termos utilizados pelos operadores"
        words={agentWords}
        emptyMessage="Nenhuma fala de atendente encontrada para gerar a nuvem."
        exportName="izzi-cloud-atendentes"
        loading={loading}
      />
      <WordCloudCard
        title="CloudWords do conjunto filtrado"
        subtitle="Amostra atual após aplicação dos filtros do dashboard"
        words={filteredWords}
        emptyMessage="Aplique filtros ou selecione outra chamada para ver a nuvem contextual."
        exportName="izzi-cloud-filtros"
        loading={loading}
      />
    </div>
  );
}
