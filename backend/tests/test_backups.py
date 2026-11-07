import datetime as dt
import sqlite3

from fastapi.testclient import TestClient

from mamoney.config import get_config
from mamoney.services import backups, updater


def _clear_auto() -> None:
    for f in backups._auto_backups():
        f.unlink()


def test_auto_backup_once_per_day_and_valid(client: TestClient) -> None:
    _clear_auto()
    client.post("/api/assets", json={"name": "Banco", "type": "bank"})
    day = dt.date(2026, 11, 6)
    created = backups.auto_backup(day)
    assert created is not None and created.name == "mamoney-20261106.db"
    assert backups.auto_backup(day) is None  # el de hoy ya existe
    conn = sqlite3.connect(created)  # `with` no cierra la conexión en sqlite3
    try:
        assert conn.execute("SELECT name FROM asset").fetchall() == [("Banco",)]
    finally:
        conn.close()
    status = client.get("/api/backup/status").json()
    assert status["auto_count"] == 1 and status["last_auto"]


def test_auto_backup_keeps_latest_and_ignores_manual() -> None:
    _clear_auto()
    manual = get_config().backup_dir / "antes-de-v9.9.9.db"
    manual.parent.mkdir(parents=True, exist_ok=True)
    manual.write_bytes(b"manual")
    start = dt.date(2026, 10, 1)
    for i in range(5):
        backups.auto_backup(start + dt.timedelta(days=i), keep=3)
    names = [p.name for p in backups._auto_backups()]
    assert names == ["mamoney-20261003.db", "mamoney-20261004.db", "mamoney-20261005.db"]
    assert manual.exists()


def test_old_update_folders_are_removed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    for name in ("v0.3.0", "v0.4.0"):
        (tmp_path / name / "Mamoney").mkdir(parents=True)
    (tmp_path / "update.log").write_text("log")
    updater.remove_old_staging(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["update.log"]
