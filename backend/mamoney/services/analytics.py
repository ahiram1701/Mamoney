"""Cálculos del dashboard. Todo se devuelve convertido a la moneda base."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlmodel import Session, select

from mamoney.models import (
    Asset,
    AssetValuation,
    ExpensePayment,
    FixedExpense,
    Goal,
    IncomeEntry,
    IncomeSource,
    Liquidity,
    Spending,
)
from mamoney.services.fx import FxTable, MissingRateError
from mamoney.services.scheduling import (
    add_months,
    clamp_day,
    last_n_months,
    monthly_amount,
    occurrences,
)

LIQUID = {Liquidity.immediate, Liquidity.short}

Row = dict[str, Any]


@dataclass
class Snapshot:
    """Datos cargados una sola vez por petición."""

    assets: list[Asset]
    valuations: dict[int, list[AssetValuation]]
    sources: list[IncomeSource]
    entries: list[IncomeEntry]
    expenses: list[FixedExpense]
    payments: list[ExpensePayment]
    fx: FxTable
    today: date
    missing_rates: set[str] = field(default_factory=set)
    spendings: list[Spending] = field(default_factory=list)

    @classmethod
    def load(cls, session: Session, today: date | None = None) -> "Snapshot":
        valuations: dict[int, list[AssetValuation]] = defaultdict(list)
        for v in session.exec(select(AssetValuation).order_by(AssetValuation.date)).all():  # type: ignore[arg-type]
            valuations[v.asset_id].append(v)
        return cls(
            assets=list(session.exec(select(Asset)).all()),
            valuations=valuations,
            sources=list(session.exec(select(IncomeSource)).all()),
            entries=list(session.exec(select(IncomeEntry)).all()),
            expenses=list(session.exec(select(FixedExpense)).all()),
            payments=list(session.exec(select(ExpensePayment)).all()),
            fx=FxTable.load(session),
            today=today or date.today(),
            spendings=list(session.exec(select(Spending)).all()),
        )

    def to_base(self, amount: float, currency: str, on: date) -> float:
        try:
            return self.fx.convert(amount, currency, on)
        except MissingRateError as exc:
            self.missing_rates.add(exc.currency)
            return 0.0

    def value_at(self, asset: Asset, on: date) -> float | None:
        """Valor (moneda base, con signo) de la última valuación <= `on`."""
        latest = None
        for v in self.valuations.get(asset.id or -1, []):
            if v.date > on:
                break
            latest = v
        if latest is None:
            return None
        value = self.to_base(latest.value, asset.currency, on)
        return -value if asset.is_liability else value


def _r(x: float) -> float:
    return round(x, 2)


def net_worth_at(snap: Snapshot, on: date) -> dict[str, float]:
    assets = liabilities = 0.0
    for asset in snap.assets:
        value = snap.value_at(asset, on)
        if value is None:
            continue
        if value < 0:
            liabilities += -value
        else:
            assets += value
    return {
        "assets": _r(assets),
        "liabilities": _r(liabilities),
        "net_worth": _r(assets - liabilities),
    }


def net_worth_history(snap: Snapshot, months: int = 24) -> list[Row]:
    all_dates = [v.date for vals in snap.valuations.values() for v in vals]
    if not all_dates:
        return []
    first = min(all_dates)
    points = []
    for year, month in last_n_months(snap.today, months):
        month_end = clamp_day(year, month, 31)
        on = min(month_end, snap.today)
        if on < first:
            continue
        points.append({"date": on.isoformat(), **net_worth_at(snap, on)})
    return points


def asset_rows(snap: Snapshot) -> list[Row]:
    rows = []
    for asset in snap.assets:
        vals = snap.valuations.get(asset.id or -1, [])
        current = vals[-1] if vals else None
        previous = vals[-2] if len(vals) > 1 else None
        value_base = snap.to_base(current.value, asset.currency, snap.today) if current else 0.0
        change_pct = None
        if current and previous and previous.value:
            change_pct = (current.value - previous.value) / previous.value * 100
        rows.append(
            {
                "id": asset.id,
                "name": asset.name,
                "type": asset.type,
                "is_liability": asset.is_liability,
                "currency": asset.currency,
                "liquidity": asset.liquidity,
                "institution": asset.institution,
                "archived": asset.archived,
                "tracks_positions": asset.tracks_positions,
                "value": current.value if current else None,
                "value_base": _r(value_base),
                "last_valuation": current.date.isoformat() if current else None,
                "change_pct": _r(change_pct) if change_pct is not None else None,
            }
        )
    return rows


def distribution(snap: Snapshot) -> dict[str, list[Row]]:
    by_type: dict[str, float] = defaultdict(float)
    by_currency: dict[str, float] = defaultdict(float)
    by_liquidity: dict[str, float] = defaultdict(float)
    for asset in snap.assets:
        if asset.is_liability or asset.archived:
            continue
        value = snap.value_at(asset, snap.today)
        if not value:
            continue
        by_type[asset.type] += value
        by_currency[asset.currency] += value
        by_liquidity[asset.liquidity] += value

    def fmt(d: dict[str, float]) -> list[Row]:
        return [{"key": k, "value": _r(v)} for k, v in sorted(d.items(), key=lambda kv: -kv[1])]

    return {
        "by_type": fmt(by_type),
        "by_currency": fmt(by_currency),
        "by_liquidity": fmt(by_liquidity),
    }


def _entry_base(snap: Snapshot, entry: IncomeEntry, source: IncomeSource) -> float:
    return snap.to_base(entry.gross_amount - entry.tax_withheld, source.currency, entry.date)


def income_by_month(snap: Snapshot, months: int = 12) -> list[Row]:
    sources = {s.id: s for s in snap.sources}
    keys = last_n_months(snap.today, months)
    buckets: dict[tuple[int, int], dict[str, float]] = {k: defaultdict(float) for k in keys}
    for entry in snap.entries:
        key = (entry.date.year, entry.date.month)
        source = sources.get(entry.source_id)
        if key not in buckets or source is None:
            continue
        buckets[key][source.name] += _entry_base(snap, entry, source)
    result = []
    for year, month in keys:
        row = {name: _r(v) for name, v in buckets[(year, month)].items()}
        result.append(
            {"month": f"{year:04d}-{month:02d}", "total": _r(sum(row.values())), "by_source": row}
        )
    return result


def _trailing_income(snap: Snapshot, months: int = 12) -> dict[int, float]:
    """Ingreso neto promedio mensual por fuente en los últimos `months` meses."""
    sources = {s.id: s for s in snap.sources}
    year, month = add_months(snap.today.year, snap.today.month, -(months - 1))
    since = date(year, month, 1)
    totals: dict[int, float] = defaultdict(float)
    for entry in snap.entries:
        source = sources.get(entry.source_id)
        if source is None or entry.date < since or entry.date > snap.today:
            continue
        totals[entry.source_id] += _entry_base(snap, entry, source)
    # Meses observados: desde la primera entrada (o el inicio de la ventana) hasta hoy.
    first_entry = min((e.date for e in snap.entries if e.date >= since), default=snap.today)
    observed = max(
        1, (snap.today.year - first_entry.year) * 12 + snap.today.month - first_entry.month + 1
    )
    return {sid: total / min(observed, months) for sid, total in totals.items()}


def income_sources_summary(snap: Snapshot) -> list[Row]:
    trailing = _trailing_income(snap)
    rows = []
    for s in snap.sources:
        expected = snap.to_base(
            monthly_amount(s.expected_amount, s.frequency), s.currency, snap.today
        )
        rows.append(
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "is_passive": s.is_passive,
                "active": s.active,
                "currency": s.currency,
                "frequency": s.frequency,
                "expected_amount": s.expected_amount,
                "expected_monthly_base": _r(expected if s.active else 0),
                "actual_monthly_base": _r(trailing.get(s.id or -1, 0.0)),
            }
        )
    return rows


def monthly_fixed_expenses(snap: Snapshot) -> float:
    total = 0.0
    for e in snap.expenses:
        if not e.active or (e.end_date and e.end_date < snap.today):
            continue
        total += snap.to_base(monthly_amount(e.amount, e.frequency), e.currency, snap.today)
    return total


def expenses_by_category(snap: Snapshot) -> list[Row]:
    totals: dict[str, float] = defaultdict(float)
    for e in snap.expenses:
        if not e.active or (e.end_date and e.end_date < snap.today):
            continue
        totals[e.category] += snap.to_base(
            monthly_amount(e.amount, e.frequency), e.currency, snap.today
        )
    return [{"key": k, "value": _r(v)} for k, v in sorted(totals.items(), key=lambda kv: -kv[1])]


def upcoming_payments(snap: Snapshot, days: int = 30, past_days: int = 7) -> list[Row]:
    """Vencimientos desde hace `past_days` (para ver atrasos) hasta dentro de `days`."""
    window_start = snap.today - timedelta(days=past_days)
    window_end = snap.today + timedelta(days=days)
    paid = {(p.expense_id, p.due_date): p for p in snap.payments}
    rows = []
    for e in snap.expenses:
        if not e.active:
            continue
        for due in occurrences(
            e.frequency, e.start_date, e.due_day, window_start, window_end, e.end_date
        ):
            payment = paid.get((e.id or -1, due))
            if due < snap.today and payment is None:
                status = "overdue"
            elif payment is not None:
                status = "paid"
            else:
                status = "pending"
            rows.append(
                {
                    "expense_id": e.id,
                    "name": e.name,
                    "category": e.category,
                    "due_date": due.isoformat(),
                    "amount": e.amount,
                    "currency": e.currency,
                    "amount_base": _r(snap.to_base(e.amount, e.currency, snap.today)),
                    "status": status,
                    "payment_id": payment.id if payment else None,
                }
            )
    rows.sort(key=lambda r: str(r["due_date"]))
    return rows


def summary(snap: Snapshot) -> Row:
    nw = net_worth_at(snap, snap.today)
    sources = income_sources_summary(snap)
    fixed = monthly_fixed_expenses(snap)

    def best(row: Row) -> float:
        actual = float(row["actual_monthly_base"])
        return actual if actual > 0 else float(row["expected_monthly_base"])

    monthly_income = sum(best(r) for r in sources if r["active"])
    passive_income = sum(best(r) for r in sources if r["active"] and r["is_passive"])
    variable = monthly_variable_spending(snap)
    free_cash_flow = monthly_income - fixed - variable

    liquid = 0.0
    for asset in snap.assets:
        if asset.is_liability or asset.archived or asset.liquidity not in LIQUID:
            continue
        liquid += snap.value_at(asset, snap.today) or 0.0

    month_key = f"{snap.today.year:04d}-{snap.today.month:02d}"
    this_month = next(
        (m["total"] for m in income_by_month(snap, 1) if m["month"] == month_key), 0.0
    )

    totals_12m: dict[str, float] = defaultdict(float)
    for row in sources:
        totals_12m[row["name"]] += float(row["actual_monthly_base"])
    total_actual = sum(totals_12m.values())
    concentration = max(totals_12m.values()) / total_actual * 100 if total_actual else None

    def ratio(a: float, b: float, scale: float = 1.0) -> float | None:
        return _r(a / b * scale) if b else None

    return {
        "base_currency": snap.fx.base,
        "as_of": snap.today.isoformat(),
        **nw,
        "liquid_assets": _r(liquid),
        "monthly_income": _r(monthly_income),
        "passive_monthly_income": _r(passive_income),
        "income_this_month": this_month,
        "monthly_fixed_expenses": _r(fixed),
        "monthly_variable_spending": _r(variable),
        "free_cash_flow": _r(free_cash_flow),
        "savings_rate_pct": ratio(free_cash_flow, monthly_income, 100),
        "passive_coverage_pct": ratio(passive_income, fixed, 100),
        "runway_months": ratio(liquid, fixed),
        "debt_to_assets_pct": ratio(nw["liabilities"], nw["assets"], 100),
        "income_concentration_pct": _r(concentration) if concentration is not None else None,
        "missing_rates": sorted(snap.missing_rates),
    }


def projection(
    start_net_worth: float, monthly_savings: float, annual_return_pct: float, years: int
) -> list[dict[str, float]]:
    """Proyección con aportación mensual constante e interés compuesto mensual."""
    monthly_rate = (1 + annual_return_pct / 100) ** (1 / 12) - 1
    value = start_net_worth
    contributed = start_net_worth
    points = [{"year": 0, "value": _r(value), "contributed": _r(contributed)}]
    for year in range(1, years + 1):
        for _ in range(12):
            value = value * (1 + monthly_rate) + monthly_savings
            contributed += monthly_savings
        points.append({"year": year, "value": _r(value), "contributed": _r(contributed)})
    return points


def asset_performance(
    snap: Snapshot, invested: dict[int, tuple[float, float]] | None = None
) -> list[Row]:
    """Rendimiento por activo: cambio de valor + ingresos asociados desde la primera valuación.

    `invested` da, para cuentas con posiciones, (costo de lo que sigue en cartera, ganancia
    realizada) en moneda base. Ahí el punto de partida es el dinero invertido y no la primera
    valuación, para que las aportaciones nuevas no cuenten como ganancia.
    """
    income_by_asset: dict[int, float] = defaultdict(float)
    sources = {s.id: s for s in snap.sources}
    rows = []
    for asset in snap.assets:
        vals = snap.valuations.get(asset.id or -1, [])
        if asset.is_liability or len(vals) < 1:
            continue
        first, last = vals[0], vals[-1]
        for entry in snap.entries:
            source = sources.get(entry.source_id)
            if source and source.asset_id == asset.id and entry.date >= first.date:
                income_by_asset[asset.id or -1] += snap.to_base(
                    entry.gross_amount - entry.tax_withheld, source.currency, entry.date
                )
        end_base = snap.to_base(last.value, asset.currency, snap.today)
        income = income_by_asset[asset.id or -1]
        days = (snap.today - first.date).days
        position_based = invested is not None and asset.id in invested
        if position_based:
            cost, realized = invested[asset.id]  # type: ignore[index]
            start_base = cost
            gain = end_base - cost + realized + income
        else:
            start_base = snap.to_base(first.value, asset.currency, first.date)
            gain = end_base - start_base + income
        total_return = gain / start_base if start_base else None
        annualized = None
        # Con aportaciones en distintas fechas, anualizar con una sola fecha de inicio engañaría.
        if not position_based and total_return is not None and days >= 30 and 1 + total_return > 0:
            annualized = ((1 + total_return) ** (365 / days) - 1) * 100
        rows.append(
            {
                "id": asset.id,
                "name": asset.name,
                "since": first.date.isoformat(),
                "basis": "cost" if position_based else "first_valuation",
                "start_value_base": _r(start_base),
                "current_value_base": _r(end_base),
                "income_base": _r(income),
                "gain_base": _r(gain),
                "total_return_pct": _r(total_return * 100) if total_return is not None else None,
                "annualized_return_pct": _r(annualized) if annualized is not None else None,
            }
        )
    rows.sort(key=lambda r: -float(r["gain_base"] or 0))
    return rows


def spending_totals(snap: Snapshot, year: int, month: int) -> dict[str, float]:
    """Gasto variable por categoría en un mes, en moneda base."""
    totals: dict[str, float] = defaultdict(float)
    for s in snap.spendings:
        if s.date.year == year and s.date.month == month:
            totals[s.category] += snap.to_base(s.amount, s.currency, s.date)
    return totals


def monthly_variable_spending(snap: Snapshot, months: int = 3) -> float:
    """Promedio mensual de gasto variable de los últimos `months` meses completos.

    Si aún no hay un mes completo con datos, usa el mes en curso proyectado a 30 días.
    """
    if not snap.spendings:
        return 0.0
    first = min(s.date for s in snap.spendings)
    complete = [
        key
        for key in last_n_months(snap.today, months + 1)[:-1]  # sin el mes en curso
        if date(key[0], key[1], 1) >= date(first.year, first.month, 1)
    ]
    if complete:
        total = sum(sum(spending_totals(snap, y, m).values()) for y, m in complete)
        return total / len(complete)
    current = sum(spending_totals(snap, snap.today.year, snap.today.month).values())
    return current / max(snap.today.day, 1) * 30


def budget_report(snap: Snapshot, limits: dict[str, float], year: int, month: int) -> Row:
    """Gasto real contra presupuesto por categoría, con proyección al cierre del mes."""
    totals = spending_totals(snap, year, month)
    last_day = clamp_day(year, month, 31).day
    is_current = (year, month) == (snap.today.year, snap.today.month)
    elapsed = snap.today.day if is_current else last_day
    categories = sorted(set(totals) | {k for k, v in limits.items() if v > 0})
    rows: list[Row] = []
    for cat in categories:
        spent = totals.get(cat, 0.0)
        limit = limits.get(cat) or 0.0
        projected = spent / elapsed * last_day if is_current and elapsed else spent
        rows.append(
            {
                "category": cat,
                "spent": _r(spent),
                "limit": _r(limit) if limit else None,
                "used_pct": _r(spent / limit * 100) if limit else None,
                "projected": _r(projected),
                "status": _budget_status(spent, projected, limit),
            }
        )
    rows.sort(key=lambda r: -float(r["spent"]))
    total_spent = sum(totals.values())
    total_limit = sum(v for v in limits.values() if v)
    return {
        "month": f"{year:04d}-{month:02d}",
        "categories": rows,
        "spent": _r(total_spent),
        "limit": _r(total_limit) if total_limit else None,
        "used_pct": _r(total_spent / total_limit * 100) if total_limit else None,
        "days_elapsed": elapsed,
        "days_in_month": last_day,
    }


def _budget_status(spent: float, projected: float, limit: float) -> str:
    if not limit:
        return "no_budget"
    if spent > limit:
        return "over"
    if projected > limit or spent >= limit * 0.8:
        return "warning"
    return "ok"


def spending_by_month(snap: Snapshot, months: int = 6) -> list[Row]:
    result = []
    for year, month in last_n_months(snap.today, months):
        totals = spending_totals(snap, year, month)
        result.append(
            {
                "month": f"{year:04d}-{month:02d}",
                "total": _r(sum(totals.values())),
                "by_category": {k: _r(v) for k, v in totals.items()},
            }
        )
    return result


def _months_between(start: date, end: date) -> float:
    return (end - start).days / 30.4375


def goal_progress(snap: Snapshot, goal: Goal, monthly_savings: float) -> Row:
    """Avance de una meta.

    El avance es el valor actual del activo ligado (p. ej. la cuenta del fondo de emergencia) o
    el monto capturado a mano. El ritmo se estima con lo que creció ese activo en los últimos
    6 meses; sin activo, con el ahorro mensual (flujo libre).
    """
    asset = next((a for a in snap.assets if a.id == goal.asset_id), None) if goal.asset_id else None
    if asset is not None:
        current = abs(snap.value_at(asset, snap.today) or 0.0)
        y, m = add_months(snap.today.year, snap.today.month, -6)
        past = snap.value_at(asset, clamp_day(y, m, snap.today.day))
        first = snap.valuations.get(asset.id or -1, [None])[0]
        if past is not None and first is not None:
            span = max(
                _months_between(max(first.date, clamp_day(y, m, snap.today.day)), snap.today), 1
            )
            pace = (current - abs(past)) / span
        else:
            pace = 0.0
    else:
        current = goal.manual_amount
        pace = monthly_savings
    remaining = max(goal.target_amount - current, 0.0)
    pct = min(current / goal.target_amount * 100, 100) if goal.target_amount else 0.0

    months_left = monthly_needed = None
    if goal.target_date:
        months_left = max(_months_between(snap.today, goal.target_date), 0.0)
        monthly_needed = remaining / months_left if months_left >= 1 else remaining

    eta = None
    if remaining == 0:
        status = "done"
    elif pace > 0:
        months_to_goal = remaining / pace
        eta_day = snap.today + timedelta(days=round(months_to_goal * 30.4375))
        eta = eta_day.isoformat()
        if goal.target_date:
            status = "on_track" if eta_day <= goal.target_date else "behind"
        else:
            status = "in_progress"
    else:
        status = "behind" if goal.target_date else "stalled"
    if goal.target_date and goal.target_date < snap.today and remaining > 0:
        status = "overdue"

    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": _r(goal.target_amount),
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "asset_id": goal.asset_id,
        "asset_name": asset.name if asset else None,
        "current": _r(current),
        "remaining": _r(remaining),
        "pct": _r(pct),
        "monthly_pace": _r(pace),
        "monthly_needed": _r(monthly_needed) if monthly_needed is not None else None,
        "eta": eta,
        "status": status,
        "archived": goal.archived,
    }
