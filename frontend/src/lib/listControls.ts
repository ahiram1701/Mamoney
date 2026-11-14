import { useMemo, useState } from "react";

/** Valor por el que se ordena: texto, número (fechas ISO cuentan como texto) o vacío. */
export type SortValue = string | number | null | undefined;

export type SortDef<T> = {
  label: string;
  get: (row: T) => SortValue;
  /** Dirección del primer toque; por omisión, desc en números y fechas, asc en texto. */
  firstDir?: SortDir;
};

export type SortDir = "asc" | "desc";

export type ListOptions<T> = {
  sorts: Record<string, SortDef<T>>;
  /** Campos donde busca el cuadro de texto. */
  search?: (row: T) => (string | null | undefined)[];
  /** Filtro de un `select`: devuelve el valor de la fila que se compara con el elegido. */
  filter?: (row: T) => string;
};

export type ListState = {
  sortKey: string | null;
  dir: SortDir;
  query: string;
  filter: string;
};

const collator = new Intl.Collator("es", { sensitivity: "base", numeric: true });

/** Minúsculas y sin acentos: "Préstamo" → "prestamo". */
export function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function isEmpty(v: SortValue): v is null | undefined {
  return v === null || v === undefined || v === "" || (typeof v === "number" && Number.isNaN(v));
}

function compare(a: SortValue, b: SortValue): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return collator.compare(String(a), String(b));
}

/** Filtra, busca y ordena. Los vacíos van siempre al final; el orden es estable. */
export function applyList<T>(rows: T[], opts: ListOptions<T>, state: ListState): T[] {
  let out = rows;
  if (opts.filter && state.filter) {
    const pick = opts.filter;
    out = out.filter((r) => pick(r) === state.filter);
  }
  const q = fold(state.query.trim());
  if (opts.search && q) {
    const fields = opts.search;
    out = out.filter((r) => fields(r).some((f) => f && fold(f).includes(q)));
  }
  const def = state.sortKey ? opts.sorts[state.sortKey] : undefined;
  if (def) {
    const sign = state.dir === "asc" ? 1 : -1;
    out = out
      .map((row, i) => ({ row, i, v: def.get(row) }))
      .sort((x, y) => {
        const ex = isEmpty(x.v);
        const ey = isEmpty(y.v);
        if (ex || ey) return ex === ey ? x.i - y.i : ex ? 1 : -1;
        return sign * compare(x.v, y.v) || x.i - y.i;
      })
      .map((x) => x.row);
  }
  return out;
}

/** Dirección del primer toque en una columna, según el tipo de sus valores. */
export function firstDir<T>(def: SortDef<T>, rows: T[]): SortDir {
  if (def.firstDir) return def.firstDir;
  const sample = rows.map(def.get).find((v) => !isEmpty(v));
  if (typeof sample === "number") return "desc";
  if (typeof sample === "string" && /^\d{4}-\d{2}-\d{2}/.test(sample)) return "desc";
  return "asc";
}

type Prefs = Pick<ListState, "sortKey" | "dir" | "filter">;
const PREFIX = "mamoney:list:";

/** Orden y filtro guardados en este navegador; si el almacenamiento falla, nada. */
export function loadPrefs(id: string): Partial<Prefs> {
  try {
    const raw = localStorage.getItem(PREFIX + id);
    const p = raw ? (JSON.parse(raw) as Partial<Prefs>) : {};
    return {
      sortKey: typeof p.sortKey === "string" ? p.sortKey : null,
      dir: p.dir === "asc" || p.dir === "desc" ? p.dir : undefined,
      filter: typeof p.filter === "string" ? p.filter : "",
    };
  } catch {
    return {};
  }
}

export function savePrefs(id: string, prefs: Prefs): void {
  try {
    localStorage.setItem(PREFIX + id, JSON.stringify(prefs));
  } catch {
    // Modo privado o almacenamiento bloqueado: la lista funciona igual, solo no recuerda.
  }
}

export type ListControls<T> = ListState & {
  rows: T[];
  total: number;
  sorts: Record<string, SortDef<T>>;
  hasFilter: boolean;
  hasSearch: boolean;
  toggleSort: (key: string) => void;
  setSort: (key: string | null, dir?: SortDir) => void;
  setDir: (dir: SortDir) => void;
  setQuery: (q: string) => void;
  setFilter: (f: string) => void;
  /** Quita búsqueda y filtro (no el orden). */
  clear: () => void;
};

/**
 * Orden por columna, búsqueda y filtro de una lista. El orden y el filtro se recuerdan por `id`;
 * la búsqueda no, para no volver a una lista recortada sin saber por qué.
 */
export function useListControls<T>(id: string, rows: T[], opts: ListOptions<T>): ListControls<T> {
  const [state, setState] = useState<ListState>(() => {
    const p = loadPrefs(id);
    const sortKey = p.sortKey && p.sortKey in opts.sorts ? p.sortKey : null;
    return { sortKey, dir: p.dir ?? "asc", query: "", filter: p.filter ?? "" };
  });

  const update = (next: ListState) => {
    setState(next);
    savePrefs(id, { sortKey: next.sortKey, dir: next.dir, filter: next.filter });
  };

  const sorted = useMemo(
    () => applyList(rows, opts, state),
    // `opts` suele ser un literal nuevo en cada render; sus funciones no cambian de lógica.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, state],
  );

  return {
    ...state,
    rows: sorted,
    total: rows.length,
    sorts: opts.sorts,
    hasFilter: Boolean(opts.filter),
    hasSearch: Boolean(opts.search),
    toggleSort: (key) => {
      const def = opts.sorts[key];
      if (!def) return;
      if (state.sortKey === key) update({ ...state, dir: state.dir === "asc" ? "desc" : "asc" });
      else update({ ...state, sortKey: key, dir: firstDir(def, rows) });
    },
    setSort: (key, dir) => {
      const def = key ? opts.sorts[key] : undefined;
      update({
        ...state,
        sortKey: def ? key : null,
        dir: dir ?? (def ? firstDir(def, rows) : "asc"),
      });
    },
    setDir: (dir) => update({ ...state, dir }),
    setQuery: (query) => setState({ ...state, query }),
    setFilter: (filter) => update({ ...state, filter }),
    clear: () => update({ ...state, query: "", filter: "" }),
  };
}
