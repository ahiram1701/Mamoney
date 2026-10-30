import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileUp,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

import { api } from "../api/client";
import {
  useApiMutation,
  useAssets,
  useBudget,
  useBudgetReport,
  useIncomeSources,
  useSpending,
} from "../api/hooks";
import type {
  BudgetCategoryRow,
  ImportPreview,
  ImportPreviewRow,
  SpendingCategory,
  SpendingItem,
} from "../api/types";
import {
  Card,
  EmptyState,
  ErrorText,
  Field,
  Modal,
  PageHeader,
  SelectOptions,
  StatTile,
} from "../components/ui";
import { money, pct, shortDate, todayIso } from "../lib/format";
import { SPENDING_CATEGORIES, label } from "../lib/labels";

const thisMonth = () => todayIso().slice(0, 7);

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthName(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("es-MX", { month: "long", year: "numeric" });
}

const STATUS_COLOR: Record<BudgetCategoryRow["status"], string> = {
  ok: "var(--series-1)",
  warning: "var(--warning)",
  over: "var(--critical)",
  no_budget: "var(--text-3)",
};

function BudgetBar({ row }: { row: BudgetCategoryRow }) {
  const width = row.limit ? Math.min((row.spent / row.limit) * 100, 100) : 0;
  return (
    <li className="text-sm">
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 text-ink-2">
          {row.status === "over" && <AlertTriangle size={14} color="var(--critical)" aria-hidden />}
          {row.status === "warning" && (
            <AlertTriangle size={14} color="var(--serious)" aria-hidden />
          )}
          {row.status === "ok" && <CheckCircle2 size={14} color="var(--good)" aria-hidden />}
          {label(SPENDING_CATEGORIES, row.category)}
        </span>
        <span className="tabular">
          <strong>{money(row.spent)}</strong>
          {row.limit != null && <span className="text-ink-3"> / {money(row.limit)}</span>}
        </span>
      </div>
      {row.limit != null ? (
        <>
          <div
            className="h-2 rounded-full bg-surface-2"
            role="meter"
            aria-valuenow={row.used_pct ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${label(SPENDING_CATEGORIES, row.category)}: ${pct(row.used_pct, 0)} del presupuesto`}
          >
            <div
              className="h-2 rounded-full"
              style={{ width: `${width}%`, background: STATUS_COLOR[row.status] }}
            />
          </div>
          <p className="mt-0.5 text-xs text-ink-3">
            {row.status === "over"
              ? `Excedido por ${money(row.spent - row.limit)}`
              : `${pct(row.used_pct, 0)} usado · al ritmo actual cerrarías en ${money(row.projected)}`}
          </p>
        </>
      ) : (
        <p className="text-xs text-ink-3">Sin presupuesto</p>
      )}
    </li>
  );
}

export function VariableSpending({ tabs }: { tabs: ReactNode }) {
  const [month, setMonth] = useState(thisMonth);
  const { data: report } = useBudgetReport(month);
  const { data: items = [] } = useSpending(month);
  const [editing, setEditing] = useState<SpendingItem | "new" | null>(null);
  const [budgetOpen, setBudgetOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const remove = useApiMutation<{ id: number }>("DELETE", (b) => `/api/spending/${b.id}`);
  const isCurrent = month === thisMonth();
  const projectedTotal = report?.categories.reduce((s, r) => s + r.projected, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Gastos"
        subtitle="Súper, gasolina, restaurantes… y tu presupuesto mensual por categoría."
        actions={
          <>
            {tabs}
            <button className="btn" onClick={() => setImportOpen(true)}>
              <FileUp size={16} /> Importar estado de cuenta
            </button>
            <button className="btn btn-primary" onClick={() => setEditing("new")}>
              <Plus size={16} /> Nuevo gasto
            </button>
          </>
        }
      />

      <div className="mb-4 flex items-center gap-2">
        <button
          className="btn btn-sm"
          onClick={() => setMonth((m) => shiftMonth(m, -1))}
          aria-label="Mes anterior"
        >
          <ChevronLeft size={16} />
        </button>
        <h2 className="min-w-40 text-center font-semibold first-letter:uppercase">
          {monthName(month)}
        </h2>
        <button
          className="btn btn-sm"
          onClick={() => setMonth((m) => shiftMonth(m, 1))}
          disabled={isCurrent}
          aria-label="Mes siguiente"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Gastado" value={money(report?.spent)} />
        <StatTile
          label="Presupuesto"
          value={report?.limit != null ? money(report.limit) : "—"}
          hint={
            report?.used_pct != null ? `${pct(report.used_pct, 0)} usado` : "Define tus límites"
          }
        />
        <StatTile
          label={isCurrent ? "Proyección al cierre" : "Movimientos"}
          value={isCurrent ? money(projectedTotal) : String(items.length)}
          tone={
            isCurrent && report?.limit != null && projectedTotal > report.limit
              ? "critical"
              : "neutral"
          }
          hint={
            isCurrent && report
              ? `Día ${report.days_elapsed} de ${report.days_in_month}`
              : undefined
          }
        />
        <StatTile
          label="Disponible"
          value={report?.limit != null ? money(report.limit - report.spent) : "—"}
          tone={report?.limit != null && report.spent > report.limit ? "critical" : "good"}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[380px_1fr]">
        <Card
          title="Presupuesto por categoría"
          actions={
            <button className="btn btn-sm" onClick={() => setBudgetOpen(true)}>
              <Pencil size={14} /> Editar
            </button>
          }
        >
          {report && report.categories.length ? (
            <ul className="space-y-4">
              {report.categories.map((row) => (
                <BudgetBar key={row.category} row={row} />
              ))}
            </ul>
          ) : (
            <EmptyState title="Sin gastos ni presupuesto este mes">
              Registra un gasto, importa tu estado de cuenta o define tus límites.
            </EmptyState>
          )}
        </Card>

        <Card title="Movimientos" subtitle={`${items.length} en ${monthName(month)}`}>
          {items.length === 0 ? (
            <EmptyState title="Sin movimientos" />
          ) : (
            <ul className="max-h-[560px] divide-y divide-line overflow-auto">
              {items.map((s) => (
                <li key={s.id} className="flex items-center gap-3 py-2 text-sm">
                  <span className="tabular w-16 shrink-0 text-xs text-ink-3">
                    {shortDate(s.date).slice(0, -5)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate">{s.description}</p>
                    <p className="text-xs text-ink-3">
                      {label(SPENDING_CATEGORIES, s.category)}
                      {s.source === "import" && " · importado"}
                    </p>
                  </div>
                  <span className="tabular font-medium">{money(s.amount, s.currency)}</span>
                  <button
                    className="btn btn-sm"
                    aria-label="Editar gasto"
                    onClick={() => setEditing(s)}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    className="btn btn-sm btn-danger"
                    aria-label="Eliminar gasto"
                    onClick={() => confirm("¿Eliminar este gasto?") && remove.mutate({ id: s.id })}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <SpendingForm
        key={editing === "new" ? "new" : editing?.id}
        item={editing}
        onClose={() => setEditing(null)}
      />
      <BudgetForm open={budgetOpen} onClose={() => setBudgetOpen(false)} />
      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} />
    </>
  );
}

function SpendingForm({
  item,
  onClose,
}: {
  item: SpendingItem | "new" | null;
  onClose: () => void;
}) {
  const current = item && item !== "new" ? item : null;
  const { data: assets = [] } = useAssets();
  const [form, setForm] = useState({
    date: current?.date ?? todayIso(),
    amount: current ? String(current.amount) : "",
    category: (current?.category ?? "groceries") as SpendingCategory,
    description: current?.description ?? "",
    payment_asset_id: current?.payment_asset_id ? String(current.payment_asset_id) : "",
  });
  const create = useApiMutation("POST", "/api/spending");
  const update = useApiMutation("PATCH", `/api/spending/${current?.id}`);
  const mutation = current ? update : create;
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await mutation.mutateAsync({
      ...form,
      amount: Number(form.amount),
      payment_asset_id: form.payment_asset_id ? Number(form.payment_asset_id) : null,
    });
    onClose();
  };

  return (
    <Modal open={item !== null} title={current ? "Editar gasto" : "Nuevo gasto"} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label="Descripción" className="sm:col-span-2">
          <input
            className="input"
            required
            value={form.description}
            onChange={set("description")}
            placeholder="Ej. Súper semanal"
          />
        </Field>
        <Field label="Monto (MXN)">
          <input
            className="input"
            type="number"
            step="0.01"
            min="0.01"
            required
            value={form.amount}
            onChange={set("amount")}
          />
        </Field>
        <Field label="Fecha">
          <input className="input" type="date" required value={form.date} onChange={set("date")} />
        </Field>
        <Field label="Categoría">
          <select className="input" value={form.category} onChange={set("category")}>
            <SelectOptions options={SPENDING_CATEGORIES} />
          </select>
        </Field>
        <Field label="Pagado con">
          <select
            className="input"
            value={form.payment_asset_id}
            onChange={set("payment_asset_id")}
          >
            <option value="">Sin especificar</option>
            {assets
              .filter((a) => !a.tracks_positions)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
          </select>
        </Field>
        <div className="sm:col-span-2">
          <ErrorText error={mutation.error} />
        </div>
        <div className="flex justify-end sm:col-span-2">
          <button className="btn btn-primary" disabled={mutation.isPending}>
            Guardar
          </button>
        </div>
      </form>
    </Modal>
  );
}

function BudgetForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: budget } = useBudget();
  const [values, setValues] = useState<Record<string, string> | null>(null);
  const save = useApiMutation("PUT", "/api/budget");
  const current =
    values ?? Object.fromEntries(Object.entries(budget ?? {}).map(([k, v]) => [k, String(v)]));
  const total = Object.values(current).reduce((s, v) => s + (Number(v) || 0), 0);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const limits = Object.fromEntries(
      Object.keys(SPENDING_CATEGORIES).map((k) => [k, current[k] ? Number(current[k]) : null]),
    );
    await save.mutateAsync({ limits });
    setValues(null);
    onClose();
  };

  return (
    <Modal open={open} title="Presupuesto mensual" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-ink-2">
          Límite mensual por categoría, en pesos. Deja vacío para no presupuestar esa categoría.
        </p>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          {Object.entries(SPENDING_CATEGORIES).map(([key, name]) => (
            <label key={key} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-ink-2">{name}</span>
              <input
                className="input w-28 text-right"
                type="number"
                min="0"
                step="100"
                value={current[key] ?? ""}
                onChange={(e) => setValues({ ...current, [key]: e.target.value })}
              />
            </label>
          ))}
        </div>
        <p className="text-sm">
          Total: <strong className="tabular">{money(total)}</strong> al mes
        </p>
        <ErrorText error={save.error} />
        <div className="flex justify-end">
          <button className="btn btn-primary" disabled={save.isPending}>
            Guardar presupuesto
          </button>
        </div>
      </form>
    </Modal>
  );
}

type RowChoice = ImportPreviewRow & {
  action: "expense" | "income" | "skip";
  income_source_id?: number;
};

function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: assets = [] } = useAssets();
  const { data: sources = [] } = useIncomeSources();
  const [file, setFile] = useState<File | null>(null);
  const [assetId, setAssetId] = useState("");
  const [invert, setInvert] = useState(false);
  const [rows, setRows] = useState<RowChoice[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<string | null>(null);

  const reset = () => {
    setFile(null);
    setRows(null);
    setResult(null);
    setError(null);
  };

  const loadPreview = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("invert", String(invert));
      if (assetId) body.append("asset_id", assetId);
      const preview = await api<ImportPreview>("/api/import/preview", { method: "POST", body });
      setRows(
        preview.rows.map((r) => ({
          ...r,
          action: r.duplicate ? "skip" : r.kind,
          income_source_id: sources[0]?.id,
        })),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const update = (key: string, patch: Partial<RowChoice>) =>
    setRows((rs) => rs?.map((r) => (r.key === key ? { ...r, ...patch } : r)) ?? null);

  const summary = useMemo(() => {
    const chosen = rows ?? [];
    return {
      expenses: chosen.filter((r) => r.action === "expense").length,
      income: chosen.filter((r) => r.action === "income").length,
      skip: chosen.filter((r) => r.action === "skip").length,
    };
  }, [rows]);

  const commit = async () => {
    if (!rows) return;
    setBusy(true);
    setError(null);
    try {
      const counts = await api<Record<string, number>>("/api/import/commit", {
        method: "POST",
        json: {
          asset_id: assetId ? Number(assetId) : null,
          rows: rows.map((r) => ({
            key: r.key,
            date: r.date,
            description: r.description,
            amount: r.amount,
            kind: r.action,
            category: r.category ?? "other",
            income_source_id: r.action === "income" ? r.income_source_id : null,
          })),
        },
      });
      setResult(
        `Importados ${counts.expenses} gastos y ${counts.income} ingresos` +
          (counts.duplicates ? `; ${counts.duplicates} ya existían` : ""),
      );
      setRows(null);
      await qc.invalidateQueries();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      wide
      title="Importar estado de cuenta"
      onClose={() => {
        reset();
        onClose();
      }}
    >
      {result ? (
        <div className="space-y-4">
          <p className="flex items-center gap-2 text-sm">
            <CheckCircle2 size={18} color="var(--good)" aria-hidden /> {result}.
          </p>
          <button className="btn" onClick={reset}>
            Importar otro archivo
          </button>
        </div>
      ) : rows === null ? (
        <form onSubmit={loadPreview} className="grid gap-3 sm:grid-cols-2">
          <p className="text-sm text-ink-2 sm:col-span-2">
            Descarga de tu banco el estado de cuenta en <strong>CSV</strong> o <strong>OFX</strong>.
            Antes de guardar podrás revisar cada movimiento, su categoría y omitir los que no
            quieras.
          </p>
          <Field label="Archivo" className="sm:col-span-2">
            <input
              className="input"
              type="file"
              accept=".csv,.ofx,.qfx,.txt"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <Field label="Cuenta" hint="Opcional: de dónde salieron los gastos">
            <select className="input" value={assetId} onChange={(e) => setAssetId(e.target.value)}>
              <option value="">Sin especificar</option>
              {assets
                .filter((a) => !a.tracks_positions)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
          </Field>
          <label className="flex items-start gap-2 self-end pb-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={invert}
              onChange={(e) => setInvert(e.target.checked)}
            />
            <span>
              Es tarjeta de crédito
              <span className="block text-xs text-ink-3">Los cargos vienen en positivo</span>
            </span>
          </label>
          <div className="sm:col-span-2">
            <ErrorText error={error} />
          </div>
          <div className="flex justify-end sm:col-span-2">
            <button className="btn btn-primary" disabled={!file || busy}>
              {busy ? "Leyendo…" : "Revisar movimientos"}
            </button>
          </div>
        </form>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-ink-2">
            {rows.length} movimientos: {summary.expenses} gastos, {summary.income} ingresos y{" "}
            {summary.skip} omitidos. Los ya importados antes aparecen omitidos.
          </p>
          <div className="max-h-[50vh] overflow-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-3">
                  <th className="py-2 font-medium">Fecha</th>
                  <th className="py-2 font-medium">Descripción</th>
                  <th className="py-2 text-right font-medium">Importe</th>
                  <th className="py-2 font-medium">Guardar como</th>
                  <th className="py-2 font-medium">Categoría / fuente</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.key}
                    className={`border-b border-line ${r.action === "skip" ? "opacity-50" : ""}`}
                  >
                    <td className="tabular py-1.5 text-ink-3">{shortDate(r.date)}</td>
                    <td className="max-w-[220px] truncate py-1.5" title={r.description}>
                      {r.description}
                      {r.duplicate && (
                        <span className="ml-1 text-xs text-ink-3">(ya importado)</span>
                      )}
                    </td>
                    <td className={`tabular py-1.5 text-right ${r.amount < 0 ? "" : "text-good"}`}>
                      {money(r.amount)}
                    </td>
                    <td className="py-1.5">
                      <select
                        className="input py-1"
                        value={r.action}
                        onChange={(e) =>
                          update(r.key, { action: e.target.value as RowChoice["action"] })
                        }
                        aria-label="Guardar como"
                      >
                        <option value="expense">Gasto</option>
                        <option value="income">Ingreso</option>
                        <option value="skip">Omitir</option>
                      </select>
                    </td>
                    <td className="py-1.5">
                      {r.action === "expense" && (
                        <select
                          className="input py-1"
                          value={r.category ?? "other"}
                          onChange={(e) =>
                            update(r.key, { category: e.target.value as SpendingCategory })
                          }
                          aria-label="Categoría"
                        >
                          <SelectOptions options={SPENDING_CATEGORIES} />
                        </select>
                      )}
                      {r.action === "income" &&
                        (sources.length ? (
                          <select
                            className="input py-1"
                            value={r.income_source_id ?? ""}
                            onChange={(e) =>
                              update(r.key, { income_source_id: Number(e.target.value) })
                            }
                            aria-label="Fuente de ingreso"
                          >
                            {sources.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className="text-xs text-critical">Crea una fuente en Ingresos</span>
                        ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ErrorText error={error} />
          <div className="flex justify-between gap-2">
            <button className="btn" onClick={reset}>
              Elegir otro archivo
            </button>
            <button
              className="btn btn-primary"
              onClick={commit}
              disabled={busy || summary.expenses + summary.income === 0}
            >
              {busy ? "Guardando…" : `Importar ${summary.expenses + summary.income} movimientos`}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
