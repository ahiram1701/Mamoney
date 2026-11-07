"""Respaldos de la base de datos: manuales, antes de cada actualización y diarios automáticos."""

import datetime as dt
import logging
import sqlite3
from pathlib import Path
from typing import Any

from mamoney.config import get_config

log = logging.getLogger(__name__)

AUTO_KEEP = 14
AUTO_PREFIX = "mamoney-"


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


def auto_dir() -> Path:
    return get_config().backup_dir / "auto"


def _auto_backups() -> list[Path]:
    folder = auto_dir()
    if not folder.exists():
        return []
    # El nombre lleva la fecha (AAAAMMDD): el orden alfabético es el cronológico.
    return sorted(folder.glob(f"{AUTO_PREFIX}*.db"))


def auto_backup(today: dt.date | None = None, keep: int = AUTO_KEEP) -> Path | None:
    """Un respaldo por día en `backups/auto`; conserva los `keep` más recientes.

    Devuelve la ruta creada, o None si el de hoy ya existía. No toca los respaldos manuales ni
    los que se hacen antes de actualizar, que viven fuera de `auto`.
    """
    today = today or dt.date.today()
    folder = auto_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{AUTO_PREFIX}{today:%Y%m%d}.db"
    created = None
    if not target.exists():
        partial = target.with_suffix(".tmp")
        backup_database(partial)
        partial.replace(target)  # nunca queda un respaldo a medias con nombre válido
        created = target
        log.info("Respaldo automático guardado en %s", target)
    for old in _auto_backups()[:-keep]:
        old.unlink(missing_ok=True)
    return created


def backup_status() -> dict[str, Any]:
    backups = _auto_backups()
    latest = backups[-1] if backups else None
    return {
        "folder": str(get_config().backup_dir),
        "auto_count": len(backups),
        "auto_keep": AUTO_KEEP,
        "last_auto": (
            dt.datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="minutes")
            if latest
            else None
        ),
    }
