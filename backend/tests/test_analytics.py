from datetime import date

import pytest

from mamoney.models import (
    Asset,
    AssetType,
    AssetValuation,
    ExpenseCategory,
    ExpensePayment,
    FixedExpense,
    Frequency,
    FxRate,
    IncomeEntry,
    IncomeSource,
    IncomeType,
    Liquidity,
)
from mamoney.services import analytics as an
from mamoney.services.fx import FxTable

TODAY = date(2026, 6, 15)


def _snapshot() -> an.Snapshot:
    assets = [
        Asset(
            id=1, name="Banco", type=AssetType.bank, currency="MXN", liquidity=Liquidity.immediate
        ),
        Asset(
            id=2,
            name="Broker USD",
            type=AssetType.investment,
            currency="USD",
            liquidity=Liquidity.short,
        ),
        Asset(
            id=3,
            name="Depa",
            type=AssetType.real_estate,
            currency="MXN",
            liquidity=Liquidity.illiquid,
        ),
        Asset(id=4, name="Hipoteca", type=AssetType.mortgage, currency="MXN", is_liability=True),
    ]
    valuations = {
        1: [AssetValuation(id=1, asset_id=1, date=date(2026, 1, 1), value=100_000)],
        2: [
            AssetValuation(id=2, asset_id=2, date=date(2026, 1, 1), value=10_000),
            AssetValuation(id=3, asset_id=2, date=date(2026, 6, 1), value=11_000),
        ],
        3: [AssetValuation(id=4, asset_id=3, date=date(2026, 1, 1), value=2_000_000)],
        4: [AssetValuation(id=5, asset_id=4, date=date(2026, 1, 1), value=1_000_000)],
    }
    sources = [
        IncomeSource(
            id=1,
            name="Sueldo",
            type=IncomeType.salary,
            frequency=Frequency.monthly,
            expected_amount=50_000,
        ),
        IncomeSource(
            id=2,
            name="Renta depa",
            type=IncomeType.rent,
            is_passive=True,
            frequency=Frequency.monthly,
            expected_amount=12_000,
            asset_id=3,
        ),
    ]
    entries = [
        IncomeEntry(
            id=i, source_id=1, date=date(2026, m, 1), gross_amount=55_000, tax_withheld=5_000
        )
        for i, m in enumerate(range(1, 7), start=1)
    ] + [IncomeEntry(id=100, source_id=2, date=date(2026, 6, 5), gross_amount=12_000)]
    expenses = [
        FixedExpense(
            id=1,
            name="Hipoteca",
            category=ExpenseCategory.housing,
            amount=15_000,
            frequency=Frequency.monthly,
            due_day=10,
            start_date=date(2025, 1, 1),
        ),
        FixedExpense(
            id=2,
            name="Luz",
            category=ExpenseCategory.utilities,
            amount=1_200,
            frequency=Frequency.bimonthly,
            due_day=20,
            start_date=date(2026, 2, 1),
        ),
        FixedExpense(
            id=3,
            name="Netflix",
            category=ExpenseCategory.subscriptions,
            amount=15,
            currency="USD",
            frequency=Frequency.monthly,
            due_day=1,
            start_date=date(2026, 1, 1),
        ),
    ]
    payments = [
        ExpensePayment(
            id=1,
            expense_id=1,
            due_date=date(2026, 6, 10),
            paid_date=date(2026, 6, 9),
            amount=15_000,
        )
    ]
    fx = FxTable([FxRate(currency="USD", date=date(2026, 1, 1), rate_to_base=20.0)], base="MXN")
    return an.Snapshot(assets, valuations, sources, entries, expenses, payments, fx, TODAY)


def test_net_worth_converts_currencies_and_subtracts_debt() -> None:
    nw = an.net_worth_at(_snapshot(), TODAY)
    assert nw["assets"] == 100_000 + 11_000 * 20 + 2_000_000
    assert nw["liabilities"] == 1_000_000
    assert nw["net_worth"] == nw["assets"] - 1_000_000


def test_net_worth_history_uses_valuations_in_time() -> None:
    history = an.net_worth_history(_snapshot(), months=6)
    first, last = history[0], history[-1]
    assert first["date"] == "2026-01-31"
    assert first["assets"] == 100_000 + 10_000 * 20 + 2_000_000
    assert last["date"] == TODAY.isoformat()


def test_summary_metrics() -> None:
    s = an.summary(_snapshot())
    fixed = 15_000 + 600 + 15 * 20
    assert s["monthly_fixed_expenses"] == fixed
    # Sueldo: 50 000 netos al mes observados; renta: 12 000 en 6 meses observados.
    assert s["monthly_income"] == pytest.approx(50_000 + 2_000)
    assert s["passive_monthly_income"] == pytest.approx(2_000)
    assert s["passive_coverage_pct"] == pytest.approx(round(2_000 / fixed * 100, 2))
    assert s["liquid_assets"] == 100_000 + 220_000
    assert s["runway_months"] == pytest.approx(round(320_000 / fixed, 2))
    assert s["income_this_month"] == 62_000
    assert s["missing_rates"] == []


def test_missing_rate_is_reported_not_fatal() -> None:
    snap = _snapshot()
    snap.fx = FxTable([], base="MXN")
    s = an.summary(snap)
    assert s["missing_rates"] == ["USD"]


def test_upcoming_payment_statuses() -> None:
    rows = an.upcoming_payments(_snapshot(), days=30, past_days=15)
    by_key = {(r["name"], r["due_date"]): r["status"] for r in rows}
    assert by_key[("Hipoteca", "2026-06-10")] == "paid"
    assert by_key[("Netflix", "2026-06-01")] == "overdue"
    assert by_key[("Netflix", "2026-07-01")] == "pending"
    assert ("Luz", "2026-06-20") in by_key


def test_distribution_excludes_liabilities() -> None:
    dist = an.distribution(_snapshot())
    keys = {d["key"] for d in dist["by_type"]}
    assert "mortgage" not in keys
    assert dist["by_currency"][0]["key"] == "MXN"


def test_projection_compounds() -> None:
    points = an.projection(100_000, 1_000, 0, 2)
    assert points[-1]["value"] == 124_000
    grown = an.projection(100_000, 0, 10, 1)
    assert grown[-1]["value"] == pytest.approx(110_000, rel=1e-6)


def test_asset_performance_includes_linked_income() -> None:
    rows = {r["name"]: r for r in an.asset_performance(_snapshot())}
    assert rows["Depa"]["income_base"] == 12_000
    assert rows["Broker USD"]["gain_base"] == 20_000
