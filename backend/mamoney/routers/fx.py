from fastapi import APIRouter
from sqlmodel import Session, select

from mamoney.config import get_config
from mamoney.models import Asset, FixedExpense, FxRate, IncomeSource
from mamoney.routers.common import SessionDep, get_or_404
from mamoney.schemas import FxRateCreate
from mamoney.services.fx import refresh_rates, upsert_rate
from mamoney.settings_store import get_setting

router = APIRouter(prefix="/api/fx", tags=["tipos de cambio"])


def currencies_in_use(session: Session) -> set[str]:
    used: set[str] = {c.upper() for c in get_setting(session, "currencies") or []}
    for model in (Asset, IncomeSource, FixedExpense):
        used.update(c.upper() for c in session.exec(select(model.currency)).all())
    used.discard(get_config().base_currency)
    return used


@router.get("/rates", response_model=list[FxRate])
def list_rates(session: SessionDep, currency: str | None = None) -> list[FxRate]:
    query = select(FxRate)
    if currency:
        query = query.where(FxRate.currency == currency.upper())
    return list(session.exec(query.order_by(FxRate.date.desc())).all())  # type: ignore[attr-defined]


@router.get("/latest")
def latest_rates(session: SessionDep) -> list[dict[str, object]]:
    rows: dict[str, FxRate] = {}
    for rate in session.exec(select(FxRate).order_by(FxRate.date)).all():  # type: ignore[arg-type]
        rows[rate.currency] = rate
    result: list[dict[str, object]] = []
    for currency in sorted(currencies_in_use(session) | set(rows)):
        latest = rows.get(currency)
        result.append(
            {
                "currency": currency,
                "rate_to_base": latest.rate_to_base if latest else None,
                "date": latest.date.isoformat() if latest else None,
                "source": latest.source if latest else None,
            }
        )
    return result


@router.post("/rates", response_model=FxRate, status_code=201)
def add_rate(data: FxRateCreate, session: SessionDep) -> FxRate:
    record = upsert_rate(session, data.currency, data.date, data.rate_to_base, "manual")
    session.commit()
    session.refresh(record)
    return record


@router.delete("/rates/{rate_id}", status_code=204)
def delete_rate(rate_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, FxRate, rate_id))
    session.commit()


@router.post("/refresh")
def refresh(session: SessionDep) -> dict[str, int]:
    return {"updated": refresh_rates(session, currencies_in_use(session))}
