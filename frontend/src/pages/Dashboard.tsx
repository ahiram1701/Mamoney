import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

import { useNetWorthHistory, useSummary, useUpcoming } from "../api/hooks";
import { ChartFrame, DataTable, Legend, TimeLineChart } from "../components/charts/Charts";
import { SERIES } from "../components/charts/palette";
import { Card, EmptyState, PageHeader, StatTile, StatusBadge } from "../components/ui";
import { money, number, pct, shortDate } from "../lib/format";

const NW_SERIES = [
  { key: "net_worth", label: "Patrimonio neto", color: SERIES[0] },
  { key: "assets", label: "Activos", color: SERIES[2] },
  { key: "liabilities", label: "Pasivos", color: SERIES[1] },
];

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

export function DashboardPage() {
  const { data: s } = useSummary();
  const { data: history = [] } = useNetWorthHistory(24);
  const { data: upcoming = [] } = useUpcoming(30);

  const pendingSoon = upcoming.filter((u) => u.status !== "paid");
  const monthYear = (iso: string) =>
    new Date(iso + "T00:00").toLocaleDateString("es-MX", { month: "short", year: "2-digit" });

  return (
    <>
      <PageHeader
        title="Resumen"
        subtitle={s ? `Valores en ${s.base_currency} al ${shortDate(s.as_of)}` : undefined}
      />
      {s && <MissingRatesBanner currencies={s.missing_rates} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Patrimonio neto"
          value={money(s?.net_worth)}
          hint={
            s
              ? `${money(s.assets, "MXN", true)} activos · ${money(s.liabilities, "MXN", true)} deudas`
              : undefined
          }
        />
        <StatTile
          label="Ingreso mensual"
          value={money(s?.monthly_income)}
          hint={s ? `Este mes: ${money(s.income_this_month)}` : undefined}
        />
        <StatTile
          label="Gastos fijos / mes"
          value={money(s?.monthly_fixed_expenses)}
          hint={s ? `${pendingSoon.length} pagos en los próximos 30 días` : undefined}
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

        <Card title="Indicadores clave">
          <dl className="space-y-3 text-sm">
            <Indicator
              label="Cobertura con ingreso pasivo"
              value={pct(s?.passive_coverage_pct, 0)}
              hint="Qué parte de tus gastos fijos pagan tus ingresos pasivos"
            />
            <Indicator
              label="Colchón de liquidez"
              value={s?.runway_months != null ? `${number(s.runway_months)} meses` : "—"}
              hint="Meses de gastos fijos que cubren tus activos líquidos"
            />
            <Indicator label="Deuda / activos" value={pct(s?.debt_to_assets_pct)} />
            <Indicator
              label="Concentración de ingresos"
              value={pct(s?.income_concentration_pct, 0)}
              hint="Peso de tu fuente de ingreso principal"
            />
          </dl>
        </Card>
      </div>

      <Card
        title="Próximos pagos"
        subtitle="Vencidos de la última semana y los de los próximos 30 días"
        className="mt-4"
        actions={
          <Link to="/gastos" className="btn btn-sm">
            Ver todos
          </Link>
        }
      >
        {upcoming.length ? (
          <ul className="divide-y divide-line">
            {upcoming.slice(0, 8).map((u) => (
              <li
                key={`${u.expense_id}-${u.due_date}`}
                className="flex items-center gap-3 py-2 text-sm"
              >
                <span className="tabular w-24 shrink-0 text-ink-3">{shortDate(u.due_date)}</span>
                <span className="flex-1 truncate">{u.name}</span>
                <StatusBadge status={u.status} />
                <span className="tabular w-28 text-right font-medium">
                  {money(u.amount, u.currency)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="Sin pagos próximos" />
        )}
      </Card>
    </>
  );
}

function Indicator({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line pb-3 last:border-0 last:pb-0">
      <div>
        <dt className="font-medium">{label}</dt>
        {hint && <p className="text-xs text-ink-3">{hint}</p>}
      </div>
      <dd className="tabular whitespace-nowrap text-lg font-semibold">{value}</dd>
    </div>
  );
}
