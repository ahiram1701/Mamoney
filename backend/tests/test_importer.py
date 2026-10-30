import datetime as dt

import pytest
from fastapi.testclient import TestClient

from mamoney.models import SpendingCategory
from mamoney.services import importer

BANK_CSV = """Estado de cuenta BBVA
Cuenta: ****1234

Fecha,Concepto,Cargo,Abono,Saldo
02/09/2026,OXXO SUC 123,"$85.50",,"10,000.00"
03/09/2026,PAGO NOMINA EMPRESA,,"$21,000.00","31,000.00"
05/09/2026,UBER *TRIP,"$120.00",,"30,880.00"
,Total,"$205.50","$21,000.00",
"""

EU_CSV = (
    "fecha;descripción;importe\n"
    "2026-09-10;Starbucks Reforma;-95,50\n"
    "2026-09-11;Devolución;1.250,00\n"
)

OFX = """OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260912120000<TRNAMT>-450.00<FITID>1<NAME>CINEPOLIS<MEMO>Boletos
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260915<TRNAMT>3000.00<FITID>2<NAME>TRANSFERENCIA
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_csv_with_debit_and_credit_columns_skips_header_and_totals() -> None:
    rows = importer.parse_csv(BANK_CSV)
    assert [(r.date.isoformat(), r.amount) for r in rows] == [
        ("2026-09-02", -85.5),
        ("2026-09-03", 21000.0),
        ("2026-09-05", -120.0),
    ]


def test_csv_with_semicolons_and_decimal_commas() -> None:
    rows = importer.parse_csv(EU_CSV)
    assert [r.amount for r in rows] == [-95.5, 1250.0]
    assert rows[0].description == "Starbucks Reforma"


def test_ofx() -> None:
    rows = importer.parse_statement(OFX.encode(), "estado.ofx")
    assert [(r.date, r.amount, r.description) for r in rows] == [
        (dt.date(2026, 9, 12), -450.0, "CINEPOLIS Boletos"),
        (dt.date(2026, 9, 15), 3000.0, "TRANSFERENCIA"),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-09-01", dt.date(2026, 9, 1)),
        ("01/09/2026", dt.date(2026, 9, 1)),
        ("01-09-26", dt.date(2026, 9, 1)),
        ("12 ene 2026", dt.date(2026, 1, 12)),
        ("12-DIC-25", dt.date(2025, 12, 12)),
    ],
)
def test_parse_date(text: str, expected: dt.date) -> None:
    assert importer.parse_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", 1234.56),
        ("(500.00)", -500.0),
        ("1.234,56", 1234.56),
        ("75-", -75.0),
        ("", None),
    ],
)
def test_parse_amount(text: str, expected: float | None) -> None:
    assert importer.parse_amount(text) == expected


def test_category_rules_and_learning() -> None:
    assert importer.suggest_category("OXXO SUC 123") == SpendingCategory.groceries
    assert importer.suggest_category("UBER EATS PEDIDO") == SpendingCategory.restaurants
    assert importer.suggest_category("UBER *TRIP") == SpendingCategory.transport
    learned = importer.learned_categories([("Tienda Don Pepe", "groceries")])
    assert importer.suggest_category("TIENDA DON  PEPE", learned) == SpendingCategory.groceries
    assert importer.suggest_category("algo raro") == SpendingCategory.other


def test_unrecognized_csv_has_clear_error() -> None:
    with pytest.raises(importer.ImportError_, match="columnas"):
        importer.parse_csv("a,b,c\n1,2,3\n")


def test_preview_and_commit_skip_duplicates(client: TestClient) -> None:
    source = client.post("/api/income/sources", json={"name": "Sueldo", "type": "salary"}).json()
    files = {"file": ("bbva.csv", BANK_CSV.encode("cp1252"), "text/csv")}
    preview = client.post("/api/import/preview", files=files).json()
    assert preview["count"] == 3 and preview["duplicates"] == 0
    by_desc = {r["description"]: r for r in preview["rows"]}
    assert by_desc["OXXO SUC 123"]["category"] == "groceries"
    assert by_desc["PAGO NOMINA EMPRESA"]["kind"] == "income"

    rows = []
    for row in preview["rows"]:
        if row["kind"] == "income":
            row["income_source_id"] = source["id"]
        rows.append(row)
    result = client.post("/api/import/commit", json={"rows": rows}).json()
    assert result == {"expenses": 2, "income": 1, "skipped": 0, "duplicates": 0}

    # Reimportar el mismo archivo: todo aparece como duplicado y no se guarda dos veces.
    again = client.post("/api/import/preview", files=files).json()
    assert again["duplicates"] == 3
    assert client.post("/api/import/commit", json={"rows": rows}).json()["duplicates"] == 3


def test_income_rows_need_a_source(client: TestClient) -> None:
    row = {
        "key": "k" * 40,
        "date": "2026-09-03",
        "description": "Nómina",
        "amount": 100,
        "kind": "income",
    }
    assert client.post("/api/import/commit", json={"rows": [row]}).status_code == 422


def test_invert_for_credit_cards(client: TestClient) -> None:
    csv = "Fecha,Descripción,Importe\n2026-09-01,AMAZON MX,1500.00\n"
    files = {"file": ("tarjeta.csv", csv.encode(), "text/csv")}
    row = client.post("/api/import/preview", files=files, data={"invert": "true"}).json()["rows"][0]
    assert row["amount"] == -1500 and row["kind"] == "expense" and row["category"] == "shopping"
