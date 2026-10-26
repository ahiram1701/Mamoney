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


def make_engine(db_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine(get_config().db_path)


def alembic_config() -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", MIGRATIONS_DIR.as_posix())
    return cfg


def init_db(engine: Engine | None = None, revision: str = "head") -> None:
    """Aplica las migraciones pendientes.

    Las llaves foráneas se desactivan mientras dura la migración, como recomienda SQLite: al
    reconstruir una tabla (ALTER en modo batch), el DROP de la tabla vieja dispararía los
    ON DELETE CASCADE y borraría los datos relacionados. El PRAGMA no tiene efecto dentro de una
    transacción, por eso se ejecuta y confirma antes de abrirla.
    """
    cfg = alembic_config()
    with (engine or get_engine()).connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            with connection.begin():
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, revision)
                problems = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if problems:
                    raise RuntimeError(f"La migración dejó referencias rotas: {problems[:5]}")
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
