import { afterEach, describe, expect, it, vi } from "vitest";

import { applyList, firstDir, fold, loadPrefs, savePrefs, type ListOptions } from "./listControls";

type Row = { name: string; value: number | null; date: string; kind: string };

const rows: Row[] = [
  { name: "Préstamo buelito", value: 4000, date: "2026-11-03", kind: "loan" },
  { name: "banorte", value: null, date: "2026-10-01", kind: "bank" },
  { name: "Ahorro 10", value: 250, date: "2026-11-10", kind: "bank" },
  { name: "Ahorro 2", value: 9000, date: "2025-01-15", kind: "bank" },
];

const opts: ListOptions<Row> = {
  sorts: {
    name: { label: "Nombre", get: (r) => r.name },
    value: { label: "Valor", get: (r) => r.value },
    date: { label: "Fecha", get: (r) => r.date },
  },
  search: (r) => [r.name],
  filter: (r) => r.kind,
};

const base = { sortKey: null, dir: "asc" as const, query: "", filter: "" };
const names = (list: Row[]) => list.map((r) => r.name);

describe("applyList", () => {
  it("sin orden conserva el orden original", () => {
    expect(applyList(rows, opts, base)).toBe(rows);
  });

  it("ordena texto en español, sin importar mayúsculas, y números dentro del texto", () => {
    const out = applyList(rows, opts, { ...base, sortKey: "name" });
    expect(names(out)).toEqual(["Ahorro 2", "Ahorro 10", "banorte", "Préstamo buelito"]);
  });

  it("deja los vacíos al final en ambas direcciones", () => {
    const asc = applyList(rows, opts, { ...base, sortKey: "value" });
    const desc = applyList(rows, opts, { ...base, sortKey: "value", dir: "desc" });
    expect(asc.map((r) => r.value)).toEqual([250, 4000, 9000, null]);
    expect(desc.map((r) => r.value)).toEqual([9000, 4000, 250, null]);
  });

  it("ordena fechas ISO", () => {
    const out = applyList(rows, opts, { ...base, sortKey: "date", dir: "desc" });
    expect(out[0].date).toBe("2026-11-10");
    expect(out.at(-1)?.date).toBe("2025-01-15");
  });

  it("busca sin acentos ni mayúsculas", () => {
    expect(names(applyList(rows, opts, { ...base, query: "PRESTAMO" }))).toEqual([
      "Préstamo buelito",
    ]);
    expect(fold("Préstamo")).toBe("prestamo");
  });

  it("filtra y combina con la búsqueda", () => {
    expect(applyList(rows, opts, { ...base, filter: "bank" })).toHaveLength(3);
    expect(applyList(rows, opts, { ...base, filter: "bank", query: "ahorro" })).toHaveLength(2);
  });
});

describe("firstDir", () => {
  it("números y fechas empiezan de mayor a menor; texto de la A a la Z", () => {
    expect(firstDir(opts.sorts.value, rows)).toBe("desc");
    expect(firstDir(opts.sorts.date, rows)).toBe("desc");
    expect(firstDir(opts.sorts.name, rows)).toBe("asc");
    expect(firstDir({ label: "Día", get: () => 5, firstDir: "asc" }, rows)).toBe("asc");
  });
});

describe("preferencias", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("guarda y lee el orden y el filtro", () => {
    savePrefs("x", { sortKey: "value", dir: "desc", filter: "bank" });
    expect(loadPrefs("x")).toEqual({ sortKey: "value", dir: "desc", filter: "bank" });
  });

  it("ignora datos dañados", () => {
    localStorage.setItem("mamoney:list:y", "{no es json");
    expect(loadPrefs("y")).toEqual({});
    localStorage.setItem("mamoney:list:z", JSON.stringify({ sortKey: 3, dir: "up" }));
    expect(loadPrefs("z")).toEqual({ sortKey: null, dir: undefined, filter: "" });
  });

  it("sigue funcionando si el almacenamiento falla", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    expect(loadPrefs("x")).toEqual({});
    expect(() => savePrefs("x", { sortKey: null, dir: "asc", filter: "" })).not.toThrow();
  });
});
