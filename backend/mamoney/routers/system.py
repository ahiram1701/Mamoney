"""Salud, autenticación por PIN, ajustes y respaldos."""

import datetime as dt
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import SQLModel, delete, select
from starlette.background import BackgroundTask

from mamoney import __version__
from mamoney.config import get_config
from mamoney.models import (
    Asset,
    AssetValuation,
    ExpensePayment,
    FixedExpense,
    FxRate,
    IncomeEntry,
    IncomeSource,
)
from mamoney.routers.common import SessionDep
from mamoney.schemas import PinLogin, PinUpdate, SettingsUpdate
from mamoney.security import (
    SESSION_COOKIE,
    SESSION_TTL,
    evaluate,
    hash_pin,
    make_session_token,
    verify_pin,
)
from mamoney.settings_store import get_setting, session_secret, set_setting

router = APIRouter(prefix="/api", tags=["sistema"])

# Orden de inserción que respeta las llaves foráneas.
EXPORT_TABLES: list[type[SQLModel]] = [
    Asset,
    AssetValuation,
    IncomeSource,
    IncomeEntry,
    FixedExpense,
    ExpensePayment,
    FxRate,
]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/auth/status")
def auth_status(request: Request, session: SessionDep) -> dict[str, Any]:
    access = evaluate(request, session)
    return {
        "authorized": access.allowed,
        "reason": access.reason,
        "is_local": access.is_local,
        "identity": access.identity,
        "pin_enabled": bool(get_setting(session, "pin_hash")),
    }


@router.post("/auth/pin")
def login_pin(
    data: PinLogin, request: Request, response: Response, session: SessionDep
) -> dict[str, bool]:
    access = evaluate(request, session, check_pin=False)
    if not access.allowed:
        raise HTTPException(access.status, access.reason)
    stored = get_setting(session, "pin_hash")
    if not stored or not verify_pin(data.pin, stored):
        raise HTTPException(401, "PIN incorrecto")
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(session_secret(session)),
        max_age=SESSION_TTL,
        httponly=True,
        samesite="strict",
        secure=not access.is_local,
    )
    return {"ok": True}


@router.get("/settings")
def read_settings(session: SessionDep) -> dict[str, Any]:
    return {
        "base_currency": get_config().base_currency,
        "currencies": get_setting(session, "currencies"),
        "allowed_logins": get_setting(session, "allowed_logins"),
        "projection_annual_return_pct": get_setting(session, "projection_annual_return_pct"),
        "pin_enabled": bool(get_setting(session, "pin_hash")),
        "data_dir": str(get_config().data_dir),
        "version": __version__,
    }


@router.patch("/settings")
def update_settings(data: SettingsUpdate, session: SessionDep) -> dict[str, Any]:
    if data.currencies is not None:
        currencies = sorted({c.strip().upper() for c in data.currencies if c.strip()})
        set_setting(session, "currencies", currencies)
    if data.allowed_logins is not None:
        logins = sorted({x.strip().lower() for x in data.allowed_logins if x.strip()})
        set_setting(session, "allowed_logins", logins)
    if data.projection_annual_return_pct is not None:
        set_setting(session, "projection_annual_return_pct", data.projection_annual_return_pct)
    return read_settings(session)


@router.put("/settings/pin")
def update_pin(data: PinUpdate, session: SessionDep) -> dict[str, bool]:
    if data.pin:
        if not data.pin.isdigit() or not 4 <= len(data.pin) <= 12:
            raise HTTPException(422, "El PIN debe tener de 4 a 12 dígitos")
        set_setting(session, "pin_hash", hash_pin(data.pin))
    else:
        set_setting(session, "pin_hash", None)
    # Rotar el secreto invalida las sesiones remotas abiertas.
    set_setting(session, "session_secret", None)
    return {"pin_enabled": bool(data.pin)}


def backup_database(destination: Path) -> Path:
    """Copia consistente de la base con la API de respaldo de SQLite."""
    source = sqlite3.connect(get_config().db_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


@router.get("/backup/db")
def download_db() -> FileResponse:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp = Path(tempfile.mkdtemp()) / f"mamoney-{stamp}.db"
    backup_database(tmp)
    return FileResponse(
        tmp,
        filename=tmp.name,
        media_type="application/vnd.sqlite3",
        background=BackgroundTask(tmp.unlink, missing_ok=True),
    )


@router.get("/backup/export")
def export_json(session: SessionDep) -> dict[str, Any]:
    return {
        "app": "mamoney",
        "version": __version__,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "tables": {
            str(model.__tablename__): [
                row.model_dump(mode="json") for row in session.exec(select(model)).all()
            ]
            for model in EXPORT_TABLES
        },
        "settings": {
            key: get_setting(session, key)
            for key in ("currencies", "allowed_logins", "projection_annual_return_pct")
        },
    }


@router.post("/backup/import")
def import_json(payload: dict[str, Any], session: SessionDep) -> dict[str, int]:
    """Reemplaza todos los datos por los de una exportación JSON (hace respaldo antes)."""
    if payload.get("app") != "mamoney" or "tables" not in payload:
        raise HTTPException(422, "El archivo no es una exportación de Mamoney")
    cfg = get_config()
    cfg.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_database(cfg.backup_dir / f"antes-de-importar-{stamp}.db")

    counts: dict[str, int] = {}
    for model in reversed(EXPORT_TABLES):
        session.exec(delete(model))
    for model in EXPORT_TABLES:
        name = str(model.__tablename__)
        rows = payload["tables"].get(name, [])
        for row in rows:
            session.add(model.model_validate(row))
        counts[name] = len(rows)
    for key, value in (payload.get("settings") or {}).items():
        set_setting(session, key, value)
    session.commit()
    return counts
