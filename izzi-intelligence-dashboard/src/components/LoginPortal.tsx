import { useState } from "react";
import { LanguageToggle } from "./LanguageToggle";
import { useTranslate } from "../i18n";

interface LoginPortalProps {
  onSuccess: () => void;
}

const VALID_USER = "paneas";
const VALID_PASSWORD = "Paneas@321";

export function LoginPortal({ onSuccess }: LoginPortalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const t = useTranslate();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const normalized = username.trim().toLowerCase();
    const isValid = normalized === VALID_USER && password === VALID_PASSWORD;

    if (isValid) {
      if (typeof window !== "undefined") {
        sessionStorage.setItem("izzi-auth", "1");
      }
      setError(null);
      onSuccess();
    } else {
      setError(t("Credenciais inválidas. Tente novamente.", "Credenciales inválidas. Inténtalo de nuevo."));
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#05060a] text-slate-100">
      <div className="absolute right-6 top-6 z-20">
        <LanguageToggle />
      </div>
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 right-[-120px] h-80 w-80 rounded-full bg-gradient-to-br from-[#84b7ff]/30 via-[#4e9eff]/20 to-transparent blur-3xl" />
        <div className="absolute bottom-[-160px] left-[-140px] h-[420px] w-[420px] rounded-full bg-gradient-to-tr from-[#6ef3ff]/25 via-[#3f8cff]/15 to-transparent blur-3xl" />
        <div className="absolute left-1/2 top-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-tr from-[#a094ff]/20 via-transparent to-transparent blur-[120px]" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-md px-6 py-16">
        <div className="mb-8 text-center">
          <p className="text-xs uppercase tracking-[0.5em] text-slate-300/70">Izzi Speech Analytics</p>
          <h1 className="mt-3 text-4xl font-semibold text-slate-50">
            {t("Painel Operacional", "Panel Operacional")}
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            {t(
              "Acesse com suas credenciais paneas para desbloquear os insights das 600 chamadas.",
              "Accede con tus credenciales paneas para desbloquear los insights de las 600 llamadas.",
            )}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-4xl border border-white/10 bg-white/5 p-10 shadow-glow backdrop-blur-2xl"
        >
          <div className="mb-8 space-y-4">
            <div>
              <label className="text-xs uppercase tracking-[0.3em] text-slate-400">
                {t("Usuário", "Usuario")}
              </label>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm font-medium text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-accent-soft"
                placeholder="paneas"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-[0.3em] text-slate-400">
                {t("Senha", "Contraseña")}
              </label>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm font-medium text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-accent-soft"
                placeholder="********"
                autoComplete="current-password"
              />
            </div>
          </div>

          {error && (
            <div className="mb-6 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-100">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-[#74a7ff] via-[#4e9eff] to-[#6ef3ff] px-4 py-3 text-sm font-semibold text-slate-950 transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 focus:ring-[#74a7ff]"
          >
            {t("Entrar", "Ingresar")}
          </button>

        </form>
      </div>
    </div>
  );
}
