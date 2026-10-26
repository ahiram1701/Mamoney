import os
import tempfile
from collections.abc import Iterator

# Debe configurarse antes de importar mamoney: la configuración se cachea.
os.environ["MAMONEY_DATA_DIR"] = tempfile.mkdtemp(prefix="mamoney-test-")
os.environ["MAMONEY_FX_AUTO"] = "0"
os.environ["MAMONEY_UPDATE_CHECK"] = "0"
os.environ["MAMONEY_QUOTES_AUTO"] = "0"
os.environ["MAMONEY_STATIC_DIR"] = tempfile.mkdtemp(prefix="mamoney-static-")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from mamoney.db import get_engine, init_db
from mamoney.main import app

init_db()


@pytest.fixture(autouse=True)
def _clean_db() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Cliente que simula la ventana local de escritorio."""
    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)) as c:
        yield c


@pytest.fixture
def tailnet_client() -> Iterator[TestClient]:
    """Cliente que simula una petición reenviada por `tailscale serve`."""
    with TestClient(
        app,
        base_url="https://pc.tailnet.ts.net",
        client=("127.0.0.1", 50001),
        headers={"Tailscale-User-Login": "yo@example.com"},
    ) as c:
        yield c
