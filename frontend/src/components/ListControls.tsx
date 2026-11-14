import clsx from "clsx";
import { ArrowDown, ArrowDownUp, ArrowUp, Search, X } from "lucide-react";
import type { ReactNode } from "react";

import type { ListControls } from "../lib/listControls";

/**
 * Barra sobre una lista: búsqueda, filtro opcional y, en el teléfono (donde no hay encabezados
 * de tabla que tocar), el selector "Ordenar por" con su dirección.
 */
export function ListToolbar<T>({
  list,
  placeholder = "Buscar…",
  filterLabel,
  filterOptions,
  alwaysShowSort = false,
}: {
  list: ListControls<T>;
  placeholder?: string;
  filterLabel?: string;
  /** Valor → texto. La opción vacía ("Todos") se agrega sola. */
  filterOptions?: Record<string, string>;
  /** Para listas sin tabla en escritorio: el selector de orden se ve en todos los tamaños. */
  alwaysShowSort?: boolean;
}) {
  const sortEntries = Object.entries(list.sorts);
  const filterEntries = filterOptions ? Object.entries(filterOptions) : [];
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {list.hasSearch && (
        <div className="relative min-w-0 basis-full sm:flex-1 sm:basis-48">
          <Search
            size={16}
            className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink-3"
            aria-hidden
          />
          <input
            type="search"
            className="input w-full pr-8 pl-8"
            placeholder={placeholder}
            aria-label={placeholder}
            value={list.query}
            onChange={(e) => list.setQuery(e.target.value)}
          />
          {list.query && (
            <button
              type="button"
              className="absolute top-1/2 right-1.5 -translate-y-1/2 rounded p-1 text-ink-3 hover:text-ink"
              onClick={() => list.setQuery("")}
              aria-label="Limpiar búsqueda"
            >
              <X size={14} />
            </button>
          )}
        </div>
      )}
      {list.hasFilter && filterEntries.length > 1 && (
        <select
          className={clsx(
            "input min-w-0 flex-1 basis-0 sm:w-auto sm:flex-none sm:basis-auto",
            list.filter && "border-accent",
          )}
          aria-label={filterLabel}
          value={list.filter}
          onChange={(e) => list.setFilter(e.target.value)}
        >
          <option value="">{filterLabel ? `${filterLabel}: todo` : "Todo"}</option>
          {filterEntries.map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </select>
      )}
      {/* En el escritorio se ordena tocando los encabezados de la tabla. */}
      <div
        className={clsx(
          "flex min-w-0 flex-1 basis-0 items-center gap-1 sm:flex-none sm:basis-auto",
          !alwaysShowSort && "md:hidden",
        )}
      >
        <ArrowDownUp size={16} className="shrink-0 text-ink-3" aria-hidden />
        <select
          className="input min-w-0 flex-1 sm:w-auto"
          aria-label="Ordenar por"
          value={list.sortKey ?? ""}
          onChange={(e) => list.setSort(e.target.value || null)}
        >
          <option value="">Orden original</option>
          {sortEntries.map(([key, def]) => (
            <option key={key} value={key}>
              {def.label}
            </option>
          ))}
        </select>
        {list.sortKey && (
          <button
            type="button"
            className="btn btn-sm shrink-0"
            onClick={() => list.setDir(list.dir === "asc" ? "desc" : "asc")}
            aria-label={
              list.dir === "asc"
                ? "Ascendente; cambiar a descendente"
                : "Descendente; cambiar a ascendente"
            }
          >
            {list.dir === "asc" ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
          </button>
        )}
      </div>
    </div>
  );
}

/** Encabezado de tabla que ordena al tocarlo; muestra la flecha cuando está activo. */
export function SortHeader<T>({
  list,
  sortKey,
  children,
  align = "left",
}: {
  list: ListControls<T>;
  sortKey: string;
  children: ReactNode;
  align?: "left" | "right";
}) {
  const active = list.sortKey === sortKey;
  const Icon = active ? (list.dir === "asc" ? ArrowUp : ArrowDown) : ArrowDownUp;
  return (
    <th
      className={clsx("py-2 font-medium", align === "right" && "text-right")}
      aria-sort={active ? (list.dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => list.toggleSort(sortKey)}
        className={clsx(
          "group inline-flex items-center gap-1 hover:text-ink",
          align === "right" && "flex-row-reverse",
          active && "text-ink",
        )}
      >
        {children}
        <Icon
          size={12}
          aria-hidden
          className={active ? "" : "opacity-0 transition-opacity group-hover:opacity-60"}
        />
      </button>
    </th>
  );
}

/** Lo que se ve cuando la búsqueda o el filtro dejan la lista vacía. */
export function NoMatches<T>({ list }: { list: ListControls<T> }) {
  if (list.rows.length || !list.total) return null;
  return (
    <div className="rounded-lg border border-dashed border-line px-4 py-8 text-center text-sm">
      <p className="text-ink-2">
        {list.query ? `Nada coincide con «${list.query}»` : "Nada con este filtro"}
      </p>
      <button type="button" className="btn btn-sm mt-3" onClick={list.clear}>
        Limpiar
      </button>
    </div>
  );
}
