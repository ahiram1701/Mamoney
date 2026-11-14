import { Check, Pencil, Plus, Trash2, Undo2 } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import {
  useApiMutation,
  useAssets,
  useExpenseHistory,
  useExpenseMonth,
  useExpenses,
  useExpensesByCategory,
  useSettings,
  useSummary,
  useUpcoming,
} from "../api/hooks";
import type { FixedExpense, UpcomingPayment } from "../api/types";
import { ChartFrame, DataTable, HBars, Legend, StackedBars } from "../components/charts/Charts";
import { SERIES } from "../components/charts/palette";
import { ListToolbar, NoMatches, SortHeader } from "../components/ListControls";
import { MonthNav } from "../components/MonthNav";
import {
  Card,
  EmptyState,
  ErrorText,
  Field,
  Modal,
  PageHeader,
  ProgressTile,
  Segmented,
  SelectOptions,
  StatTile,
  StatusBadge,
} from "../components/ui";
import { money, monthLabel, pct, shortDate, todayIso } from "../lib/format";
import {
  EXPENSE_CATEGORIES,
  FREQUENCIES,
  SPENDING_CATEGORIES,
  label,
  type ExpenseCategory,
} from "../lib/labels";
import { useListControls } from "../lib/listControls";
import { thisMonth } from "../lib/month";
import { CurrencySelect } from "./Assets";
import { VariableSpending } from "./Spending";

type Tab = "month" | "fixed" | "variables";
const TAB_PARAM: Record<Tab, string | null> = {
  month: null,
  fixed: "fijos",
  variables: "variables",
};

export function ExpensesPage() {
  const [params, setParams] = useSearchParams();
  const param = params.get("tab");
  const tab: Tab = param === "variables" ? "variables" : param === "fijos" ? "fixed" : "month";
  const tabs = (
    <Segmented
      label="Vista de gastos"
      value={tab}
      onChange={(v) => {
        const value = TAB_PARAM[v];
        setParams(value ? { tab: value } : {});
      }}
      options={[
        { value: "month", label: "Este mes" },
        { value: "fixed", label: "Fijos" },
        { value: "variables", label: "Variables y presupuesto" },
      ]}
    />
  );
  if (tab === "variables") return <VariableSpending tabs={tabs} />;
  if (tab === "fixed") return <FixedExpenses tabs={tabs} />;
  return <MonthOverview tabs={tabs} />;
}

const HISTORY_SERIES = [
  { key: "fixed", label: "Fijos", color: SERIES[0] },
  { key: "variable", label: "Variables", color: SERIES[2] },
];

const KIND_LABEL = { fixed: "Fijo", variable: "Variable" } as const;

