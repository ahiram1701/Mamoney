import { CheckCircle2, Clock, Pencil, Plus, Target, Trash2, TrendingDown } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useApiMutation, useAssets, useGoals } from "../api/hooks";
import type { GoalRow } from "../api/types";
import { money, shortDate, todayIso } from "../lib/format";
import { Card, EmptyState, ErrorText, Field, Modal } from "./ui";

const STATUS: Record<GoalRow["status"], { label: string; color: string; icon: typeof Clock }> = {
  done: { label: "Cumplida", color: "var(--good)", icon: CheckCircle2 },
  on_track: { label: "A tiempo", color: "var(--good)", icon: CheckCircle2 },
  in_progress: { label: "En curso", color: "var(--series-1)", icon: Clock },
  behind: { label: "Atrasada", color: "var(--serious)", icon: TrendingDown },
  stalled: { label: "Sin avance", color: "var(--text-3)", icon: Clock },
  overdue: { label: "Vencida", color: "var(--critical)", icon: TrendingDown },
};

function GoalItem({ goal, onEdit }: { goal: GoalRow; onEdit?: () => void }) {
  const status = STATUS[goal.status];
  const Icon = status.icon;
  return (
    <li className="space-y-1.5 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{goal.name}</p>
          <p className="text-xs text-ink-3">
            {goal.asset_name ? `Ligada a ${goal.asset_name}` : "Monto capturado a mano"}
            {goal.target_date && ` · para el ${shortDate(goal.target_date)}`}
          </p>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-ink-2">
          <Icon size={14} color={status.color} aria-hidden /> {status.label}
        </span>
        {onEdit && (
          <button className="btn btn-sm" onClick={onEdit} aria-label={`Editar ${goal.name}`}>
            <Pencil size={14} />
          </button>
        )}
      </div>
      <div
        className="h-2.5 rounded-full bg-surface-2"
        role="meter"
        aria-valuenow={goal.pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${goal.name}: ${goal.pct.toFixed(0)} %`}
      >
        <div
          className="h-2.5 rounded-full"
          style={{ width: `${goal.pct}%`, background: status.color }}
        />
      </div>
      <p className="tabular text-xs text-ink-2">
        <strong className="text-ink">{money(goal.current)}</strong> de {money(goal.target_amount)} (
        {goal.pct.toFixed(0)} %)
        {goal.remaining > 0 &&
          goal.monthly_needed != null &&
          ` · necesitas ${money(goal.monthly_needed)}/mes`}
        {goal.remaining > 0 && goal.eta && ` · a tu ritmo, lista en ${shortDate(goal.eta)}`}
      </p>
    </li>
  );
}

export function GoalsCard({ compact = false }: { compact?: boolean }) {
  const { data: goals = [] } = useGoals();
  const [editing, setEditing] = useState<GoalRow | "new" | null>(null);
  if (compact && goals.length === 0) return null;
  return (
    <Card
      title="Metas de ahorro"
      subtitle={compact ? undefined : "El avance sale del activo ligado o del monto que captures"}
      actions={
        compact ? undefined : (
          <button className="btn btn-sm" onClick={() => setEditing("new")}>
            <Plus size={14} /> Nueva meta
          </button>
        )
      }
    >
      {goals.length === 0 ? (
        <EmptyState title="Sin metas">
          <p>Por ejemplo: fondo de emergencia de 6 meses, enganche de un depa o un viaje.</p>
          <button className="btn btn-primary mt-3" onClick={() => setEditing("new")}>
            <Target size={16} /> Crear mi primera meta
          </button>
        </EmptyState>
      ) : (
        <ul className="divide-y divide-line">
          {goals.map((g) => (
            <GoalItem key={g.id} goal={g} onEdit={compact ? undefined : () => setEditing(g)} />
          ))}
        </ul>
      )}
      <GoalForm
        key={editing === "new" ? "new" : editing?.id}
        goal={editing}
        onClose={() => setEditing(null)}
      />
    </Card>
  );
}

function GoalForm({ goal, onClose }: { goal: GoalRow | "new" | null; onClose: () => void }) {
  const current = goal && goal !== "new" ? goal : null;
  const { data: assets = [] } = useAssets();
  const [form, setForm] = useState({
    name: current?.name ?? "",
    target_amount: current ? String(current.target_amount) : "",
    target_date: current?.target_date ?? "",
    asset_id: current?.asset_id ? String(current.asset_id) : "",
    manual_amount: current && !current.asset_id ? String(current.current) : "",
  });
  const create = useApiMutation("POST", "/api/goals");
  const update = useApiMutation("PATCH", `/api/goals/${current?.id}`);
  const remove = useApiMutation("DELETE", `/api/goals/${current?.id}`);
  const mutation = current ? update : create;
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await mutation.mutateAsync({
      name: form.name,
      target_amount: Number(form.target_amount),
      target_date: form.target_date || null,
      asset_id: form.asset_id ? Number(form.asset_id) : null,
      manual_amount: form.asset_id ? 0 : Number(form.manual_amount || 0),
    });
    onClose();
  };

  return (
    <Modal
      open={goal !== null}
      title={current ? "Editar meta" : "Nueva meta de ahorro"}
      onClose={onClose}
    >
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <Field label="Nombre" className="sm:col-span-2">
          <input
            className="input"
            required
            value={form.name}
            onChange={set("name")}
            placeholder="Ej. Fondo de emergencia"
          />
        </Field>
        <Field label="Meta (MXN)">
          <input
            className="input"
            type="number"
            min="1"
            step="100"
            required
            value={form.target_amount}
            onChange={set("target_amount")}
          />
        </Field>
        <Field label="Fecha objetivo" hint="Opcional">
          <input
            className="input"
            type="date"
            min={todayIso()}
            value={form.target_date}
            onChange={set("target_date")}
          />
        </Field>
        <Field
          label="Ligar a un activo"
          hint="Su valor actual será tu avance"
          className="sm:col-span-2"
        >
          <select className="input" value={form.asset_id} onChange={set("asset_id")}>
            <option value="">No, capturo el avance a mano</option>
            {assets
              .filter((a) => !a.is_liability && !a.archived)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
          </select>
        </Field>
        {!form.asset_id && (
          <Field label="Llevas ahorrado (MXN)">
            <input
              className="input"
              type="number"
              min="0"
              step="100"
              value={form.manual_amount}
              onChange={set("manual_amount")}
            />
          </Field>
        )}
        <div className="sm:col-span-2">
          <ErrorText error={mutation.error ?? remove.error} />
        </div>
        <div className="flex justify-between gap-2 sm:col-span-2">
          {current ? (
            <button
              type="button"
              className="btn btn-danger"
              onClick={async () => {
                if (!confirm(`¿Eliminar la meta «${current.name}»?`)) return;
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
