import { AlertTriangle, Bell, CalendarClock, PiggyBank, Target } from "lucide-react";
import { Link } from "react-router-dom";

import { useAlerts } from "../api/hooks";
import type { AlertItem } from "../api/types";

const ICON: Record<AlertItem["kind"], typeof Bell> = {
  payment: CalendarClock,
  budget: PiggyBank,
  goal: Target,
};

/** Pagos por vencer, presupuesto excedido y metas atrasadas, con icono + texto. */
export function AlertsBanner() {
  const { data: alerts = [] } = useAlerts();
  if (alerts.length === 0) return null;
  const critical = alerts.filter((a) => a.severity === "critical").length;
  return (
    <section aria-label="Alertas" className="mb-4 rounded-xl border border-line bg-surface p-4">
      <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <AlertTriangle
          size={16}
          color={critical ? "var(--critical)" : "var(--serious)"}
          aria-hidden
        />
        {alerts.length === 1 ? "1 alerta" : `${alerts.length} alertas`}
        {critical > 0 && (
          <span className="text-xs font-normal text-ink-3">({critical} urgentes)</span>
        )}
      </h2>
      <ul className="divide-y divide-line">
        {alerts.slice(0, 6).map((a) => {
          const Icon = ICON[a.kind];
          return (
            <li key={a.key}>
              <Link to={a.link} className="flex items-center gap-3 py-2 text-sm hover:underline">
                <Icon
                  size={16}
                  className="shrink-0"
                  color={a.severity === "critical" ? "var(--critical)" : "var(--serious)"}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{a.title}</span>
                  <span className="block truncate text-xs text-ink-3">{a.detail}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      {alerts.length > 6 && <p className="mt-1 text-xs text-ink-3">y {alerts.length - 6} más</p>}
    </section>
  );
}
