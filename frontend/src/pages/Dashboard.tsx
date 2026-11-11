import { AlertTriangle, ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { AlertsBanner } from "../components/AlertsBanner";
import { GoalsCard } from "../components/Goals";

import {
  useBudgetReport,
  useDistribution,
  useNetWorthHistory,
  usePositions,
  useSummary,
  useUpcoming,
} from "../api/hooks";
import type { Summary } from "../api/types";
import { ChartFrame, DataTable, Donut, Legend, TimeLineChart } from "../components/charts/Charts";
import { foldOther, SERIES } from "../components/charts/palette";
import { Card, EmptyState, PageHeader, ProgressBar, StatTile, StatusBadge } from "../components/ui";
import { money, number, pct, shortDate } from "../lib/format";
import { ASSET_TYPES, SPENDING_CATEGORIES, label } from "../lib/labels";
import { thisMonth } from "../lib/month";

const NW_SERIES = [
  { key: "net_worth", label: "Patrimonio neto", color: SERIES[0] },
  { key: "assets", label: "Activos", color: SERIES[2] },
  { key: "liabilities", label: "Pasivos", color: SERIES[1] },
];

const TYPE_ORDER = Object.keys(ASSET_TYPES);

export function MissingRatesBanner({ currencies }: { currencies: string[] }) {
  if (!currencies.length) return null;
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-line bg-surface p-3 text-sm">
      <AlertTriangle size={18} color="var(--serious)" className="shrink-0" aria-hidden />
      <p>
        Falta el tipo de cambio de <strong>{currencies.join(", ")}</strong>; esos montos cuentan
        como cero. Agrégalo en{" "}
        <Link to="/ajustes" className="underline">
          Ajustes
        </Link>
        .
      </p>
    </div>
  );
}

/** "▲ $12,300 (1.5 %) este mes": la flecha y el signo acompañan al color. */
function changeHint(s: Summary | undefined): string | undefined {
  if (!s) return undefined;
  if (s.net_worth_change == null) {
    return `${money(s.assets, "MXN", true)} activos · ${money(s.liabilities, "MXN", true)} deudas`;
  }
  const up = s.net_worth_change >= 0;
  const pctText =
    s.net_worth_change_pct != null ? ` (${pct(Math.abs(s.net_worth_change_pct))})` : "";
  return `${up ? "▲" : "▼"} ${money(Math.abs(s.net_worth_change), "MXN", true)}${pctText} en el mes`;
}

