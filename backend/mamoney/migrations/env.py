from alembic import context
from sqlalchemy import Connection
from sqlmodel import SQLModel

import mamoney.models  # noqa: F401  registra las tablas en el metadata
from mamoney.db import get_engine

config = context.config
target_metadata = SQLModel.metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


# La app pasa su propia conexión; si no, se usa el motor configurado (MAMONEY_DATA_DIR).
existing = config.attributes.get("connection")
if existing is not None:
    _run(existing)
else:
    with get_engine().connect() as conn:
        _run(conn)
        conn.commit()
