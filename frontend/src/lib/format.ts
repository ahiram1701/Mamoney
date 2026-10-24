const BASE = "MXN";

const moneyFormatters = new Map<string, Intl.NumberFormat>();
const ISO_CURRENCIES = new Set(Intl.supportedValuesOf?.("currency") ?? ["MXN", "USD", "EUR"]);
const plain = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 8 });

export function money(value: number | null | undefined, currency = BASE, compact = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const key = `${currency}-${compact}`;
  let fmt = moneyFormatters.get(key);
  // Monedas no ISO (p. ej. BTC): número con más decimales + código.
  if (!ISO_CURRENCIES.has(currency)) return `${plain.format(value)} ${currency}`;
  if (!fmt) {
    fmt = new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency,
      notation: compact ? "compact" : "standard",
      maximumFractionDigits: compact ? 1 : 2,
    });
    moneyFormatters.set(key, fmt);
  }
  return fmt.format(value);
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${value.toLocaleString("es-MX", { maximumFractionDigits: digits })} %`;
}

export function number(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("es-MX", { maximumFractionDigits: digits });
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-MX", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("es-MX", { month: "short", year: "2-digit" });
}

export function todayIso(): string {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}
