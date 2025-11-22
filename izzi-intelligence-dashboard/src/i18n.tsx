import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Language = "pt-br" | "es";

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
}

const STORAGE_KEY = "izzi-language";

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

function resolveInitialLanguage(): Language {
  if (typeof window === "undefined") return "pt-br";
  const persisted = window.localStorage.getItem(STORAGE_KEY) as Language | null;
  if (persisted === "pt-br" || persisted === "es") return persisted;
  const browser = window.navigator.language.toLowerCase();
  if (browser.startsWith("es")) return "es";
  return "pt-br";
}

let currentLocale = "pt-BR";

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    const initial = resolveInitialLanguage();
    currentLocale = resolveLocale(initial);
    return initial;
  });
  currentLocale = resolveLocale(language);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, language);
  }, [language]);

  const value = useMemo(() => ({ language, setLanguage }), [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used within a LanguageProvider");
  return context;
}

export function useTranslate() {
  const { language } = useLanguage();
  return useMemo(() => {
    return (pt: string, es: string) => (language === "pt-br" ? pt : es);
  }, [language]);
}

export function resolveLocale(language: Language) {
  return language === "pt-br" ? "pt-BR" : "es-ES";
}

export function getCurrentLocale() {
  return currentLocale;
}
