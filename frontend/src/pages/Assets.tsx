import { Archive, History, LineChart, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  useApiMutation,
  useAssetRows,
  useAssets,
  useDistribution,
  useSettings,
  useValuations,
} from "../api/hooks";
import type { Asset, AssetRow } from "../api/types";
import { Donut, TimeLineChart } from "../components/charts/Charts";
import { foldOther, SERIES } from "../components/charts/palette";
import {
  Card,
  EmptyState,
  ErrorText,
  Field,
  Modal,
  PageHeader,
  SelectOptions,
  Segmented,
  StatTile,
} from "../components/ui";
import { money, pct, shortDate, todayIso } from "../lib/format";
import { ASSET_TYPES, LIABILITY_TYPES, LIQUIDITY, label, type AssetType } from "../lib/labels";

const TYPE_ORDER = Object.keys(ASSET_TYPES);
const POSITION_TYPES = new Set(["investment", "crypto", "retirement"]);
const LIQUIDITY_ORDER = Object.keys(LIQUIDITY);

export function AssetsPage() {
  const { data: rows = [] } = useAssetRows();
  const { data: dist } = useDistribution();
  const [editing, setEditing] = useState<Asset | "new" | null>(null);
  const [valuing, setValuing] = useState<AssetRow | null>(null);
  const [historyOf, setHistoryOf] = useState<AssetRow | null>(null);
  const [view, setView] = useState<"by_type" | "by_currency" | "by_liquidity">("by_type");
  const [showArchived, setShowArchived] = useState(false);
  const { data: assets = [] } = useAssets();

  const visible = rows.filter((r) => showArchived || !r.archived);
  const activeRows = visible.filter((r) => !r.is_liability);
  const debtRows = visible.filter((r) => r.is_liability);
  const totalAssets = activeRows.reduce((s, r) => s + r.value_base, 0);
  const totalDebt = debtRows.reduce((s, r) => s + r.value_base, 0);

  const distData = dist ? foldOther(dist[view]) : [];
  const distLabels: Record<string, string> =
    view === "by_type" ? ASSET_TYPES : view === "by_liquidity" ? LIQUIDITY : {};
  const keyOrder =
    view === "by_type" ? TYPE_ORDER : view === "by_liquidity" ? LIQUIDITY_ORDER : undefined;

  return (
    <>
      <PageHeader
        title="Patrimonio"
        subtitle="Tus activos y deudas. Registra una valuación cada vez que cambie su valor."
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            <Plus size={16} /> Nuevo activo o deuda
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatTile label="Activos" value={money(totalAssets)} />
        <StatTile label="Deudas" value={money(totalDebt)} />
        <StatTile label="Patrimonio neto" value={money(totalAssets - totalDebt)} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
        <Card
          title="Cuentas y bienes"
          actions={
            <label className="flex items-center gap-2 text-xs text-ink-2">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              Mostrar archivados
            </label>
          }
        >
          {rows.length === 0 ? (
            <EmptyState title="Todavía no registras nada">
              Empieza con tus cuentas bancarias, inversiones, inmuebles y deudas.
            </EmptyState>
          ) : (
            <div className="space-y-6">
              <AssetTable
                title="Activos"
                rows={activeRows}
                onValue={setValuing}
                onHistory={setHistoryOf}
                onEdit={(r) => setEditing(assets.find((a) => a.id === r.id) ?? null)}
              />
              {debtRows.length > 0 && (
                <AssetTable
                  title="Deudas"
                  rows={debtRows}
                  onValue={setValuing}
                  onHistory={setHistoryOf}
                  onEdit={(r) => setEditing(assets.find((a) => a.id === r.id) ?? null)}
                />
              )}
            </div>
          )}
        </Card>

        <Card
          title="Distribución de activos"
          actions={
            <Segmented
              label="Agrupar por"
              value={view}
              onChange={setView}
              options={[
                { value: "by_type", label: "Tipo" },
                { value: "by_currency", label: "Moneda" },
                { value: "by_liquidity", label: "Liquidez" },
              ]}
            />
          }
        >
          {distData.length ? (
            <Donut data={distData} labels={distLabels} keyOrder={keyOrder} />
          ) : (
            <EmptyState title="Sin datos" />
          )}
        </Card>
      </div>

      <AssetForm
        key={editing === "new" ? "new" : editing?.id}
        asset={editing}
        onClose={() => setEditing(null)}
      />
      <ValuationForm key={valuing?.id} row={valuing} onClose={() => setValuing(null)} />
      <HistoryModal row={historyOf} onClose={() => setHistoryOf(null)} />
    </>
  );
}

