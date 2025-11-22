import clsx from "clsx";
import { Languages } from "lucide-react";
import { useLanguage, useTranslate } from "../i18n";

interface LanguageToggleProps {
  className?: string;
}

const OPTIONS: Array<{ code: "pt-br" | "es"; flag: string; label: string }> = [
  { code: "pt-br", flag: "🇧🇷", label: "PT-BR" },
  { code: "es", flag: "🇪🇸", label: "ES" },
];

export function LanguageToggle({ className }: LanguageToggleProps) {
  const { language, setLanguage } = useLanguage();
  const t = useTranslate();

  return (
    <div
      className={clsx(
        "flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 shadow-glow backdrop-blur-md",
        className,
      )}
      aria-label={t("Seleção de idioma", "Selector de idioma")}
    >
      <Languages className="h-4 w-4 text-sky-200" aria-hidden />
      <div className="flex items-center gap-1.5">
        {OPTIONS.map((option) => {
          const active = language === option.code;
          return (
            <button
              key={option.code}
              type="button"
              onClick={() => setLanguage(option.code)}
              className={clsx(
                "flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-accent-soft focus:ring-offset-2 focus:ring-offset-slate-950",
                active ? "bg-white text-slate-900 shadow" : "text-slate-300 hover:bg-white/10",
              )}
            >
              <span role="img" aria-hidden>
                {option.flag}
              </span>
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
