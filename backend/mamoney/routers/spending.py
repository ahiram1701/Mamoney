import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import col, select

from mamoney.models import Budget, Spending, SpendingBase, SpendingCategory
from mamoney.routers.common import SessionDep, apply_update, get_or_404, save
from mamoney.schemas import partial
from mamoney.services import analytics as an

router = APIRouter(prefix="/api", tags=["gastos variables"])

SpendingUpdate = partial(SpendingBase, "SpendingUpdate")


class SpendingCreate(SpendingBase):
    pass


def _month(value: str | None) -> tuple[int, int]:
    if not value:
        today = dt.date.today()
        return today.year, today.month
    try:
        year, month = (int(x) for x in value.split("-"))
        dt.date(year, month, 1)
    except ValueError as exc:
        raise HTTPException(422, "Mes inválido; usa el formato AAAA-MM") from exc
    return year, month


@router.get("/spending")
def list_spending(session: SessionDep, month: str | None = None) -> list[Spending]:
    year, mon = _month(month)
    start = dt.date(year, mon, 1)
    end = dt.date(year + (mon == 12), mon % 12 + 1, 1)
    query = (
        select(Spending)
        .where(col(Spending.date) >= start, col(Spending.date) < end)
        .order_by(col(Spending.date).desc(), col(Spending.id).desc())
    )
    return list(session.exec(query).all())


@router.post("/spending", status_code=201)
def create_spending(data: SpendingCreate, session: SessionDep) -> Spending:
    payload = data.model_dump()
    payload["currency"] = payload["currency"].upper()
    return save(session, Spending.model_validate(payload))


@router.patch("/spending/{spending_id}")
def update_spending(spending_id: int, data: SpendingUpdate, session: SessionDep) -> Spending:  # type: ignore[valid-type]
    item = get_or_404(session, Spending, spending_id)
    return save(session, apply_update(item, data, SpendingBase))


@router.delete("/spending/{spending_id}", status_code=204)
def delete_spending(spending_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Spending, spending_id))
    session.commit()


def budget_limits(session: SessionDep) -> dict[str, float]:
    return {b.category: b.monthly_limit for b in session.exec(select(Budget)).all()}


@router.get("/budget")
def get_budget(session: SessionDep) -> dict[str, float]:
    return budget_limits(session)


class BudgetUpdate(BaseModel):
    limits: dict[SpendingCategory, float | None] = Field(
        description="Límite mensual por categoría en MXN; vacío o 0 quita el límite"
    )


@router.put("/budget")
def set_budget(data: BudgetUpdate, session: SessionDep) -> dict[str, float]:
    for category, limit in data.limits.items():
        row = session.get(Budget, category)
        if not limit or limit <= 0:
            if row:
                session.delete(row)
            continue
        if row:
            row.monthly_limit = limit
        else:
            session.add(Budget(category=category, monthly_limit=limit))
    session.commit()
    return budget_limits(session)


@router.get("/analytics/budget")
def budget_report(session: SessionDep, month: str | None = None) -> dict[str, Any]:
    year, mon = _month(month)
    return an.budget_report(an.Snapshot.load(session), budget_limits(session), year, mon)


@router.get("/analytics/spending-by-month")
def spending_by_month(
    session: SessionDep, months: int = Query(6, ge=1, le=36)
) -> list[dict[str, Any]]:
    return an.spending_by_month(an.Snapshot.load(session), months)
