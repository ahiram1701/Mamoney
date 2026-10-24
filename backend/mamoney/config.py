"""Configuración de la app leída de variables de entorno."""

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Mamoney"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mamoney"


def _bundle_dir() -> Path:
    """Directorio de recursos: el del paquete o el temporal de PyInstaller."""
    frozen_dir = getattr(sys, "_MEIPASS", None)
    if frozen_dir:
        return Path(frozen_dir)
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    data_dir: Path
    host: str
    port: int
    base_currency: str
    fx_auto_update: bool
    static_dir: Path

    @property
    def db_path(self) -> Path:
        return self.data_dir / "mamoney.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"


@lru_cache
def get_config() -> Config:
    data_dir = Path(os.environ.get("MAMONEY_DATA_DIR", _default_data_dir()))
    data_dir.mkdir(parents=True, exist_ok=True)
    static_default = _bundle_dir() / "frontend" / "dist"
    return Config(
        data_dir=data_dir,
        host=os.environ.get("MAMONEY_HOST", "127.0.0.1"),
        port=int(os.environ.get("MAMONEY_PORT", "8765")),
        base_currency="MXN",
        fx_auto_update=os.environ.get("MAMONEY_FX_AUTO", "1") == "1",
        static_dir=Path(os.environ.get("MAMONEY_STATIC_DIR", static_default)),
    )
