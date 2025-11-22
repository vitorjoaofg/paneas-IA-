import clsx from "clsx";
import type { PropsWithChildren, ReactNode } from "react";

const ACCENT_GRADIENT = "linear-gradient(135deg, rgba(132,183,255,0.25), rgba(78,158,255,0.1))";

interface SectionCardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function SectionCard({ title, subtitle, actions, className, children }: PropsWithChildren<SectionCardProps>) {
  return (
    <div
      className={clsx(
        "relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 shadow-glow backdrop-blur-xl",
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 opacity-40" style={{ background: ACCENT_GRADIENT }} />
      <div className="relative z-10 flex flex-col gap-4">
        {(title || actions) && (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              {title && <h3 className="text-base font-semibold text-slate-50">{title}</h3>}
              {subtitle && <p className="text-sm text-slate-400">{subtitle}</p>}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