export function DashboardPage() {
  const { data: s } = useSummary();
  const { data: history = [] } = useNetWorthHistory(24);
  const { data: upcoming = [] } = useUpcoming(30);
  const { data: dist } = useDistribution();

  const pendingSoon = upcoming.filter((u) => u.status !== "paid");
  const monthYear = (iso: string) =>
    new Date(iso + "T00:00").toLocaleDateString("es-MX", { month: "short", year: "2-digit" });
  const composition = dist ? foldOther(dist.by_type) : [];

  return (
    <>
      <PageHeader
        title="Resumen"
        subtitle={s ? `Valores en ${s.base_currency} al ${shortDate(s.as_of)}` : undefined}
      />
      {s && <MissingRatesBanner currencies={s.missing_rates} />}
      <AlertsBanner />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Patrimonio neto" value={money(s?.net_worth)} hint={changeHint(s)} />
        <StatTile
          label="Ingreso mensual"
          value={money(s?.monthly_income)}
          hint={s ? `Este mes: ${money(s.income_this_month)}` : undefined}
        />
        <StatTile
          label="Gastos / mes"
          value={money(s ? s.monthly_fixed_expenses + s.monthly_variable_spending : undefined)}
          hint={
            s
              ? `${money(s.monthly_fixed_expenses, "MXN", true)} fijos + ${money(s.monthly_variable_spending, "MXN", true)} var.${s.variable_spending_days && s.variable_spending_days < 60 ? ` (${s.variable_spending_days} días)` : ""}`
              : undefined
          }
        />
        <StatTile
          label="Flujo libre / mes"
          value={money(s?.free_cash_flow)}
          tone={s && s.free_cash_flow < 0 ? "critical" : "neutral"}
          hint={s ? `Tasa de ahorro ${pct(s.savings_rate_pct)}` : undefined}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card
          title="Evolución del patrimonio"
          subtitle="Últimos 24 meses"
          className="lg:col-span-2"
        >
          {history.length ? (
            <>
              <ChartFrame
                height={280}
                chart={
                  <TimeLineChart
                    data={history}
                    xKey="date"
                    series={NW_SERIES}
                    xFormat={monthYear}
                  />
                }
                table={
                  <DataTable
                    columns={[
                      { key: "date", label: "Fecha" },
                      { key: "assets", label: "Activos", money: true },
                      { key: "liabilities", label: "Pasivos", money: true },
                      { key: "net_worth", label: "Neto", money: true },
                    ]}
                    rows={history}
                  />
                }
              />
              <Legend series={NW_SERIES} />
            </>
          ) : (
            <EmptyState title="Aún no hay valuaciones">
              Agrega tus cuentas y bienes en{" "}
              <Link className="underline" to="/patrimonio">
                Patrimonio
              </Link>
              .
            </EmptyState>
          )}
        </Card>

        <Card title="Composición" subtitle="En qué está tu patrimonio (sin deudas)">
          {composition.length ? (
            <Donut data={composition} labels={ASSET_TYPES} keyOrder={TYPE_ORDER} />
          ) : (
            <EmptyState title="Sin activos" />
          )}
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <MonthFlowCard summary={s} />
        <InvestmentsCard />
        <VariableSpendingCard />
      </div>

      <div className="mt-4">
        <GoalsCard compact />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card
          title="Próximos pagos"
          subtitle={`${pendingSoon.length} por pagar en los próximos 30 días`}
          actions={<CardLink to="/gastos?tab=fijos">Ver todos</CardLink>}
        >
          {pendingSoon.length ? (
            <ul className="divide-y divide-line">
              {pendingSoon.slice(0, 6).map((u) => (
                <li
                  key={`${u.expense_id}-${u.due_date}`}
                  className="flex items-center gap-3 py-2 text-sm"
                >
                  <span className="tabular w-20 shrink-0 text-ink-3">{shortDate(u.due_date)}</span>
                  <span className="min-w-0 flex-1 truncate">{u.name}</span>
                  <StatusBadge status={u.status} />
                  <span className="tabular w-24 text-right font-medium">
                    {money(u.amount, u.currency)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="Todo pagado por ahora" />
          )}
        </Card>

        <Card title="Indicadores clave" actions={<CardLink to="/analisis">Análisis</CardLink>}>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Indicator
              label="Cobertura pasiva"
              value={pct(s?.passive_coverage_pct, 0)}
              hint="De tus gastos fijos"
            />
            <Indicator
              label="Colchón de liquidez"
              value={s?.runway_months != null ? `${number(s.runway_months)} meses` : "—"}
              hint="De gastos fijos"
            />
            <Indicator label="Deuda / activos" value={pct(s?.debt_to_assets_pct)} />
            <Indicator
              label="Concentración"
              value={pct(s?.income_concentration_pct, 0)}
              hint="Peso de tu ingreso principal"
            />
          </dl>
        </Card>
      </div>
    </>
  );
}

function CardLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="btn btn-sm">
      {children} <ArrowRight size={14} aria-hidden />
    </Link>
  );
}

function FlowRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-2">{label}</dt>
      <dd className="tabular">{value}</dd>
    </div>
  );
}

