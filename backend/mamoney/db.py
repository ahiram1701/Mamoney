"""Motor SQLite, sesiones y migraciones Alembic."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, event
from sqlmodel import Session, create_engine

from mamoney.config import get_config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


@lru_cache
def get_engine() -> Engine:
    url = f"sqlite:///{get_config().db_path.as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def alembic_config() -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", MIGRATIONS_DIR.as_posix())
    return cfg


def init_db() -> None:
    """Aplica las migraciones pendientes usando el motor de la app."""
    cfg = alembic_config()
    with get_engine().begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