function MonthOverview({ tabs }: { tabs: ReactNode }) {
  const [month, setMonth] = useState(thisMonth);
  const { data: m } = useExpenseMonth(month);
  const { data: history = [] } = useExpenseHistory(12);
  const isCurrent = month === thisMonth();

  const categories = (m?.by_category ?? []).map((c) => ({
    key: `${c.kind}:${c.category}`,
    value: c.value,
  }));
  const categoryLabels = Object.fromEntries(
    (m?.by_category ?? []).map((c) => [
      `${c.kind}:${c.category}`,
      `${label(c.kind === "fixed" ? EXPENSE_CATEGORIES : SPENDING_CATEGORIES, c.category)} · ${KIND_LABEL[c.kind]}`,
    ]),
  );
  const change = m?.change_pct;

  return (
    <>
      <PageHeader
        title="Gastos"
        subtitle="Todo lo que sale en el mes: pagos fijos y gastos variables."
        actions={tabs}
      />
      <MonthNav month={month} onChange={setMonth} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Gasto del mes"
          value={money(m?.total)}
          tone={change != null && change > 0 ? "critical" : "neutral"}
          hint={
            change != null
              ? `${change > 0 ? "▲" : change < 0 ? "▼" : "="} ${pct(Math.abs(change), 0)} vs. ${money(m?.previous_total, "MXN", true)} del mes anterior`
              : "Sin mes anterior para comparar"
          }
        />
        <ProgressTile
          label="Fijos pagados"
          value={m?.fixed.paid ?? 0}
          max={m?.fixed.total ?? null}
          color="var(--good)"
          hint={
            m?.fixed.overdue_count
              ? `${m.fixed.overdue_count} vencido${m.fixed.overdue_count > 1 ? "s" : ""}`
              : undefined
          }
        />
        <ProgressTile
          label="Variables"
          value={m?.variable.total ?? 0}
          max={m?.variable.limit ?? null}
          hint={m?.variable.limit ? "del presupuesto" : "Sin presupuesto definido"}
        />
        <StatTile
          label={isCurrent ? "Falta por pagar" : "Quedó sin pagar"}
          value={money(m?.fixed.pending)}
          tone={m?.fixed.overdue_count ? "critical" : "neutral"}
          hint={
            m && m.fixed.items.length
              ? `${m.fixed.paid_count} de ${m.fixed.items.length} pagos fijos hechos`
              : undefined
          }
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card title="Por categoría" subtitle="Fijos y variables del mes, en MXN">
          {categories.length ? (
            <HBars data={categories} labels={categoryLabels} />
          ) : (
            <EmptyState title="Sin gastos en este mes" />
          )}
        </Card>
        <Card
          title="Pagos fijos del mes"
          subtitle={`${m?.fixed.paid_count ?? 0} de ${m?.fixed.items.length ?? 0} pagados`}
        >
          {m?.fixed.items.length ? (
            <ul className="divide-y divide-line">
              {m.fixed.items.map((u) => (
                <PaymentRow key={`${u.expense_id}-${u.due_date}`} item={u} />
              ))}
            </ul>
          ) : (
            <EmptyState title="Sin pagos fijos en este mes" />
          )}
        </Card>
      </div>

      <Card
        className="mt-4"
        title="Historial"
        subtitle="Últimos 12 meses. Los fijos cuentan lo pagado o, si no lo registraste, lo programado"
      >
        {history.some((h) => h.total > 0) ? (
          <>
            <ChartFrame
              height={260}
              chart={
                <StackedBars
                  data={history}
                  xKey="month"
                  series={HISTORY_SERIES}
                  xFormat={monthLabel}
                />
              }
              table={
                <DataTable
                  columns={[
                    { key: "month", label: "Mes" },
                    { key: "fixed", label: "Fijos", money: true },
                    { key: "variable", label: "Variables", money: true },
                    { key: "total", label: "Total", money: true },
                  ]}
                  rows={history}
                />
              }
            />
            <Legend series={HISTORY_SERIES} />
          </>
        ) : (
          <EmptyState title="Aún no hay gastos que graficar" />
        )}
      </Card>
    </>
  );
}

const HIDE_PAID_KEY = "mamoney.hide-paid";

function readHidePaid(): boolean {
  try {
    return localStorage.getItem(HIDE_PAID_KEY) === "1";
  } catch {
    return false;
  }
}

const MONTHLY_FACTOR: Record<string, number> = {
  once: 0,
  weekly: 52 / 12,
  biweekly: 2,
  monthly: 1,
  bimonthly: 1 / 2,
  quarterly: 1 / 3,
  semiannual: 1 / 6,
  annual: 1 / 12,
};

