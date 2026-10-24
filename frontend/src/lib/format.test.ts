import { describe, expect, it } from "vitest";

import { foldOther, colorMap, OTHER, SERIES } from "../components/charts/palette";
import { money, monthLabel, pct } from "./format";

describe("format", () => {
  it("formatea pesos mexicanos", () => {
    expect(money(1234.5)).toMatch(/1,234\.50/);
    expect(money(null)).toBe("—");
  });

  it("acepta monedas no ISO", () => {
    expect(money(0.5, "BTC")).toBe("0.5 BTC");
  });

  it("formatea porcentajes y meses", () => {
    expect(pct(12.345)).toBe("12.3 %");
    expect(monthLabel("2026-01")).toMatch(/ene/i);
  });
});

describe("palette", () => {
  it("asigna color por entidad en orden fijo y agrupa el resto", () => {
    const keys = Array.from({ length: 10 }, (_, i) => `k${i}`);
    const map = colorMap(keys);
    expect(map.get("k0")).toBe(SERIES[0]);
    expect(map.get("k9")).toBe(OTHER);
  });

  it("dobla en 'Otros' a partir de la octava entrada", () => {
    const rows = Array.from({ length: 10 }, (_, i) => ({ key: `k${i}`, value: 1 }));
    const folded = foldOther(rows);
    expect(folded).toHaveLength(8);
    expect(folded.at(-1)).toEqual({ key: "Otros", value: 3 });
  });
});