function AssetTable({
  title,
  rows,
  onValue,
  onHistory,
  onEdit,
}: {
  title: string;
  rows: AssetRow[];
  onValue: (r: AssetRow) => void;
  onHistory: (r: AssetRow) => void;
  onEdit: (r: AssetRow) => void;
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-ink-3">
              <th className="py-2 font-medium">Nombre</th>
              <th className="py-2 font-medium">Tipo</th>
              <th className="py-2 text-right font-medium">Valor</th>
              <th className="py-2 text-right font-medium">En MXN</th>
              <th className="py-2 text-right font-medium">Cambio</th>
              <th className="py-2 text-right font-medium">Actualizado</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.id}
                className={r.archived ? "border-b border-line opacity-50" : "border-b border-line"}
              >
                <td className="py-2">
                  <p className="font-medium">{r.name}</p>
                  {r.institution && <p className="text-xs text-ink-3">{r.institution}</p>}
                </td>
                <td className="py-2 text-ink-2">{label(ASSET_TYPES, r.type)}</td>
                <td className="tabular py-2 text-right">{money(r.value, r.currency)}</td>
                <td className="tabular py-2 text-right font-medium">{money(r.value_base)}</td>
                <td className="tabular py-2 text-right text-ink-2">
                  {r.change_pct === null
                    ? "—"
                    : `${r.change_pct > 0 ? "▲" : r.change_pct < 0 ? "▼" : ""} ${pct(Math.abs(r.change_pct))}`}
                </td>
                <td className="tabular py-2 text-right text-ink-3">
                  {shortDate(r.last_valuation)}
                </td>
                <td className="py-2">
                  <div className="flex justify-end gap-1">
                    {r.tracks_positions ? (
                      <Link
                        className="btn btn-sm"
                        to="/inversiones"
                        title="Valor calculado con tus posiciones"
                      >
                        <LineChart size={14} /> Posiciones
                      </Link>
                    ) : (
                      <button
                        className="btn btn-sm"
                        onClick={() => onValue(r)}
                        title="Registrar nuevo valor"
                      >
                        <RefreshCw size={14} /> Valor
                      </button>
                    )}
                    <button
                      className="btn btn-sm"
                      onClick={() => onHistory(r)}
                      aria-label="Historial"
                    >
                      <History size={14} />
                    </button>
                    <button className="btn btn-sm" onClick={() => onEdit(r)} aria-label="Editar">
                      <Pencil size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AssetForm({ asset, onClose }: { asset: Asset | "new" | null; onClose: () => void }) {
  const isNew = asset === "new";
  const current = asset && asset !== "new" ? asset : null;
  const { data: settings } = useSettings();
  const [form, setForm] = useState({
    name: current?.name ?? "",
    type: (current?.type ?? "bank") as AssetType,
    currency: current?.currency ?? "MXN",
    liquidity: current?.liquidity ?? "immediate",
    institution: current?.institution ?? "",
    notes: current?.notes ?? "",
    initial_value: "",
    initial_date: todayIso(),
    tracks_positions: false,
  });
  const create = useApiMutation("POST", "/api/assets");
  const update = useApiMutation("PATCH", `/api/assets/${current?.id}`);
  const remove = useApiMutation("DELETE", `/api/assets/${current?.id}`);
  const mutation = isNew ? create : update;

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const body = {
      name: form.name,
      type: form.type,
      is_liability: LIABILITY_TYPES.has(form.type),
      currency: form.currency,
      liquidity: LIABILITY_TYPES.has(form.type) ? "immediate" : form.liquidity,
      institution: form.institution || null,
      notes: form.notes || null,
      ...(isNew
        ? { tracks_positions: form.tracks_positions && POSITION_TYPES.has(form.type) }
        : {}),
      ...(isNew && !form.tracks_positions && form.initial_value !== ""
        ? { initial_value: Number(form.initial_value), initial_date: form.initial_date }
        : {}),
    };
    await mutation.mutateAsync(body);
    onClose();
  };

  return (
    <Modal
      open={asset !== null}
      title={isNew ? "Nuevo activo o deuda" : "Editar"}
      onClose={onClose}
    >
      <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Nombre" className="sm:col-span-2">
          <input
            className="input"
            required
            value={form.name}
            onChange={set("name")}
            placeholder="Ej. Nómina BBVA"
          />
        </Field>
        <Field label="Tipo">
          <select className="input" value={form.type} onChange={set("type")}>
            <optgroup label="Activos">
              <SelectOptions
                options={Object.fromEntries(
                  Object.entries(ASSET_TYPES).filter(([k]) => !LIABILITY_TYPES.has(k)),
                )}
              />
            </optgroup>
            <optgroup label="Deudas">
              <SelectOptions
                options={Object.fromEntries(
                  Object.entries(ASSET_TYPES).filter(([k]) => LIABILITY_TYPES.has(k)),
                )}
              />
            </optgroup>
          </select>
        </Field>
        <Field label="Moneda">
          <CurrencySelect
            value={form.currency}
            onChange={set("currency")}
            currencies={settings?.currencies}
          />
        </Field>
        {!LIABILITY_TYPES.has(form.type) && (
          <Field label="Liquidez" hint="Qué tan rápido puedes convertirlo en efectivo">
            <select className="input" value={form.liquidity} onChange={set("liquidity")}>
              <SelectOptions options={LIQUIDITY} />
            </select>
          </Field>
        )}
        <Field label="Institución">
          <input
            className="input"
            value={form.institution}
            onChange={set("institution")}
            placeholder="Opcional"
          />
        </Field>
        {isNew && POSITION_TYPES.has(form.type) && (
          <label className="flex items-start gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={form.tracks_positions}
              onChange={(e) => setForm((f) => ({ ...f, tracks_positions: e.target.checked }))}
            />
            <span>
              Llevar posiciones (acciones, ETFs o cripto)
              <span className="block text-xs text-ink-3">
                Registras compras y ventas en Inversiones y el valor se calcula con precios de
                mercado.
              </span>
            </span>
          </label>
        )}
        {isNew && !form.tracks_positions && (
          <>
            <Field label={LIABILITY_TYPES.has(form.type) ? "Saldo adeudado" : "Valor actual"}>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0"
                value={form.initial_value}
                onChange={set("initial_value")}
              />
            </Field>
            <Field label="Fecha del valor">
              <input
                className="input"
                type="date"
                value={form.initial_date}
                onChange={set("initial_date")}
              />
            </Field>
          </>
        )}
        <Field label="Notas" className="sm:col-span-2">
          <textarea className="input" rows={2} value={form.notes} onChange={set("notes")} />
        </Field>
        <div className="sm:col-span-2">
          <ErrorText error={mutation.error ?? remove.error} />
        </div>
        <div className="flex flex-wrap justify-between gap-2 sm:col-span-2">
          {current ? (
            <div className="flex gap-2">
              <button
                type="button"
                className="btn"
                onClick={async () => {
                  await update.mutateAsync({ archived: !current.archived });
                  onClose();
                }}
              >
                <Archive size={14} /> {current.archived ? "Desarchivar" : "Archivar"}
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={async () => {
                  if (
                    !confirm(
                      `¿Eliminar "${current.name}" y todo su historial? No se puede deshacer.`,
                    )
                  )
                    return;
                  await remove.mutateAsync(undefined);
                  onClose();
                }}
              >
                <Trash2 size={14} /> Eliminar
              </button>
            </div>
          ) : (
            <span />
          )}
          <button className="btn btn-primary" disabled={mutation.isPending}>
            Guardar
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function CurrencySelect({
  value,
  onChange,
  currencies = ["MXN", "USD", "EUR"],
}: {
  value: string;
  onChange: (e: { target: { value: string } }) => void;
  currencies?: string[];
}) {
  const list = Array.from(new Set(["MXN", ...currencies, value]));
  return (
    <select className="input" value={value} onChange={onChange}>
      {list.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  );
}

function ValuationForm({ row, onClose }: { row: AssetRow | null; onClose: () => void }) {
  const [date, setDate] = useState(todayIso());
  const [value, setValue] = useState("");
  const add = useApiMutation("POST", `/api/assets/${row?.id}/valuations`);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await add.mutateAsync({ date, value: Number(value) });
    setValue("");
    onClose();
  };
  return (
    <Modal open={row !== null} title={`Actualizar valor · ${row?.name ?? ""}`} onClose={onClose}>
      <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label={`${row?.is_liability ? "Saldo adeudado" : "Valor"} (${row?.currency})`}>
          <input
            className="input"
            type="number"
            step="any"
            min="0"
            required
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={row?.value != null ? String(row.value) : ""}
          />
        </Field>
        <Field label="Fecha">
          <input
            className="input"
            type="date"
            required
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </Field>
        <p className="text-xs text-ink-3 sm:col-span-2">
          Si ya hay una valuación en esa fecha, se reemplaza.
        </p>
        <div className="sm:col-span-2">
          <ErrorText error={add.error} />
        </div>
        <div className="flex justify-end sm:col-span-2">
          <button className="btn btn-primary" disabled={add.isPending}>
            Guardar valuación
          </button>
        </div>
      </form>
    </Modal>
  );
}

function HistoryModal({ row, onClose }: { row: AssetRow | null; onClose: () => void }) {
  const { data: vals = [] } = useValuations(row?.id ?? null);
  const remove = useApiMutation<{ id: number }>("DELETE", (b) => `/api/valuations/${b.id}`);
  const shortD = (iso: string) => shortDate(iso);
  return (
    <Modal open={row !== null} title={`Historial · ${row?.name ?? ""}`} onClose={onClose} wide>
      {vals.length > 1 && (
        <div className="mb-4 h-48">
          <TimeLineChart
            data={vals}
            xKey="date"
            xFormat={shortD}
            area
            series={[{ key: "value", label: row?.currency ?? "", color: SERIES[0] }]}
          />
        </div>
      )}
      <ul className="max-h-72 divide-y divide-line overflow-auto text-sm">
        {[...vals].reverse().map((v) => (
          <li key={v.id} className="flex items-center gap-3 py-2">
            <span className="tabular w-28 text-ink-3">{shortDate(v.date)}</span>
            <span className="tabular flex-1 font-medium">{money(v.value, row?.currency)}</span>
            <button
              className="btn btn-sm btn-danger"
              aria-label="Eliminar valuación"
              onClick={() => confirm("¿Eliminar esta valuación?") && remove.mutate({ id: v.id })}
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
