from fastapi import APIRouter, Query
from sqlmodel import col, select

from mamoney.models import Asset
from mamoney.routers.common import SessionDep
from mamoney.services import analytics as an
from mamoney.services.portfolio import positions_report
from mamoney.settings_store import get_setting

router = APIRouter(prefix="/api/analytics", tags=["análisis"])


@router.get("/summary")
def summary(session: SessionDep) -> dict[str, object]:
    return an.summary(an.Snapshot.load(session))


@router.get("/net-worth-history")
def net_worth_history(
    session: SessionDep, months: int = Query(24, ge=1, le=240)
) -> list[dict[str, object]]:
    return an.net_worth_history(an.Snapshot.load(session), months)


@router.get("/assets")
def assets(session: SessionDep) -> list[dict[str, object]]:
    return an.asset_rows(an.Snapshot.load(session))


@router.get("/distribution")
def distribution(session: SessionDep) -> dict[str, list[dict[str, object]]]:
    return an.distribution(an.Snapshot.load(session))


@router.get("/income-by-month")
def income_by_month(
    session: SessionDep, months: int = Query(12, ge=1, le=120)
) -> list[dict[str, object]]:
    return an.income_by_month(an.Snapshot.load(session), months)


@router.get("/income-sources")
def income_sources(session: SessionDep) -> list[dict[str, object]]:
    return an.income_sources_summary(an.Snapshot.load(session))


@router.get("/expenses-by-category")
def expenses_by_category(session: SessionDep) -> list[dict[str, object]]:
    return an.expenses_by_category(an.Snapshot.load(session))


@router.get("/upcoming")
def upcoming(session: SessionDep, days: int = Query(30, ge=1, le=366)) -> list[dict[str, object]]:
    return an.upcoming_payments(an.Snapshot.load(session), days)


@router.get("/performance")
def performance(session: SessionDep) -> list[dict[str, object]]:
    invested: dict[int, tuple[float, float]] = {}
    for asset in session.exec(select(Asset).where(col(Asset.tracks_positions))).all():
        report = positions_report(session, asset.id)
        invested[asset.id] = (report["cost_base"], report["realized_base"])  # type: ignore[index]
    return an.asset_performance(an.Snapshot.load(session), invested)


@router.get("/projection")
def projection(
    session: SessionDep,
    years: int = Query(10, ge=1, le=50),
    annual_return_pct: float | None = Query(None, ge=-50, le=100),
    monthly_savings: float | None = None,
) -> dict[str, object]:
    snap = an.Snapshot.load(session)
    current = an.summary(snap)
    rate = (
        annual_return_pct
        if annual_return_pct is not None
        else float(get_setting(session, "projection_annual_return_pct"))
    )
    savings = monthly_savings if monthly_savings is not None else float(current["free_cash_flow"])
    start = float(current["net_worth"])
    return {
        "annual_return_pct": rate,
        "monthly_savings": savings,
        "points": an.projection(start, savings, rate, years),
    }
