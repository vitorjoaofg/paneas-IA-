import { ClipboardCheck, RadioTower, Megaphone, ShieldCheck, MicVocal } from "lucide-react";
import clsx from "clsx";
import type { QualityMetrics } from "../../utils/executiveMetrics";
import { useTranslate } from "../../i18n";
import { formatPercent } from "../../utils/numberFormat";

interface QualityIndicatorsProps {
  data: QualityMetrics;
}

const tiles = [
  {
    key: "script",
    icon: ClipboardCheck,
    accent: "text-emerald-200",
  },
  {
    key: "origin",
    icon: RadioTower,
    accent: "text-sky-200",
  },
  {
    key: "pitch",
    icon: Megaphone,
    accent: "text-indigo-200",
  },
  {
    key: "objection",
    icon: ShieldCheck,
    accent: "text-amber-200",
  },
  {
    key: "silence",
    icon: MicVocal,
    accent: "text-rose-200",
  },
] as const;

export const QualityIndicators = ({ data }: QualityIndicatorsProps) => {
  const t = useTranslate();
  const map = {
    script: {
      label: t("Script seguido", "Guion seguido"),
      value: formatPercent(data.scriptAlignedRate, 1),
      helper: t("Somente ligações com script aplicável.", "Solo llamadas con guion aplicable."),
    },
    origin: {
      label: t("Origem reconhecida", "Origen reconocida"),
      value: formatPercent(data.originRecognitionRate, 1),
      helper: t("Agentes explicitaram a origem do contato.", "Los agentes explicitaron el origen del contacto."),
    },
    pitch: {
      label: t("Pitch satisfatório", "Pitch satisfactorio"),
      value: formatPercent(data.pitchSatisfactoryRate, 1),
      helper: t("Pontuação ≥ 0,7 ou classificado como satisfatório.", "Puntuación ≥ 0,7 o clasificado como satisfactorio."),
    },
    objection: {
      label: t("Contra-argumentos", "Contraargumentos"),
      value: formatPercent(data.contraArgumentRate, 1),
      helper: t("Atendimentos com tratamento ativo de objeções.", "Atenciones con tratamiento activo de objeciones."),
    },
    silence: {
      label: t("Silêncio médio", "Silencio medio"),
      value: formatPercent(data.averageSilence, 1),
      helper: t("Tempo sem fala em relação à duração total.", "Tiempo sin habla en relación a la duración total."),
    },
  };

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      {tiles.map((tile) => {
        const metric = map[tile.key];
        const Icon = tile.icon;
        return (
          <div
            key={tile.key}
            className={clsx(
              "flex h-full flex-col justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-slate-100 shadow-inner backdrop-blur",
            )}
          >
            <div className="flex items-center justify-between">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-300">{metric.label}</p>
              <span className={clsx("rounded-2xl border border-white/10 bg-white/10 p-2", tile.accent)}>
                <Icon className="h-4 w-4" />
              </span>
            </div>
            <p className="text-xl font-semibold">{metric.value}</p>
            <p className="text-xs text-slate-400">{metric.helper}</p>
          </div>
        );
      })}
    </div>
  );
};
