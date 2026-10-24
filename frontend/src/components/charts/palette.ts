/** Paleta categórica validada (orden fijo; nunca se recicla). */
export const SERIES = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`);
export const OTHER = "var(--series-other)";

/**
 * Asigna color por entidad, no por ranking: la clave conserva su color aunque
 * cambie el filtro. A partir de la novena entidad todo se agrupa en "Otros".
 */
export function colorMap(keys: string[]): Map<string, string> {
  const map = new Map<string, string>();
  keys.forEach((k, i) => map.set(k, i < SERIES.length ? SERIES[i] : OTHER));
  return map;
}

/** Agrupa todo lo que pase de `max` elementos en una entrada "Otros". */
export function foldOther<T extends { key: string; value: number }>(rows: T[], max = 7) {
  if (rows.length <= max + 1) return rows.map((r) => ({ key: r.key, value: r.value }));
  const head = rows.slice(0, max).map((r) => ({ key: r.key, value: r.value }));
  const rest = rows.slice(max).reduce((s, r) => s + r.value, 0);
  return [...head, { key: "Otros", value: rest }];
}
