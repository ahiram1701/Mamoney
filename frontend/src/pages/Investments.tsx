import { useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Search, Trash2, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useApiMutation, useAssets, usePositions, useTrades } from "../api/hooks";
import type { Asset, SecuritySearchResult } from "../api/types";
import { Donut } from "../components/charts/Charts";
import { foldOther } from "../components/charts/palette";
import {
  Card,
  EmptyState,
  ErrorText,
  Field,
  Modal,
  PageHeader,
  Segmented,
  StatTile,
} from "../components/ui";
import { money, number, pct, shortDate, todayIso } from "../lib/format";
import { MissingRatesBanner } from "./Dashboard";

const KIND_LABEL: Record<string, string> = {
  stock: "Acción",
  etf: "ETF",
  crypto: "Cripto",
  fund: "Fondo",
  other: "Otro",
};

/** Ganancia con flecha y signo: el color nunca va solo. */
function Gain({
  value,
  pctValue,
  currency,
}: {
  value: number | null;
  pctValue?: number | null;
  currency?: string;
}) {
  if (value === null) return <span className="text-ink-3">—</span>;
  const up = value >= 0;
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span className={`inline-flex items-center gap-1 ${up ? "text-good" : "text-critical"}`}>
      <Icon size={14} aria-hidden />
      {up ? "+" : "−"}
      {money(Math.abs(value), currency)}
      {pctValue != null && <span className="text-xs">({pct(Math.abs(pctValue))})</span>}
    </span>
  );
}

