import datetime as dt
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from mamoney.db import get_engine
from mamoney.models import Asset, Security, SecurityKind, Trade, TradeSide
from mamoney.routers.common import SessionDep, get_or_404
from mamoney.services import portfolio, quotes

router = APIRouter(prefix="/api/portfolio", tags=["inversiones"])


class TradeCreate(BaseModel):
    asset_id: int
    symbol: str = Field(min_length=1, max_length=24)
    kind: SecurityKind | None = None
    date: dt.date
    side: TradeSide = TradeSide.buy
    quantity: float = Field(gt=0)
    price: float = Field(ge=0)
    fee: float = Field(default=0, ge=0)
    notes: str | None = None


def _tracked_account(session: Session, asset_id: int) -> Asset:
    asset = get_or_404(session, Asset, asset_id)
    if not asset.tracks_positions:
        raise HTTPException(409, "Esta cuenta no lleva posiciones; actívalo al editarla")
    return asset


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=60)) -> list[dict[str, Any]]:
    try:
        return await run_in_threadpool(quotes.search, q)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"No se pudo buscar en Yahoo Finance: {exc}") from exc


@router.get("/quote")
async def quote(symbol: str, kind: SecurityKind | None = None) -> dict[str, Any]:
    normalized = quotes.normalize_symbol(symbol, kind)
    try:
        result = await run_in_threadpool(quotes.fetch_quote, normalized)
    except (quotes.QuoteError, httpx.HTTPError) as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "symbol": result.symbol,
        "price": result.price,
        "currency": result.currency,
        "name": result.name,
        "kind": result.kind,
    }


@router.get("/positions")
def positions(session: SessionDep, asset_id: int | None = None) -> dict[str, Any]:
    return portfolio.positions_report(session, asset_id)


@router.get("/trades")
def list_trades(session: SessionDep, asset_id: int | None = None) -> list[dict[str, Any]]:
    query = select(Trade, Security, Asset).join(Security).join(Asset)
    if asset_id is not None:
        query = query.where(Trade.asset_id == asset_id)
    rows = session.exec(query.order_by(col(Trade.date).desc(), col(Trade.id).desc())).all()
    return [
        {
            **trade.model_dump(mode="json"),
            "symbol": sec.symbol,
            "security_name": sec.name,
            "currency": sec.currency,
            "account": asset.name,
            "total": round(
                trade.quantity * trade.price
                + (trade.fee if trade.side == TradeSide.buy else -trade.fee),
                2,
            ),
        }
        for trade, sec, asset in rows
    ]


@router.post("/trades", status_code=201)
def add_trade(data: TradeCreate, session: SessionDep) -> dict[str, Any]:
    asset = _tracked_account(session, data.asset_id)
    try:
        security = portfolio.get_or_create_security(session, data.symbol, data.kind)
        trade = Trade(
            asset_id=data.asset_id,
            security_id=security.id,  # type: ignore[arg-type]
            **data.model_dump(exclude={"asset_id", "symbol", "kind"}),
        )
        # Valida que las ventas no superen los títulos en ninguna fecha.
        portfolio.apply_trades([*portfolio.account_trades(session, asset.id), trade])  # type: ignore[arg-type]
    except portfolio.PortfolioError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from exc
    session.add(trade)
    session.commit()
    session.refresh(trade)
    result = {**trade.model_dump(mode="json"), "symbol": security.symbol}
    portfolio.ensure_history(session, security, data.date)
    session.commit()
    portfolio.sync_account(session, asset)
    return result


@router.delete("/trades/{trade_id}", status_code=204)
def delete_trade(trade_id: int, session: SessionDep) -> None:
    trade = get_or_404(session, Trade, trade_id)
    asset = get_or_404(session, Asset, trade.asset_id)
    remaining = [t for t in portfolio.account_trades(session, asset.id) if t.id != trade_id]  # type: ignore[arg-type]
    try:
        portfolio.apply_trades(remaining)
    except portfolio.PortfolioError as exc:
        raise HTTPException(
            422, f"No se puede borrar: dejaría ventas sin títulos suficientes. {exc}"
        ) from exc
    session.delete(trade)
    session.commit()
    portfolio.sync_account(session, asset)


@router.post("/refresh")
async def refresh() -> dict[str, int]:
    def run() -> dict[str, int]:
        with Session(get_engine()) as session:
            return portfolio.refresh_prices(session)

    return await run_in_threadpool(run)
