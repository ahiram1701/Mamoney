"""Ajustes clave/valor persistidos en la tabla `setting`."""

import json
import secrets
from typing import Any

from sqlmodel import Session

from mamoney.models import Setting

DEFAULTS: dict[str, Any] = {
    "currencies": ["MXN", "USD", "EUR"],
    "allowed_logins": [],
    "pin_hash": None,
    "session_secret": None,
    "projection_annual_return_pct": 7.0,
}


def get_setting(session: Session, key: str) -> Any:
    row = session.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key)
    return json.loads(row.value)


def set_setting(session: Session, key: str, value: Any) -> None:
    row = session.get(Setting, key) or Setting(key=key, value="null")
    row.value = json.dumps(value)
    session.add(row)
    session.commit()


def session_secret(session: Session) -> str:
    secret = get_setting(session, "session_secret")
    if not secret:
        secret = secrets.token_hex(32)
        set_setting(session, "session_secret", secret)
    return str(secret)
