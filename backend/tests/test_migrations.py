"""Las migraciones deben conservar los datos existentes."""

from pathlib import Path

from sqlalchemy import text

from mamoney.db import init_db, make_engine

TABLES = (
    "asset",
    "assetvaluation",
    "incomesource",
    "incomeentry",
    "fixedexpense",
    "expensepayment",
)


def _counts(engine) -> dict[str, int]:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return {t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in TABLES}


def test_upgrade_from_first_version_keeps_all_data(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "mamoney.db")
    init_db(engine, revision="0001")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO asset (id, name, type, is_liability, currency, liquidity, archived,"
                " created_at) VALUES (1, 'Banco', 'bank', 0, 'MXN', 'immediate', 0, '2026-01-01')"
            )
        )
        for day in range(1, 11):
            conn.execute(
                text("INSERT INTO assetvaluation (asset_id, date, value) VALUES (1, :d, :v)"),
                {"d": f"2026-01-{day:02d}", "v": 1000 * day},
            )
        conn.execute(
            text(
                "INSERT INTO incomesource (id, name, type, is_passive, currency, frequency,"
                " expected_amount, asset_id, active, created_at) VALUES (1, 'Renta', 'rent', 1,"
                " 'MXN', 'monthly', 100, 1, 1, '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO incomeentry (source_id, date, gross_amount, tax_withheld)"
                " VALUES (1, '2026-01-05', 100, 0)"
            )
        )
    before = _counts(engine)

    init_db(engine)  # hasta la última versión

    assert _counts(engine) == before
    with engine.connect() as conn:
        assert conn.execute(text("SELECT tracks_positions FROM asset")).scalar_one() == 0
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    engine.dispose()
