export const getLocale = () => {
  if (typeof navigator !== "undefined" && navigator.language) {
    return navigator.language;
  }
  return "pt-BR";
};

export const formatNumber = (value: number, digits = 0) => {
  if (!Number.isFinite(value)) return "-";
  return value.toLocaleString(getLocale(), {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

export const formatPercent = (value: number, digits = 1) => {
  if (!Number.isFinite(value)) return "-";
  const percentage = value * 100;
  return `${percentage.toLocaleString(getLocale(), {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })}%`;
};

