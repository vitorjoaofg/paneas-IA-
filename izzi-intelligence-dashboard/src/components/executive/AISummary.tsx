import { Sparkles } from "lucide-react";
import { useTranslate } from "../../i18n";

interface AISummaryProps {
  text: string;
}

export const AISummary = ({ text }: AISummaryProps) => {
  const t = useTranslate();

  if (!text) return null;

  return (
    <div className="rounded-2xl border border-indigo-400/40 bg-indigo-500/10 px-4 py-4 text-sm text-indigo-100 shadow-inner backdrop-blur">
      <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.3em]">
        <Sparkles className="h-4 w-4" />
        <span>{t("Resumo inteligente", "Resumen inteligente")}</span>
      </div>
      <p>{text}</p>
    </div>
  );
};