function MonthFlowCard({ summary: s }: { summary: Summary | undefined }) {
  const flow = s?.month_flow;
  return (
    <Card
      title="Este mes"
      subtitle="Lo que entró y lo que ya salió"
      actions={<CardLink to="/gastos">Gastos</CardLink>}
    >
      {flow ? (
        <>
          <p
            className={`tabular text-2xl font-semibold ${flow.available < 0 ? "text-critical" : ""}`}
          >
            {money(flow.available)}
          </p>
          <p className="mb-3 text-xs text-ink-3">
            {flow.income === 0
              ? "Aún no registras ingresos este mes"
              : flow.available < 0
                ? "Gastaste más de lo que entró este mes"
                : "Te quedan del ingreso del mes"}
          </p>
          {flow.income > 0 && (
            <div className="mb-3">
              <ProgressBar value={flow.spent} max={flow.income} label="Gastado del ingreso" />
              <p className="mt-1 text-xs text-ink-2">
                {pct((flow.spent / flow.income) * 100, 0)} del ingreso ya se gastó
              </p>
            </div>
          )}
          <dl className="space-y-1.5 text-sm">
            <FlowRow label="Ingresos" value={money(flow.income)} />
            <FlowRow label="Fijos pagados" value={`− ${money(flow.fixed_paid)}`} />
            <FlowRow label="Gastos variables" value={`− ${money(flow.variable)}`} />
            {flow.fixed_pending > 0 && (
              <FlowRow label="Fijos por pagar" value={money(flow.fixed_pending)} />
            )}
          </dl>
        </>
      ) : (
        <EmptyState title="Cargando…" />
      )}
    </Card>
  );
}

function InvestmentsCard() {
  const { data: report } = usePositions();
  const gain = report?.unrealized_base ?? 0;
  return (
    <Card
      title="Inversiones"
      subtitle="Acciones, ETFs y cripto"
      actions={<CardLink to="/inversiones">Ver</CardLink>}
    >
      {report?.positions.length ? (
        <>
          <p className="tabular text-2xl font-semibold">{money(report.value_base)}</p>
          <p className="mb-3 text-xs text-ink-3">Valor de mercado en MXN</p>
          <dl className="space-y-1.5 text-sm">
            <FlowRow label="Invertido" value={money(report.cost_base)} />
            <FlowRow
              label="Ganancia"
              value={
                <span className={`font-medium ${gain < 0 ? "text-critical" : "text-good"}`}>
                  {gain >= 0 ? "▲ +" : "▼ −"}
                  {money(Math.abs(gain))}
                  {report.unrealized_pct != null && ` (${pct(Math.abs(report.unrealized_pct))})`}
                </span>
              }
            />
            <FlowRow label="Posiciones" value={String(report.positions.length)} />
          </dl>
        </>
      ) : (
        <EmptyState title="Sin inversiones">
          Registra tus acciones o cripto en{" "}
          <Link className="underline" to="/inversiones">
            Inversiones
          </Link>
          .
        </EmptyState>
      )}
    </Card>
  );
}

function VariableSpendingCard() {
  const { data: report } = useBudgetReport(thisMonth());
  const top = (report?.categories ?? []).filter((c) => c.spent > 0).slice(0, 3);
  return (
    <Card
      title="Gasto variable"
      subtitle="Súper, restaurantes, transporte…"
      actions={<CardLink to="/gastos?tab=variables">Presupuesto</CardLink>}
    >
      {report ? (
        <>
          <p className="tabular text-2xl font-semibold">{money(report.spent)}</p>
          {report.limit ? (
            <div className="mt-2 mb-3">
              <ProgressBar value={report.spent} max={report.limit} label="Presupuesto usado" />
              <p className="mt-1 text-xs text-ink-2">
                de {money(report.limit)} · día {report.days_elapsed} de {report.days_in_month}
              </p>
            </div>
          ) : (
            <p className="mb-3 text-xs text-ink-3">Sin presupuesto definido para este mes</p>
          )}
          {top.length > 0 && (
            <dl className="space-y-1.5 text-sm">
              {top.map((c) => (
                <FlowRow
                  key={c.category}
                  label={label(SPENDING_CATEGORIES, c.category)}
                  value={money(c.spent)}
                />
              ))}
            </dl>
          )}
        </>
      ) : (
        <EmptyState title="Cargando…" />
      )}
    </Card>
  );
}

function Indicator({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="tabular text-lg font-semibold">{value}</dd>
      {hint && <p className="text-xs text-ink-3">{hint}</p>}
    </div>
  );
}
