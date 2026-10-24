import { Check, Pencil, Plus, Trash2, Undo2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  useApiMutation,
  useAssets,
  useExpenses,
  useExpensesByCategory,
  useSettings,
  useSummary,
  useUpcoming,
} from "../api/hooks";
import type { FixedExpense, UpcomingPayment } from "../api/types";
import { HBars } from "../components/charts/Charts";
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
  StatusBadge,
} from "../components/ui";
import { money, shortDate, todayIso } from "../lib/format";
import { EXPENSE_CATEGORIES, FREQUENCIES, label, type ExpenseCategory } from "../lib/labels";
import { CurrencySelect } from "./Assets";

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

export function ExpensesPage() {
  const { data: expenses = [] } = useExpenses();
  const { data: byCategory = [] } = useExpensesByCategory();
  const { data: summary } = useSummary();
  const [days, setDays] = useState(30);
  const { data: upcoming = [] } = useUpcoming(days);
  const [editing, setEditing] = useState<FixedExpense | "new" | null>(null);

  const overdue = upcoming.filter((u) => u.status === "overdue");
  const pendingTotal = upcoming
    .filter((u) => u.status !== "paid")
    .reduce((s, u) => s + u.amount_base, 0);

  return (
    <>
      <PageHeader
        title="Gastos fijos"
        subtitle="Renta, servicios, seguros, suscripciones y cualquier pago recurrente."
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            <Plus size={16} /> Nuevo gasto fijo
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Total mensualizado" value={money(summary?.monthly_fixed_expenses)} />
        <StatTile label="Anual" value={money((summary?.monthly_fixed_expenses ?? 0) * 12)} />
        <StatTile label={`Por pagar (${days} días)`} value={money(pendingTotal)} />
        <StatTile
          label="Vencidos"
          value={String(overdue.length)}
          tone={overdue.length ? "critical" : "neutral"}
          hint={overdue.length ? "Revisa los pagos atrasados" : "Todo al corriente"}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_380px]">
        <Card
          title="Calendario de pagos"
          actions={
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
          }
        >
          {upcoming.length ? (
            <ul className="divide-y divide-line">
              {upcoming.map((u) => (
                <PaymentRow key={`${u.expense_id}-${u.due_date}`} item={u} />
              ))}
            </ul>
          ) : (
            <EmptyState title="Sin vencimientos en este periodo" />
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
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-3">
                  <th className="py-2 font-medium">Concepto</th>
                  <th className="py-2 font-medium">Categoría</th>
                  <th className="py-2 font-medium">Frecuencia</th>
                  <th className="py-2 text-right font-medium">Monto</th>
                  <th className="py-2 text-right font-medium">Al mes</th>
                  <th className="py-2 text-right font-medium">Día</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {expenses.map((e) => (
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
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
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
