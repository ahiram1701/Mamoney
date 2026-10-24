import { useState } from "react";

import { usePerformance, useProjection, useSummary } from "../api/hooks";
import { ChartFrame, DataTable, Legend, TimeLineChart } from "../components/charts/Charts";
import { SERIES } from "../components/charts/palette";
import { Card, EmptyState, Field, PageHeader, StatTile } from "../components/ui";
import { money, number, pct, shortDate } from "../lib/format";
import { MissingRatesBanner } from "./Dashboard";

const PROJ_SERIES = [
  { key: "value", label: "Patrimonio proyectado", color: SERIES[0] },
  { key: "contributed", label: "Solo aportaciones", color: SERIES[1] },
];

function Meter({ value, label }: { value: number | null; label: string }) {
  const clamped = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-ink-2">{label}</span>
        <span className="tabular font-semibold">{pct(value, 0)}</span>
      </div>
      <div
        className="h-2.5 rounded-full bg-surface-2"
        role="meter"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className="h-2.5 rounded-full"
          style={{ width: `${clamped}%`, background: "var(--series-1)" }}
        />
      </div>
    </div>
  );
}

export function AnalysisPage() {
  const { data: s } = useSummary();
  const { data: perf = [] } = usePerformance();
  const [years, setYears] = useState(10);
  const [rate, setRate] = useState<string>("");
  const [savings, setSavings] = useState<string>("");
  const { data: proj } = useProjection(
    years,
    rate === "" ? null : Number(rate),
    savings === "" ? null : Number(savings),
  );

  const yearLabel = (y: string) => `Año ${y}`;
  const finalPoint = proj?.points.at(-1);

  return (
    <>
      <PageHeader title="Análisis" subtitle="Qué tan sólida es tu situación y hacia dónde va." />
      {s && <MissingRatesBanner currencies={s.missing_rates} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Independencia financiera" subtitle="Ingreso pasivo contra gastos fijos">
          <Meter
            value={s?.passive_coverage_pct ?? null}
            label="Gastos fijos cubiertos por ingreso pasivo"
          />
          <p className="mt-3 text-sm text-ink-2">
            Ingreso pasivo de{" "}
            <strong className="tabular">{money(s?.passive_monthly_income)}</strong> al mes frente a{" "}
            <strong className="tabular">{money(s?.monthly_fixed_expenses)}</strong> de gastos fijos.
            {s && s.passive_monthly_income < s.monthly_fixed_expenses && (
              <>
                {" "}
                Te faltan{" "}
                <strong className="tabular">
                  {money(s.monthly_fixed_expenses - s.passive_monthly_income)}
                </strong>{" "}
                al mes de ingreso pasivo para cubrirlos.
              </>
            )}
          </p>
        </Card>

        <div className="grid grid-cols-2 gap-3">
          <StatTile
            label="Colchón de liquidez"
            value={s?.runway_months != null ? `${number(s.runway_months)} meses` : "—"}
            hint={`${money(s?.liquid_assets)} en activos líquidos`}
          />
          <StatTile
            label="Tasa de ahorro"
            value={pct(s?.savings_rate_pct)}
            hint="Flujo libre / ingreso"
          />
          <StatTile label="Deuda / activos" value={pct(s?.debt_to_assets_pct)} />
          <StatTile
            label="Concentración"
            value={pct(s?.income_concentration_pct, 0)}
            hint="Peso de tu principal fuente"
          />
        </div>
      </div>

      <Card
        className="mt-4"
        title="Proyección de patrimonio"
        subtitle="Interés compuesto mensual con aportación constante"
      >
        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          <Field label="Años">
            <input
              className="input"
              type="number"
              min={1}
              max={50}
              value={years}
              onChange={(e) => setYears(Number(e.target.value) || 1)}
            />
          </Field>
          <Field
            label="Rendimiento anual (%)"
            hint={proj ? `Actual: ${proj.annual_return_pct} %` : undefined}
          >
            <input
              className="input"
              type="number"
              step="0.1"
              placeholder={proj ? String(proj.annual_return_pct) : ""}
              value={rate}
              onChange={(e) => setRate(e.target.value)}
            />
          </Field>
          <Field label="Ahorro mensual" hint="Por defecto, tu flujo libre actual">
            <input
              className="input"
              type="number"
              step="100"
              placeholder={proj ? String(Math.round(proj.monthly_savings)) : ""}
              value={savings}
              onChange={(e) => setSavings(e.target.value)}
            />
          </Field>
        </div>
        {proj && (
          <>
            <p className="mb-4 text-sm text-ink-2">
              En {years} años podrías tener{" "}
              <strong className="tabular text-ink">{money(finalPoint?.value)}</strong>, de los
              cuales {money(finalPoint?.contributed)} son tu patrimonio actual más aportaciones.
            </p>
            <ChartFrame
              chart={
                <TimeLineChart
                  data={proj.points}
                  xKey="year"
                  series={PROJ_SERIES}
                  xFormat={yearLabel}
                />
              }
              table={
                <DataTable
                  columns={[
                    { key: "year", label: "Año" },
                    { key: "contributed", label: "Aportado", money: true },
                    { key: "value", label: "Proyectado", money: true },
                  ]}
                  rows={proj.points}
                />
              }
            />
            <Legend series={PROJ_SERIES} />
          </>
        )}
      </Card>

      <Card
        className="mt-4"
        title="Rendimiento por activo"
        subtitle="Cambio de valor más ingresos asociados, en MXN"
      >
        {perf.length === 0 ? (
          <EmptyState title="Sin datos suficientes">
            Registra al menos una valuación por activo.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-3">
                  <th className="py-2 font-medium">Activo</th>
                  <th className="py-2 font-medium">Desde</th>
                  <th className="py-2 text-right font-medium">Inicial</th>
                  <th className="py-2 text-right font-medium">Actual</th>
                  <th className="py-2 text-right font-medium">Ingresos</th>
                  <th className="py-2 text-right font-medium">Ganancia</th>
                  <th className="py-2 text-right font-medium">Total</th>
                  <th className="py-2 text-right font-medium">Anualizado</th>
                </tr>
              </thead>
              <tbody>
                {perf.map((p) => (
                  <tr key={p.id} className="border-b border-line">
                    <td className="py-2 font-medium">{p.name}</td>
                    <td className="tabular py-2 text-ink-3">{shortDate(p.since)}</td>
                    <td className="tabular py-2 text-right">{money(p.start_value_base)}</td>
                    <td className="tabular py-2 text-right">{money(p.current_value_base)}</td>
                    <td className="tabular py-2 text-right">{money(p.income_base)}</td>
                    <td
                      className={`tabular py-2 text-right font-medium ${p.gain_base < 0 ? "text-critical" : ""}`}
                    >
                      {money(p.gain_base)}
                    </td>
                    <td className="tabular py-2 text-right">{pct(p.total_return_pct)}</td>
                    <td className="tabular py-2 text-right">{pct(p.annualized_return_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
