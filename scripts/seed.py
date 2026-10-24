"""Carga datos de ejemplo en una instancia de Mamoney en ejecución.

Uso:
    MAMONEY_DATA_DIR=./.demo-data uv run mamoney-server   # en otra terminal
    uv run python scripts/seed.py --url http://127.0.0.1:8765
"""

import argparse
import random
from datetime import date

import httpx


def months_back(n: int) -> list[date]:
    today = date.today()
    out = []
    for i in range(n, -1, -1):
        total = today.year * 12 + today.month - 1 - i
        out.append(date(total // 12, total % 12 + 1, 1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    random.seed(7)
    c = httpx.Client(base_url=args.url, timeout=30)

    def post(path: str, body: dict) -> dict:
        r = c.post(path, json=body)
        r.raise_for_status()
        return r.json()

    post("/api/fx/rates", {"currency": "USD", "date": "2025-01-01", "rate_to_base": 20.1})
    post(
        "/api/fx/rates", {"currency": "USD", "date": date.today().isoformat(), "rate_to_base": 18.6}
    )
    post(
        "/api/fx/rates",
        {"currency": "BTC", "date": date.today().isoformat(), "rate_to_base": 1_950_000},
    )

    months = months_back(18)
    assets = {
        "nomina": post("/api/assets", {"name": "Nómina", "type": "bank", "institution": "BBVA"}),
        "cetes": post(
            "/api/assets", {"name": "CETES Directo", "type": "investment", "liquidity": "short"}
        ),
        "broker": post(
            "/api/assets",
            {
                "name": "ETFs (VOO)",
                "type": "investment",
                "currency": "USD",
                "liquidity": "short",
                "institution": "GBM",
            },
        ),
        "afore": post(
            "/api/assets", {"name": "AFORE", "type": "retirement", "liquidity": "illiquid"}
        ),
        "depa": post(
            "/api/assets", {"name": "Depa Narvarte", "type": "real_estate", "liquidity": "illiquid"}
        ),
        "auto": post("/api/assets", {"name": "Auto", "type": "vehicle", "liquidity": "long"}),
        "btc": post(
            "/api/assets",
            {"name": "Bitcoin", "type": "crypto", "currency": "BTC", "liquidity": "short"},
        ),
        "hipoteca": post(
            "/api/assets", {"name": "Hipoteca Depa", "type": "mortgage", "is_liability": True}
        ),
        "tdc": post(
            "/api/assets", {"name": "Tarjeta Oro", "type": "credit_card", "is_liability": True}
        ),
    }
    for i, m in enumerate(months):
        values = {
            "nomina": 60_000 + i * 2_500 + random.randint(-8_000, 8_000),
            "cetes": 150_000 * (1.009**i) + i * 5_000,
            "broker": 8_000 * (1.01**i) + i * 300,
            "afore": 420_000 * (1.006**i),
            "depa": 2_800_000 * (1.004**i),
            "auto": 320_000 * (0.988**i),
            "btc": 0.05 + i * 0.002,
            "hipoteca": 1_900_000 - i * 9_000,
            "tdc": random.randint(5_000, 22_000),
        }
        for key, value in values.items():
            post(
                f"/api/assets/{assets[key]['id']}/valuations",
                {"date": m.isoformat(), "value": round(value, 4)},
            )

    salary = post(
        "/api/income/sources",
        {"name": "Sueldo", "type": "salary", "expected_amount": 42_000, "frequency": "biweekly"},
    )
    freelance = post(
        "/api/income/sources",
        {"name": "Consultoría", "type": "freelance", "expected_amount": 15_000},
    )
    rent = post(
        "/api/income/sources",
        {
            "name": "Renta Depa",
            "type": "rent",
            "is_passive": True,
            "expected_amount": 16_500,
            "asset_id": assets["depa"]["id"],
        },
    )
    divs = post(
        "/api/income/sources",
        {
            "name": "Dividendos VOO",
            "type": "dividends",
            "is_passive": True,
            "currency": "USD",
            "frequency": "quarterly",
            "expected_amount": 60,
            "asset_id": assets["broker"]["id"],
        },
    )
    interest = post(
        "/api/income/sources",
        {
            "name": "Intereses CETES",
            "type": "interest",
            "is_passive": True,
            "expected_amount": 1_300,
            "asset_id": assets["cetes"]["id"],
        },
    )
    for i, m in enumerate(months):
        for day in (15, 28):
            post(
                f"/api/income/sources/{salary['id']}/entries",
                {
                    "date": m.replace(day=day).isoformat(),
                    "gross_amount": 42_000,
                    "tax_withheld": 7_900,
                },
            )
        if random.random() > 0.35:
            post(
                f"/api/income/sources/{freelance['id']}/entries",
                {
                    "date": m.replace(day=20).isoformat(),
                    "gross_amount": random.randint(9_000, 26_000),
                    "tax_withheld": 1_500,
                },
            )
        post(
            f"/api/income/sources/{rent['id']}/entries",
            {"date": m.replace(day=5).isoformat(), "gross_amount": 16_500, "tax_withheld": 1_650},
        )
        post(
            f"/api/income/sources/{interest['id']}/entries",
            {"date": m.replace(day=27).isoformat(), "gross_amount": 1_100 + i * 40},
        )
        if m.month in (3, 6, 9, 12):
            post(
                f"/api/income/sources/{divs['id']}/entries",
                {"date": m.replace(day=25).isoformat(), "gross_amount": 55 + i, "tax_withheld": 5},
            )

    start = months[0].isoformat()
    expenses = [
        ("Hipoteca", "housing", 21_500, "monthly", 10, "MXN"),
        ("Mantenimiento", "housing", 1_800, "monthly", 5, "MXN"),
        ("Luz CFE", "utilities", 1_150, "bimonthly", 18, "MXN"),
        ("Internet y móvil", "utilities", 949, "monthly", 12, "MXN"),
        ("Gas", "utilities", 650, "monthly", 22, "MXN"),
        ("Seguro de auto", "insurance", 14_800, "annual", 3, "MXN"),
        ("Gastos médicos mayores", "insurance", 2_300, "monthly", 1, "MXN"),
        ("Netflix + Spotify", "subscriptions", 22, "monthly", 8, "USD"),
        ("Gimnasio", "health", 890, "monthly", 1, "MXN"),
        ("Colegiatura", "education", 6_500, "monthly", 7, "MXN"),
        ("Predial", "taxes", 4_200, "annual", 31, "MXN"),
    ]
    created = []
    for name, cat, amount, freq, day, cur in expenses:
        created.append(
            post(
                "/api/expenses",
                {
                    "name": name,
                    "category": cat,
                    "amount": amount,
                    "frequency": freq,
                    "due_day": day,
                    "start_date": start,
                    "currency": cur,
                },
            )
        )
    for item in c.get("/api/analytics/upcoming", params={"days": 3}).json():
        if item["status"] != "pending" and item["name"] in {"Gimnasio", "Gastos médicos mayores"}:
            post(
                "/api/expenses/payments",
                {
                    "expense_id": item["expense_id"],
                    "due_date": item["due_date"],
                    "paid_date": item["due_date"],
                    "amount": item["amount"],
                },
            )
    print("Datos de ejemplo cargados.")


if __name__ == "__main__":
    main()