export function InvestmentsPage() {
  const qc = useQueryClient();
  const { data: assets = [] } = useAssets();
  const { data: report } = usePositions();
  const { data: trades = [] } = useTrades();
  const [tradeOpen, setTradeOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<unknown>(null);
  const removeTrade = useApiMutation<{ id: number }>(
    "DELETE",
    (b) => `/api/portfolio/trades/${b.id}`,
  );

  const accounts = assets.filter((a) => a.tracks_positions && !a.archived);
  const positions = useMemo(() => report?.positions ?? [], [report]);
  const lastPriceAt = positions
    .map((p) => p.price_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  const refresh = async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      await api("/api/portfolio/refresh", { method: "POST" });
      await qc.invalidateQueries();
    } catch (err) {
      setRefreshError(err);
    } finally {
      setRefreshing(false);
    }
  };

  const allocation = useMemo(
    () => foldOther(positions.map((p) => ({ key: p.symbol, value: p.value_base }))),
    [positions],
  );

  if (accounts.length === 0) {
    return (
      <>
        <PageHeader
          title="Inversiones"
          subtitle="Acciones, ETFs y cripto con precios de mercado."
        />
        <EmptyState title="Aún no tienes cuentas de inversión con posiciones">
          <p>
            Crea una cuenta (por ejemplo tu broker o tu exchange de cripto) y registra tus compras y
            ventas. Mamoney trae los precios solo y calcula valor, costo y ganancias.
          </p>
          <button className="btn btn-primary mt-4" onClick={() => setAccountOpen(true)}>
            <Plus size={16} /> Crear cuenta de inversión
          </button>
        </EmptyState>
        <AccountForm open={accountOpen} onClose={() => setAccountOpen(false)} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Inversiones"
        subtitle={
          lastPriceAt
            ? `Precios de mercado actualizados ${new Date(lastPriceAt).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })}`
            : "Acciones, ETFs y cripto con precios de mercado."
        }
        actions={
          <>
            <button className="btn" onClick={refresh} disabled={refreshing}>
              <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} /> Actualizar
              precios
            </button>
            <button className="btn btn-primary" onClick={() => setTradeOpen(true)}>
              <Plus size={16} /> Registrar operación
            </button>
          </>
        }
      />
      {report && <MissingRatesBanner currencies={report.missing_rates} />}
      <ErrorText error={refreshError} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Valor de mercado" value={money(report?.value_base)} />
        <StatTile label="Invertido (costo)" value={money(report?.cost_base)} />
        <StatTile
          label="Ganancia no realizada"
          value={
            report
              ? `${report.unrealized_base >= 0 ? "+" : "−"}${money(Math.abs(report.unrealized_base))}`
              : "—"
          }
          tone={report && report.unrealized_base < 0 ? "critical" : "good"}
          hint={
            report?.unrealized_pct != null
              ? `${pct(report.unrealized_pct)} sobre el costo`
              : undefined
          }
        />
        <StatTile
          label="Ganancia realizada"
          value={money(report?.realized_base)}
          hint="Por ventas, después de comisiones"
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
        <Card
          title="Posiciones"
          subtitle="Precio y valor en la moneda del instrumento; peso sobre el total en MXN"
        >
          {positions.length === 0 ? (
            <EmptyState title="Sin posiciones abiertas">Registra tu primera compra.</EmptyState>
          ) : (
            <>
              {/* Teléfono: tarjetas con valor y ganancia a la vista. */}
              <ul className="divide-y divide-line md:hidden">
                {positions.map((p) => (
                  <li key={`${p.account_id}-${p.security_id}`} className="py-3 text-sm">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="font-semibold">{p.symbol}</p>
                      <p className="tabular font-semibold">{money(p.value, p.currency)}</p>
                    </div>
                    <div className="mt-0.5 flex items-baseline justify-between gap-3 text-xs">
                      <p className="min-w-0 truncate text-ink-3">
                        {number(p.quantity, 8)} × {money(p.price, p.currency)}
                      </p>
                      <span className="tabular shrink-0">
                        <Gain value={p.gain} pctValue={p.gain_pct} currency={p.currency} />
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-3">
                      Costo prom. {money(p.avg_cost, p.currency)} · {pct(p.weight_pct)} del total
                    </p>
                  </li>
                ))}
              </ul>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[760px] text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs text-ink-3">
                      <th className="py-2 font-medium">Instrumento</th>
                      <th className="py-2 text-right font-medium">Títulos</th>
                      <th className="py-2 text-right font-medium">Costo prom.</th>
                      <th className="py-2 text-right font-medium">Precio</th>
                      <th className="py-2 text-right font-medium">Valor</th>
                      <th className="py-2 text-right font-medium">Ganancia</th>
                      <th className="py-2 text-right font-medium">Peso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => (
                      <tr key={`${p.account_id}-${p.security_id}`} className="border-b border-line">
                        <td className="py-2">
                          <p className="font-semibold">{p.symbol}</p>
                          <p className="max-w-[220px] truncate text-xs text-ink-3">
                            {KIND_LABEL[p.kind]} · {p.name ?? ""}{" "}
                            {accounts.length > 1 ? `· ${p.account}` : ""}
                          </p>
                        </td>
                        <td className="tabular py-2 text-right">{number(p.quantity, 8)}</td>
                        <td className="tabular py-2 text-right">{money(p.avg_cost, p.currency)}</td>
                        <td className="tabular py-2 text-right">{money(p.price, p.currency)}</td>
                        <td className="tabular py-2 text-right font-medium">
                          {money(p.value, p.currency)}
                        </td>
                        <td className="tabular py-2 text-right">
                          <Gain value={p.gain} pctValue={p.gain_pct} currency={p.currency} />
                        </td>
                        <td className="tabular py-2 text-right text-ink-2">{pct(p.weight_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>

        <Card title="Distribución" subtitle="Por instrumento, en MXN">
          {allocation.length ? <Donut data={allocation} /> : <EmptyState title="Sin datos" />}
        </Card>
      </div>

      <Card
        className="mt-4"
        title="Operaciones"
        actions={
          <button className="btn btn-sm" onClick={() => setAccountOpen(true)}>
            <Plus size={14} /> Nueva cuenta
          </button>
        }
      >
        {trades.length === 0 ? (
          <EmptyState title="Sin operaciones" />
        ) : (
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-3">
                  <th className="py-2 font-medium">Fecha</th>
                  <th className="py-2 font-medium">Operación</th>
                  <th className="py-2 text-right font-medium">Títulos</th>
                  <th className="py-2 text-right font-medium">Precio</th>
                  <th className="py-2 text-right font-medium">Total</th>
                  <th className="py-2 font-medium">Cuenta</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-line">
                    <td className="tabular py-2 text-ink-3">{shortDate(t.date)}</td>
                    <td className="py-2">
                      <span className={t.side === "buy" ? "text-good" : "text-critical"}>
                        {t.side === "buy" ? "Compra" : "Venta"}
                      </span>{" "}
                      <strong>{t.symbol}</strong>
                    </td>
                    <td className="tabular py-2 text-right">{number(t.quantity, 8)}</td>
                    <td className="tabular py-2 text-right">{money(t.price, t.currency)}</td>
                    <td className="tabular py-2 text-right font-medium">
                      {money(t.total, t.currency)}
                    </td>
                    <td className="py-2 text-ink-2">{t.account}</td>
                    <td className="py-2 text-right">
                      <button
                        className="btn btn-sm btn-danger"
                        aria-label="Eliminar operación"
                        onClick={() =>
                          confirm("¿Eliminar esta operación?") && removeTrade.mutate({ id: t.id })
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <ErrorText error={removeTrade.error} />
        <p className="mt-3 text-xs text-ink-3">
          Los dividendos se registran en{" "}
          <Link className="underline" to="/ingresos">
            Ingresos
          </Link>{" "}
          como fuente pasiva ligada a la cuenta. El efectivo de las ventas no se suma solo:
          regístralo en tu cuenta bancaria o de efectivo.
        </p>
      </Card>

      <TradeForm open={tradeOpen} accounts={accounts} onClose={() => setTradeOpen(false)} />
      <AccountForm open={accountOpen} onClose={() => setAccountOpen(false)} />
    </>
  );
}

function SymbolSearch({ onPick }: { onPick: (r: SecuritySearchResult) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SecuritySearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (query.trim().length < 2) return;
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        setResults(
          await api<SecuritySearchResult[]>(`/api/portfolio/search?q=${encodeURIComponent(query)}`),
        );
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [query]);
  // Con menos de 2 letras no se muestran resultados (sin tener que vaciar el estado).
  const visible = query.trim().length >= 2 ? results : [];

  return (
    <div className="relative">
      <div className="relative">
        <Search
          size={16}
          className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3"
        />
        <input
          className="input pl-9"
          placeholder="Busca por nombre o símbolo: Apple, VOO, Bitcoin…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>
      {(visible.length > 0 || loading) && (
        <ul className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-line bg-surface shadow-lg">
          {loading && <li className="px-3 py-2 text-sm text-ink-3">Buscando…</li>}
          {visible.map((r) => (
            <li key={r.symbol}>
              <button
                type="button"
                className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-surface-2"
                onClick={() => {
                  onPick(r);
                  setQuery("");
                  setResults([]);
                }}
              >
                <span className="w-20 shrink-0 font-semibold">{r.symbol}</span>
                <span className="min-w-0 flex-1 truncate text-ink-2">{r.name}</span>
                <span className="text-xs text-ink-3">{KIND_LABEL[r.kind]}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TradeForm({
  open,
  accounts,
  onClose,
}: {
  open: boolean;
  accounts: Asset[];
  onClose: () => void;
}) {
  const [picked, setPicked] = useState<SecuritySearchResult | null>(null);
  const [form, setForm] = useState({
    asset_id: "",
    side: "buy" as "buy" | "sell",
    date: todayIso(),
    quantity: "",
    price: "",
    fee: "",
  });
  const [currency, setCurrency] = useState("USD");
  const add = useApiMutation("POST", "/api/portfolio/trades");
  const accountId = form.asset_id || String(accounts[0]?.id ?? "");
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const pick = async (r: SecuritySearchResult) => {
    setPicked(r);
    try {
      const q = await api<{ price: number; currency: string }>(
        `/api/portfolio/quote?symbol=${encodeURIComponent(r.symbol)}`,
      );
      setCurrency(q.currency);
      setForm((f) => ({ ...f, price: f.price || String(q.price) }));
    } catch {
      /* el precio se captura a mano */
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    await add.mutateAsync({
      asset_id: Number(accountId),
      symbol: picked.symbol,
      kind: picked.kind,
      side: form.side,
      date: form.date,
      quantity: Number(form.quantity),
      price: Number(form.price),
      fee: Number(form.fee || 0),
    });
    setPicked(null);
    setForm((f) => ({ ...f, quantity: "", price: "", fee: "" }));
    onClose();
  };

  const total = Number(form.quantity || 0) * Number(form.price || 0);

  return (
    <Modal open={open} title="Registrar operación" onClose={onClose}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          {picked ? (
            <div className="flex items-center justify-between rounded-lg border border-line p-3 text-sm">
              <div>
                <p className="font-semibold">{picked.symbol}</p>
                <p className="text-xs text-ink-3">
                  {KIND_LABEL[picked.kind]} · {picked.name}
                </p>
              </div>
              <button type="button" className="btn btn-sm" onClick={() => setPicked(null)}>
                Cambiar
              </button>
            </div>
          ) : (
            <SymbolSearch onPick={pick} />
          )}
        </div>
        <Segmented
          label="Tipo de operación"
          value={form.side}
          onChange={(v) => setForm((f) => ({ ...f, side: v }))}
          options={[
            { value: "buy", label: "Compra" },
            { value: "sell", label: "Venta" },
          ]}
        />
        {accounts.length > 1 ? (
          <select
            className="input"
            value={accountId}
            onChange={set("asset_id")}
            aria-label="Cuenta"
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        ) : (
          <p className="self-center text-sm text-ink-2">Cuenta: {accounts[0]?.name}</p>
        )}
        <Field label="Títulos" hint="Admite fracciones (p. ej. 0.015 BTC)">
          <input
            className="input"
            type="number"
            step="any"
            min="0"
            required
            value={form.quantity}
            onChange={set("quantity")}
          />
        </Field>
        <Field label={`Precio por título (${currency})`}>
          <input
            className="input"
            type="number"
            step="any"
            min="0"
            required
            value={form.price}
            onChange={set("price")}
          />
        </Field>
        <Field label="Fecha">
          <input
            className="input"
            type="date"
            required
            max={todayIso()}
            value={form.date}
            onChange={set("date")}
          />
        </Field>
        <Field label={`Comisión (${currency})`}>
          <input
            className="input"
            type="number"
            step="any"
            min="0"
            value={form.fee}
            onChange={set("fee")}
          />
        </Field>
        <p className="text-sm text-ink-2 sm:col-span-2">
          Total: <strong className="tabular text-ink">{money(total, currency)}</strong>
        </p>
        <div className="sm:col-span-2">
          <ErrorText error={add.error} />
        </div>
        <div className="flex justify-end sm:col-span-2">
          <button className="btn btn-primary" disabled={!picked || add.isPending}>
            {add.isPending ? "Guardando…" : "Guardar operación"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function AccountForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState({ name: "", institution: "", type: "investment" });
  const create = useApiMutation("POST", "/api/assets");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await create.mutateAsync({
      name: form.name,
      institution: form.institution || null,
      type: form.type,
      currency: "USD",
      liquidity: "short",
      tracks_positions: true,
    });
    setForm({ name: "", institution: "", type: "investment" });
    onClose();
  };
  return (
    <Modal open={open} title="Nueva cuenta de inversión" onClose={onClose}>
      <form onSubmit={submit} className="grid gap-3">
        <Field label="Nombre">
          <input
            className="input"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Ej. GBM Internacional, Bitso"
          />
        </Field>
        <Field label="Tipo">
          <select
            className="input"
            value={form.type}
            onChange={(e) => setForm({ ...form, type: e.target.value })}
          >
            <option value="investment">Acciones y ETFs</option>
            <option value="crypto">Cripto</option>
          </select>
        </Field>
        <Field label="Institución" hint="Opcional">
          <input
            className="input"
            value={form.institution}
            onChange={(e) => setForm({ ...form, institution: e.target.value })}
          />
        </Field>
        <p className="text-xs text-ink-3">
          La cuenta se lleva en dólares; su valor en pesos usa el tipo de cambio del día.
        </p>
        <ErrorText error={create.error} />
        <div className="flex justify-end">
          <button className="btn btn-primary" disabled={create.isPending}>
            Crear cuenta
          </button>
        </div>
      </form>
    </Modal>
  );
}
