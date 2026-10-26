import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from mamoney.models import Asset, AssetBase, AssetValuation, AssetValuationBase
from mamoney.routers.common import SessionDep, apply_update, get_or_404, save
from mamoney.schemas import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    ValuationCreate,
    ValuationRead,
    ValuationUpdate,
)
from mamoney.services import portfolio

router = APIRouter(prefix="/api", tags=["patrimonio"])


@router.get("/assets", response_model=list[AssetRead])
def list_assets(session: SessionDep) -> list[Asset]:
    return list(session.exec(select(Asset).order_by(Asset.name)).all())


@router.post("/assets", response_model=AssetRead, status_code=201)
def create_asset(data: AssetCreate, session: SessionDep) -> Asset:
    asset = save(
        session, Asset.model_validate(data.model_dump(exclude={"initial_value", "initial_date"}))
    )
    if data.initial_value is not None and not data.tracks_positions:
        save(
            session,
            AssetValuation(
                asset_id=asset.id,  # type: ignore[arg-type]
                date=data.initial_date or dt.date.today(),
                value=data.initial_value,
            ),
        )
    return asset


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: int, session: SessionDep) -> Asset:
    return get_or_404(session, Asset, asset_id)


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: int, data: AssetUpdate, session: SessionDep) -> Asset:
    asset = save(session, apply_update(get_or_404(session, Asset, asset_id), data, AssetBase))
    if asset.tracks_positions:
        portfolio.sync_account(session, asset)  # p. ej. cambió la moneda de la cuenta
    return asset


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Asset, asset_id))
    session.commit()


@router.get("/assets/{asset_id}/valuations", response_model=list[ValuationRead])
def list_valuations(asset_id: int, session: SessionDep) -> list[AssetValuation]:
    get_or_404(session, Asset, asset_id)
    query = (
        select(AssetValuation)
        .where(AssetValuation.asset_id == asset_id)
        .order_by(AssetValuation.date)  # type: ignore[arg-type]
    )
    return list(session.exec(query).all())


@router.post("/assets/{asset_id}/valuations", response_model=ValuationRead, status_code=201)
def add_valuation(asset_id: int, data: ValuationCreate, session: SessionDep) -> AssetValuation:
    asset = get_or_404(session, Asset, asset_id)
    if asset.tracks_positions:
        raise HTTPException(
            409, "Esta cuenta se valúa con sus posiciones; registra compras y ventas en Inversiones"
        )
    # Una sola valuación por día: si ya existe, se reemplaza.
    existing = session.exec(
        select(AssetValuation).where(
            AssetValuation.asset_id == asset_id, AssetValuation.date == data.date
        )
    ).first()
    if existing:
        existing.value = data.value
        existing.notes = data.notes
        return save(session, existing)
    return save(session, AssetValuation(asset_id=asset_id, **data.model_dump()))


@router.patch("/valuations/{valuation_id}", response_model=ValuationRead)
def update_valuation(
    valuation_id: int, data: ValuationUpdate, session: SessionDep
) -> AssetValuation:
    valuation = get_or_404(session, AssetValuation, valuation_id)
    return save(session, apply_update(valuation, data, AssetValuationBase))


@router.delete("/valuations/{valuation_id}", status_code=204)
def delete_valuation(valuation_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, AssetValuation, valuation_id))
    session.commit()
