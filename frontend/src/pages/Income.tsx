import { Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import {
  useApiMutation,
  useAssets,
  useIncomeByMonth,
  useIncomeEntries,
  useIncomeSourceRows,
  useIncomeSources,
  useSettings,
} from "../api/hooks";
import type { IncomeSource } from "../api/types";
import {
  ChartFrame,
  DataTable,
  Legend,
  StackedBars,
  type SeriesDef,
} from "../components/charts/Charts";
import { OTHER, SERIES } from "../components/charts/palette";
import {
  Card,
  EmptyState,
  ErrorText,
  Field,
  Modal,
  PageHeader,
  Segmented,
  SelectOptions,
  StatTile,
} from "../components/ui";
import { money, monthLabel, pct, shortDate, todayIso } from "../lib/format";
import {
  FREQUENCIES,
  INCOME_TYPES,
  PASSIVE_INCOME_TYPES,
  label,
  type IncomeType,
} from "../lib/labels";
import { CurrencySelect } from "./Assets";

export function IncomePage() {
  const { data: sources = [] } = useIncomeSources();
  const { data: rows = [] } = useIncomeSourceRows();
  const { data: entries = [] } = useIncomeEntries();
  const [months, setMonths] = useState(12);
  const { data: byMonth = [] } = useIncomeByMonth(months);
  const [editing, setEditing] = useState<IncomeSource | "new" | null>(null);
  const [entryFor, setEntryFor] = useState<IncomeSource | null>(null);
  const remove = useApiMutation<{ id: number }>("DELETE", (b) => `/api/income/entries/${b.id}`);

  // Color por fuente según su id: estable aunque cambie el periodo.
  const series: SeriesDef[] = useMemo(
    () =>
      [...sources]
        .sort((a, b) => a.id - b.id)
        .map((s, i) => ({
          key: s.name,
          label: s.name,
          color: i < SERIES.length ? SERIES[i] : OTHER,
        })),
    [sources],
  );
  const chartData = byMonth.map((m) => ({ month: m.month, ...m.by_source }));
  const sourceName = new Map(sources.map((s) => [s.id, s]));

  const expected = rows.filter((r) => r.active).reduce((s, r) => s + r.expected_monthly_base, 0);
  const actual = rows.reduce((s, r) => s + r.actual_monthly_base, 0);
  const passive = rows.filter((r) => r.is_passive).reduce((s, r) => s + r.actual_monthly_base, 0);

  return (
    <>
      <PageHeader
        title="Ingresos"
        subtitle="Todas tus fuentes: salario, negocios, rentas, dividendos, intereses…"
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            <Plus size={16} /> Nueva fuente
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Esperado / mes" value={money(expected)} />
        <StatTile label="Real / mes (prom. 12 m)" value={money(actual)} />
        <StatTile
          label="Pasivo / mes"
          value={money(passive)}
          hint={actual ? `${pct((passive / actual) * 100, 0)} del total` : undefined}
        />
        <StatTile label="Fuentes activas" value={String(rows.filter((r) => r.active).length)} />
      </div>

      <Card
        className="mt-4"
        title="Ingreso neto por mes"
        subtitle="Apilado por fuente, después de impuestos, en MXN"
        actions={
          <Segmented
            label="Periodo"
            value={months}
            onChange={setMonths}
            options={[
              { value: 6, label: "6 m" },
              { value: 12, label: "12 m" },
              { value: 24, label: "24 m" },
            ]}
          />
        }
      >
        {entries.length ? (
          <>
            <ChartFrame
              chart={
                <StackedBars data={chartData} xKey="month" series={series} xFormat={monthLabel} />
              }
              table={
                <DataTable
                  columns={[
                    { key: "month", label: "Mes" },
                    ...series.map((s) => ({ key: s.key, label: s.label, money: true })),
                  ]}
                  rows={chartData}
                />
              }
            />
            <Legend series={series} />
          </>
        ) : (
          <EmptyState title="Aún no registras ingresos">
            Crea una fuente y registra tu primer cobro.
          </EmptyState>
        )}
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card title="Fuentes de ingreso">
          {rows.length === 0 ? (
            <EmptyState title="Sin fuentes" />
          ) : (
            <ul className="divide-y divide-line">
              {rows.map((r) => {
                const source = sourceName.get(r.id);
                const gap = r.expected_monthly_base
                  ? (r.actual_monthly_base / r.expected_monthly_base) * 100
                  : null;
                return (
                  <li key={r.id} className={r.active ? "py-3" : "py-3 opacity-50"}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="inline-block size-2.5 rounded-sm"
                        style={{ background: series.find((s) => s.key === r.name)?.color }}
                      />
                      <span className="font-medium">{r.name}</span>
                      <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-ink-2">
                        {label(INCOME_TYPES, r.type)}
                      </span>
                      {r.is_passive && (
                        <span className="rounded bg-accent-soft px-1.5 py-0.5 text-xs text-ink">
                          Pasivo
                        </span>
                      )}
                      <div className="ml-auto flex gap-1">
                        <button
                          className="btn btn-sm"
                          onClick={() => source && setEntryFor(source)}
                        >
                          <Plus size={14} /> Registrar cobro
                        </button>
                        <button
                          className="btn btn-sm"
                          aria-label="Editar"
                          onClick={() => source && setEditing(source)}
                        >
                          <Pencil size={14} />
                        </button>
                      </div>
                    </div>
                    <p className="tabular mt-1 text-xs text-ink-3">
                      Esperado (bruto) {money(r.expected_amount, r.currency)}{" "}
                      {label(FREQUENCIES, r.frequency).toLowerCase()} · real neto{" "}
                      {money(r.actual_monthly_base)}/mes
                      {gap !== null && ` (${pct(gap, 0)} de lo esperado)`}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card title="Cobros recientes">
          {entries.length === 0 ? (
            <EmptyState title="Sin cobros" />
          ) : (
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-ink-3">
                    <th className="py-2 font-medium">Fecha</th>
                    <th className="py-2 font-medium">Fuente</th>
                    <th className="py-2 text-right font-medium">Bruto</th>
                    <th className="py-2 text-right font-medium">Neto</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {entries.slice(0, 100).map((e) => {
                    const s = sourceName.get(e.source_id);
                    return (
                      <tr key={e.id} className="border-b border-line">
                        <td className="tabular py-2 text-ink-3">{shortDate(e.date)}</td>
                        <td className="py-2">{s?.name}</td>
                        <td className="tabular py-2 text-right text-ink-2">
                          {money(e.gross_amount, s?.currency)}
                        </td>
                        <td className="tabular py-2 text-right font-medium">
                          {money(e.net_amount, s?.currency)}
                        </td>
                        <td className="py-2 text-right">
                          <button
                            className="btn btn-sm btn-danger"
                            aria-label="Eliminar cobro"
                            onClick={() =>
                              confirm("¿Eliminar este cobro?") && remove.mutate({ id: e.id })
                            }
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <SourceForm
        key={editing === "new" ? "new" : editing?.id}
        source={editing}
        onClose={() => setEditing(null)}
      />
      <EntryForm key={entryFor?.id} source={entryFor} onClose={() => setEntryFor(null)} />
    </>
  );
}

function SourceForm({
  source,
  onClose,
}: {
  source: IncomeSource | "new" | null;
  onClose: () => void;
}) {
  const current = source && source !== "new" ? source : null;
  const { data: settings } = useSettings();
  const { data: assets = [] } = useAssets();
  const [form, setForm] = useState({
    name: current?.name ?? "",
    type: (current?.type ?? "salary") as IncomeType,
    is_passive: current?.is_passive ?? false,
    currency: current?.currency ?? "MXN",
    frequency: current?.frequency ?? "monthly",
    expected_amount: String(current?.expected_amount ?? ""),
    asset_id: current?.asset_id ? String(current.asset_id) : "",
    active: current?.active ?? true,
    notes: current?.notes ?? "",
  });
  const create = useApiMutation("POST", "/api/income/sources");
  const update = useApiMutation("PATCH", `/api/income/sources/${current?.id}`);
  const remove = useApiMutation("DELETE", `/api/income/sources/${current?.id}`);
  const mutation = current ? update : create;
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await mutation.mutateAsync({
      ...form,
      expected_amount: Number(form.expected_amount || 0),
      asset_id: form.asset_id ? Number(form.asset_id) : null,
      notes: form.notes || null,
    });
    onClose();
  };

  return (
    <Modal
      open={source !== null}
      title={current ? "Editar fuente" : "Nueva fuente de ingreso"}
      onClose={onClose}
    >
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label="Nombre" className="sm:col-span-2">
          <input
            className="input"
            required
            value={form.name}
            onChange={set("name")}
            placeholder="Ej. Sueldo empresa X"
          />
        </Field>
        <Field label="Tipo">
          <select
            className="input"
            value={form.type}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                type: e.target.value as IncomeType,
                is_passive: PASSIVE_INCOME_TYPES.has(e.target.value),
              }))
            }
          >
            <SelectOptions options={INCOME_TYPES} />
          </select>
        </Field>
        <Field label="Frecuencia">
          <select className="input" value={form.frequency} onChange={set("frequency")}>
            <SelectOptions options={FREQUENCIES} />
          </select>
        </Field>
        <Field label="Monto esperado por periodo">
          <input
            className="input"
            type="number"
            step="0.01"
            min="0"
            value={form.expected_amount}
            onChange={set("expected_amount")}
          />
        </Field>
        <Field label="Moneda">
          <CurrencySelect
            value={form.currency}
            onChange={set("currency")}
            currencies={settings?.currencies}
          />
        </Field>
        <Field
          label="Activo que lo genera"
          hint="Ej. el inmueble que rentas o la cuenta de inversión"
          className="sm:col-span-2"
        >
          <select className="input" value={form.asset_id} onChange={set("asset_id")}>
            <option value="">Ninguno</option>
            {assets
              .filter((a) => !a.is_liability)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
          </select>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_passive}
            onChange={(e) => setForm((f) => ({ ...f, is_passive: e.target.checked }))}
          />
          Ingreso pasivo
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
          />
          Activa
        </label>
        <div className="sm:col-span-2">
          <ErrorText error={mutation.error ?? remove.error} />
        </div>
        <div className="flex justify-between gap-2 sm:col-span-2">
          {current ? (
            <button
              type="button"
              className="btn btn-danger"
              onClick={async () => {
                if (!confirm(`¿Eliminar "${current.name}" y todos sus cobros?`)) return;
                await remove.mutateAsync(undefined);
                onClose();
              }}
            >
              <Trash2 size={14} /> Eliminar
            </button>
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

function EntryForm({ source, onClose }: { source: IncomeSource | null; onClose: () => void }) {
  const [form, setForm] = useState({
    date: todayIso(),
    gross_amount: source?.expected_amount ? String(source.expected_amount) : "",
    tax_withheld: "",
    notes: "",
  });
  const add = useApiMutation("POST", `/api/income/sources/${source?.id}/entries`);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await add.mutateAsync({
      date: form.date,
      gross_amount: Number(form.gross_amount),
      tax_withheld: Number(form.tax_withheld || 0),
      notes: form.notes || null,
    });
    onClose();
  };
  const net = Number(form.gross_amount || 0) - Number(form.tax_withheld || 0);
  return (
    <Modal
      open={source !== null}
      title={`Registrar cobro · ${source?.name ?? ""}`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label={`Monto bruto (${source?.currency})`}>
          <input
            className="input"
            type="number"
            step="0.01"
            min="0"
            required
            autoFocus
            value={form.gross_amount}
            onChange={set("gross_amount")}
          />
        </Field>
        <Field label="Impuestos / retención">
          <input
            className="input"
            type="number"
            step="0.01"
            min="0"
            value={form.tax_withheld}
            onChange={set("tax_withheld")}
          />
        </Field>
        <Field label="Fecha">
          <input className="input" type="date" required value={form.date} onChange={set("date")} />
        </Field>
        <div className="self-end pb-2 text-sm text-ink-2">
          Neto:{" "}
          <span className="tabular font-semibold text-ink">{money(net, source?.currency)}</span>
        </div>
        <Field label="Notas" className="sm:col-span-2">
          <input className="input" value={form.notes} onChange={set("notes")} />
        </Field>
        <div className="sm:col-span-2">
          <ErrorText error={add.error} />
        </div>
        <div className="flex justify-end sm:col-span-2">
          <button className="btn btn-primary" disabled={add.isPending}>
            Guardar
          </button>
        </div>
      </form>
    </Modal>
  );
}
