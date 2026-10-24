import { Table2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { money } from "../../lib/format";
import { colorMap, OTHER } from "./palette";

// Cualquier objeto plano de la API sirve como fila.
type Row = object;
const cell = (r: Row, k: string) => (r as Record<string, unknown>)[k];

export interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

function TooltipBox({
  title,
  items,
}: {
  title: string;
  items: { label: string; value: number; color: string }[];
}) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-ink">{title}</p>
      {items.map((item) => (
        <p key={item.label} className="flex items-center gap-2 text-ink-2">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: item.color }} />
          <span className="flex-1">{item.label}</span>
          <span className="tabular font-medium text-ink">{money(item.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function Legend({ series }: { series: SeriesDef[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-sm" style={{ background: s.color }} />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

/** Envuelve una gráfica con un botón para alternar a vista de tabla (accesibilidad). */
export function ChartFrame({
  chart,
  table,
  height = 260,
}: {
  chart: ReactNode;
  table: ReactNode;
  height?: number;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <div>
      <div className="-mt-2 mb-1 flex justify-end">
        <button
          className="btn btn-sm"
          onClick={() => setAsTable((v) => !v)}
          aria-pressed={asTable}
          title={asTable ? "Ver gráfica" : "Ver como tabla"}
        >
          <Table2 size={14} />
          <span className="sr-only">{asTable ? "Ver gráfica" : "Ver como tabla"}</span>
        </button>
      </div>
      {asTable ? (
        <div className="max-h-[320px] overflow-auto">{table}</div>
      ) : (
        <div style={{ height }}>{chart}</div>
      )}
    </div>
  );
}

export function DataTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string; money?: boolean }[];
  rows: Row[];
}) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-ink-3">
          {columns.map((c) => (
            <th key={c.key} className={c.money ? "py-1.5 text-right" : "py-1.5"}>
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-b border-line/60">
            {columns.map((c) => (
              <td key={c.key} className={c.money ? "tabular py-1.5 text-right" : "py-1.5"}>
                {c.money ? money(Number(cell(r, c.key) ?? 0)) : String(cell(r, c.key) ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const axisMoney = (v: number) => money(v, "MXN", true);

export function TimeLineChart({
  data,
  xKey,
  series,
  xFormat,
  area = false,
}: {
  data: Row[];
  xKey: string;
  series: SeriesDef[];
  xFormat: (v: string) => string;
  area?: boolean;
}) {
  const Chart = area ? AreaChart : LineChart;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <Chart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey={xKey}
          tickFormatter={xFormat}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis tickFormatter={axisMoney} tickLine={false} axisLine={false} width={72} />
        <Tooltip
          cursor={{ stroke: "var(--text-3)", strokeDasharray: "3 3" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox
                title={xFormat(String(label))}
                items={series.map((s) => ({
                  label: s.label,
                  color: s.color,
                  value: Number(payload.find((p) => p.dataKey === s.key)?.value ?? 0),
                }))}
              />
            ) : null
          }
        />
        {series.map((s, i) =>
          area && i === 0 ? (
            <Area
              key={s.key}
              type="monotone"
              isAnimationActive={false}
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={2}
              fill={s.color}
              fillOpacity={0.12}
              activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }}
              dot={false}
            />
          ) : (
            <Line
              key={s.key}
              type="monotone"
              isAnimationActive={false}
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }}
            />
          ),
        )}
      </Chart>
    </ResponsiveContainer>
  );
}

export function StackedBars({
  data,
  xKey,
  series,
  xFormat,
}: {
  data: Row[];
  xKey: string;
  series: SeriesDef[];
  xFormat: (v: string) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }} barCategoryGap="28%">
        <CartesianGrid vertical={false} />
        <XAxis dataKey={xKey} tickFormatter={xFormat} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={axisMoney} tickLine={false} axisLine={false} width={72} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox
                title={xFormat(String(label))}
                items={payload
                  .filter((p) => Number(p.value) > 0)
                  .map((p) => ({
                    label: series.find((s) => s.key === p.dataKey)?.label ?? String(p.dataKey),
                    color: String(p.color),
                    value: Number(p.value),
                  }))}
              />
            ) : null
          }
        />
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            stackId="a"
            isAnimationActive={false}
            fill={s.color}
            stroke="var(--surface)"
            strokeWidth={2}
            radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({
  data,
  labels,
  keyOrder,
}: {
  data: { key: string; value: number }[];
  labels?: Record<string, string>;
  keyOrder?: string[];
}) {
  const colors = colorMap(keyOrder ?? data.map((d) => d.key));
  const total = data.reduce((s, d) => s + d.value, 0);
  const name = (k: string) => labels?.[k] ?? k;
  return (
    <div className="space-y-4">
      <div className="mx-auto h-[180px] max-w-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="key"
              innerRadius="62%"
              outerRadius="100%"
              stroke="var(--surface)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {data.map((d) => (
                <Cell key={d.key} fill={colors.get(d.key) ?? OTHER} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={name(String(payload[0].name))}
                    items={[
                      {
                        label: `${((Number(payload[0].value) / total) * 100).toFixed(1)} %`,
                        value: Number(payload[0].value),
                        color: colors.get(String(payload[0].name)) ?? OTHER,
                      },
                    ]}
                  />
                ) : null
              }
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-1.5 text-sm">
        {data.map((d) => (
          <li key={d.key} className="flex items-center gap-2">
            <span
              className="inline-block size-2.5 shrink-0 rounded-sm"
              style={{ background: colors.get(d.key) ?? OTHER }}
            />
            <span className="flex-1 truncate text-ink-2">{name(d.key)}</span>
            <span className="tabular text-ink-3">
              {total ? ((d.value / total) * 100).toFixed(0) : 0} %
            </span>
            <span className="tabular w-24 text-right font-medium">
              {money(d.value, "MXN", true)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function HBars({
  data,
  labels,
}: {
  data: { key: string; value: number }[];
  labels?: Record<string, string>;
}) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <ul className="space-y-2.5">
      {data.map((d) => (
        <li
          key={d.key}
          className="text-sm"
          title={`${labels?.[d.key] ?? d.key}: ${money(d.value)}`}
        >
          <div className="mb-1 flex justify-between">
            <span className="text-ink-2">{labels?.[d.key] ?? d.key}</span>
            <span className="tabular font-medium">{money(d.value)}</span>
          </div>
          <div className="h-2 rounded-full bg-surface-2">
            <div
              className="h-2 rounded-full"
              style={{ width: `${(d.value / max) * 100}%`, background: "var(--series-1)" }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
