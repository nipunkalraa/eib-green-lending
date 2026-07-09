export function formatEUR(value: number): string {
  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatEURCompact(value: number): string {
  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency: "EUR",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IE").format(value);
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat("en-IE", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}