function FixedExpenses({ tabs }: { tabs: ReactNode }) {
  const { data: expenses = [] } = useExpenses();
  const { data: byCategory = [] } = useExpensesByCategory();
  const { data: summary } = useSummary();
  const [days, setDays] = useState(30);
  const { data: upcoming = [] } = useUpcoming(days);
  const { data: month } = useExpenseMonth(thisMonth());
  const [editing, setEditing] = useState<FixedExpense | "new" | null>(null);
  const [hidePaid, setHidePaid] = useState(readHidePaid);
  const toggleHidePaid = (value: boolean) => {
    setHidePaid(value);
    try {
      localStorage.setItem(HIDE_PAID_KEY, value ? "1" : "0");
    } catch {
      /* sin almacenamiento: solo no se recuerda */
    }
  };
  const visible = hidePaid ? upcoming.filter((u) => u.status !== "paid") : upcoming;
  const list = useListControls("fixed-expenses", expenses, {
    sorts: {
      name: { label: "Concepto", get: (e) => e.name },
      category: { label: "Categoría", get: (e) => label(EXPENSE_CATEGORIES, e.category) },
      // Frecuencia: de la más seguida (semanal) a la más espaciada (anual).
      frequency: {
        label: "Frecuencia",
        get: (e) => MONTHLY_FACTOR[e.frequency] ?? 0,
        firstDir: "desc",
      },
      amount: { label: "Monto", get: (e) => e.amount },
      monthly: { label: "Al mes", get: (e) => e.amount * (MONTHLY_FACTOR[e.frequency] ?? 1) },
      day: { label: "Día de pago", get: (e) => e.due_day, firstDir: "asc" },
    },
    search: (e) => [e.name, e.notes],
    filter: (e) => e.category,
  });
  const presentCategories = Object.fromEntries(
    Object.entries(EXPENSE_CATEGORIES).filter(([k]) => expenses.some((e) => e.category === k)),
  );

  const overdue = upcoming.filter((u) => u.status === "overdue");
  const pendingTotal = upcoming
    .filter((u) => u.status !== "paid")
    .reduce((s, u) => s + u.amount_base, 0);

  return (
    <>
      <PageHeader
        title="Gastos"
        subtitle="Renta, servicios, seguros, suscripciones y cualquier pago recurrente."
        actions={
          <>
            {tabs}
            <button className="btn btn-primary" onClick={() => setEditing("new")}>
              <Plus size={16} /> Nuevo gasto fijo
            </button>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Total mensualizado"
          value={money(summary?.monthly_fixed_expenses)}
          hint={`${money((summary?.monthly_fixed_expenses ?? 0) * 12)} al año`}
        />
        <ProgressTile
          label="Pagado este mes"
          value={month?.fixed.paid ?? 0}
          max={month?.fixed.total ?? null}
          color="var(--good)"
        />
        <StatTile label={`Por pagar (${days} días)`} value={money(pendingTotal)} />
        <StatTile
          label="Vencidos"
          value={String(overdue.length)}
          tone={overdue.length ? "critical" : "neutral"}
          hint={overdue.length ? "Revisa los pagos atrasados" : "Todo al corriente"}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
        <Card
          title="Calendario de pagos"
          actions={
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs text-ink-2">
                <input
                  type="checkbox"
                  checked={hidePaid}
                  onChange={(e) => toggleHidePaid(e.target.checked)}
                />
                Ocultar pagados
              </label>
              <Segmented
                label="Ventana"
                value={days}
                onChange={setDays}
                options={[
                  { value: 30, label: "30 días" },
                  { value: 60, label: "60 días" },
                  { value: 90, label: "90 días" },
                ]}
              />
            </div>
          }
        >
          {visible.length ? (
            <ul className="divide-y divide-line">
              {visible.map((u) => (
                <PaymentRow key={`${u.expense_id}-${u.due_date}`} item={u} />
              ))}
            </ul>
          ) : (
            <EmptyState
              title={
                hidePaid && upcoming.length
                  ? "Todo pagado en este periodo"
                  : "Sin vencimientos en este periodo"
              }
            />
          )}
        </Card>

        <Card title="Por categoría" subtitle="Equivalente mensual en MXN">
          {byCategory.length ? (
            <HBars data={byCategory} labels={EXPENSE_CATEGORIES} />
          ) : (
            <EmptyState title="Sin datos" />
          )}
        </Card>
      </div>

      <Card className="mt-4" title="Todos los gastos fijos">
        {expenses.length === 0 ? (
          <EmptyState title="Aún no registras gastos fijos" />
        ) : (
          <>
            <ListToolbar
              list={list}
              placeholder="Buscar gasto fijo"
              filterLabel="Categoría"
              filterOptions={presentCategories}
            />
            <NoMatches list={list} />
            {/* Teléfono: tarjetas en lugar de la tabla ancha. */}
            <ul className="divide-y divide-line md:hidden">
              {list.rows.map((e) => (
                <li
                  key={e.id}
                  className={
                    e.active
                      ? "flex items-center gap-3 py-3 text-sm"
                      : "flex items-center gap-3 py-3 text-sm opacity-50"
                  }
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="min-w-0 truncate font-medium">{e.name}</p>
                      <p className="tabular shrink-0 font-semibold">
                        {money(e.amount * (MONTHLY_FACTOR[e.frequency] ?? 1), e.currency)}
                        <span className="text-xs font-normal text-ink-3">/mes</span>
                      </p>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-ink-3">
                      {label(EXPENSE_CATEGORIES, e.category)} ·{" "}
                      {label(FREQUENCIES, e.frequency).toLowerCase()} · día {e.due_day}
                    </p>
                  </div>
                  <button className="btn btn-sm" aria-label="Editar" onClick={() => setEditing(e)}>
                    <Pencil size={14} />
                  </button>
                </li>
              ))}
            </ul>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-ink-3">
                    <SortHeader list={list} sortKey="name">
                      Concepto
                    </SortHeader>
                    <SortHeader list={list} sortKey="category">
                      Categoría
                    </SortHeader>
                    <SortHeader list={list} sortKey="frequency">
                      Frecuencia
                    </SortHeader>
                    <SortHeader list={list} sortKey="amount" align="right">
                      Monto
                    </SortHeader>
                    <SortHeader list={list} sortKey="monthly" align="right">
                      Al mes
                    </SortHeader>
                    <SortHeader list={list} sortKey="day" align="right">
                      Día
                    </SortHeader>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {list.rows.map((e) => (
                    <tr
                      key={e.id}
                      className={
                        e.active ? "border-b border-line" : "border-b border-line opacity-50"
                      }
                    >
                      <td className="py-2 font-medium">{e.name}</td>
                      <td className="py-2 text-ink-2">{label(EXPENSE_CATEGORIES, e.category)}</td>
                      <td className="py-2 text-ink-2">{label(FREQUENCIES, e.frequency)}</td>
                      <td className="tabular py-2 text-right">{money(e.amount, e.currency)}</td>
                      <td className="tabular py-2 text-right font-medium">
                        {money(e.amount * (MONTHLY_FACTOR[e.frequency] ?? 1), e.currency)}
                      </td>
                      <td className="tabular py-2 text-right text-ink-3">{e.due_day}</td>
                      <td className="py-2 text-right">
                        <button
                          className="btn btn-sm"
                          aria-label="Editar"
                          onClick={() => setEditing(e)}
                        >
                          <Pencil size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <ExpenseForm
        key={editing === "new" ? "new" : editing?.id}
        expense={editing}
        onClose={() => setEditing(null)}
      />
    </>
  );
}

function PaymentRow({ item }: { item: UpcomingPayment }) {
  const pay = useApiMutation("POST", "/api/expenses/payments");
  const undo = useApiMutation("DELETE", `/api/expenses/payments/${item.payment_id}`);
  return (
    <li className="flex flex-wrap items-center gap-3 py-2 text-sm">
      <span className="tabular w-24 shrink-0 text-ink-3">{shortDate(item.due_date)}</span>
      <span className="min-w-0 flex-1 truncate">
        {item.name}
        <span className="ml-2 text-xs text-ink-3">{label(EXPENSE_CATEGORIES, item.category)}</span>
      </span>
      <StatusBadge status={item.status} />
      <span className="tabular w-28 text-right font-medium">
        {money(item.amount, item.currency)}
      </span>
      {item.status === "paid" ? (
        <button
          className="btn btn-sm"
          onClick={() => undo.mutate(undefined)}
          aria-label="Deshacer pago"
        >
          <Undo2 size={14} />
        </button>
      ) : (
        <button
          className="btn btn-sm"
          disabled={pay.isPending}
          onClick={() =>
            pay.mutate({
              expense_id: item.expense_id,
              due_date: item.due_date,
              paid_date: todayIso(),
              amount: item.amount,
            })
          }
        >
          <Check size={14} /> Pagado
        </button>
      )}
    </li>
  );
}

function ExpenseForm({
  expense,
  onClose,
}: {
  expense: FixedExpense | "new" | null;
  onClose: () => void;
}) {
  const current = expense && expense !== "new" ? expense : null;
  const { data: settings } = useSettings();
  const { data: assets = [] } = useAssets();
  const [form, setForm] = useState({
    name: current?.name ?? "",
    category: (current?.category ?? "housing") as ExpenseCategory,
    amount: String(current?.amount ?? ""),
    currency: current?.currency ?? "MXN",
    frequency: current?.frequency ?? "monthly",
    due_day: String(current?.due_day ?? 1),
    start_date: current?.start_date ?? todayIso(),
    end_date: current?.end_date ?? "",
    payment_asset_id: current?.payment_asset_id ? String(current.payment_asset_id) : "",
    active: current?.active ?? true,
    notes: current?.notes ?? "",
  });
  const create = useApiMutation("POST", "/api/expenses");
  const update = useApiMutation("PATCH", `/api/expenses/${current?.id}`);
  const remove = useApiMutation("DELETE", `/api/expenses/${current?.id}`);
  const mutation = current ? update : create;
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await mutation.mutateAsync({
      ...form,
      amount: Number(form.amount),
      due_day: Number(form.due_day),
      end_date: form.end_date || null,
      payment_asset_id: form.payment_asset_id ? Number(form.payment_asset_id) : null,
      notes: form.notes || null,
    });
    onClose();
  };

  return (
    <Modal
      open={expense !== null}
      title={current ? "Editar gasto fijo" : "Nuevo gasto fijo"}
      onClose={onClose}
    >
      <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Concepto" className="sm:col-span-2">
          <input
            className="input"
            required
            value={form.name}
            onChange={set("name")}
            placeholder="Ej. Luz CFE"
          />
        </Field>
        <Field label="Categoría">
          <select className="input" value={form.category} onChange={set("category")}>
            <SelectOptions options={EXPENSE_CATEGORIES} />
          </select>
        </Field>
        <Field label="Frecuencia">
          <select className="input" value={form.frequency} onChange={set("frequency")}>
            <SelectOptions options={FREQUENCIES} />
          </select>
        </Field>
        <Field label="Monto por periodo">
          <input
            className="input"
            type="number"
            step="0.01"
            min="0"
            required
            value={form.amount}
            onChange={set("amount")}
          />
        </Field>
        <Field label="Moneda">
          <CurrencySelect
            value={form.currency}
            onChange={set("currency")}
            currencies={settings?.currencies}
          />
        </Field>
        <Field label="Día de pago" hint="Si el mes es más corto se usa el último día">
          <input
            className="input"
            type="number"
            min="1"
            max="31"
            required
            value={form.due_day}
            onChange={set("due_day")}
          />
        </Field>
        <Field label="Desde">
          <input
            className="input"
            type="date"
            required
            value={form.start_date}
            onChange={set("start_date")}
          />
        </Field>
        <Field label="Hasta (opcional)">
          <input className="input" type="date" value={form.end_date} onChange={set("end_date")} />
        </Field>
        <Field label="Se paga desde">
          <select
            className="input"
            value={form.payment_asset_id}
            onChange={set("payment_asset_id")}
          >
            <option value="">Sin especificar</option>
            {assets.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(e) => setForm((f) => ({ ...f, active: e.target.checked }))}
          />
          Activo
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
                if (!confirm(`¿Eliminar "${current.name}" y su historial de pagos?`)) return;
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
