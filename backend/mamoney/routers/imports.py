import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import col, select

from mamoney.models import Asset, IncomeEntry, IncomeSource, Spending, SpendingCategory
from mamoney.routers.common import SessionDep, get_or_404
from mamoney.services import importer

router = APIRouter(prefix="/api/import", tags=["importación"])

MAX_BYTES = 5 * 1024 * 1024
INCOME_NOTE = "import:"


def _known_keys(session: SessionDep) -> set[str]:
    keys = set(
        session.exec(select(Spending.import_key).where(col(Spending.import_key).is_not(None))).all()
    )
    notes = session.exec(
        select(IncomeEntry.notes).where(col(IncomeEntry.notes).startswith(INCOME_NOTE))
    ).all()
    keys.update(n.removeprefix(INCOME_NOTE) for n in notes if n)
    return {k for k in keys if k}


@router.post("/preview")
async def preview(
    session: SessionDep,
    file: UploadFile = File(...),
    asset_id: int | None = Form(None),
    invert: bool = Form(False),
) -> dict[str, Any]:
    """Lee el archivo y propone qué hacer con cada movimiento; no guarda nada."""
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "El archivo supera 5 MB")
    if asset_id is not None:
        get_or_404(session, Asset, asset_id)
    try:
        rows = importer.parse_statement(content, file.filename or "")
    except importer.ImportError_ as exc:
        raise HTTPException(422, str(exc)) from exc

    learned = importer.learned_categories(
        [
            (s.description, s.category)
            for s in session.exec(select(Spending).order_by(col(Spending.id)))
        ]
    )
    known = _known_keys(session)
    result = []
    for row in rows:
        if invert:  # tarjetas de crédito: los cargos vienen positivos
            row.amount = -row.amount
        row.key = importer.row_key(row, asset_id)
        expense = row.amount < 0
        result.append(
            {
                **row.to_dict(),
                "kind": "expense" if expense else "income",
                "category": importer.suggest_category(row.description, learned)
                if expense
                else None,
                "duplicate": row.key in known,
            }
        )
    result.sort(key=lambda r: r["date"], reverse=True)
    return {
        "rows": result,
        "count": len(result),
        "duplicates": sum(r["duplicate"] for r in result),
        "expenses": sum(-r["amount"] for r in result if r["amount"] < 0),
        "income": sum(r["amount"] for r in result if r["amount"] > 0),
    }


class CommitRow(BaseModel):
    key: str = Field(min_length=8, max_length=64)
    date: dt.date
    description: str = Field(min_length=1, max_length=200)
    amount: float
    kind: Literal["expense", "income", "skip"]
    category: SpendingCategory | None = None
    income_source_id: int | None = None


class CommitRequest(BaseModel):
    asset_id: int | None = None
    currency: str = Field(default="MXN", min_length=3, max_length=8)
    rows: list[CommitRow]


@router.post("/commit")
def commit(data: CommitRequest, session: SessionDep) -> dict[str, int]:
    """Guarda los movimientos elegidos; los ya importados antes se omiten."""
    known = _known_keys(session)
    counts = {"expenses": 0, "income": 0, "skipped": 0, "duplicates": 0}
    for row in data.rows:
        if row.kind == "skip":
            counts["skipped"] += 1
            continue
        if row.key in known:
            counts["duplicates"] += 1
            continue
        if row.kind == "expense":
            session.add(
                Spending(
                    date=row.date,
                    amount=abs(row.amount),
                    currency=data.currency.upper(),
                    category=row.category or SpendingCategory.other,
                    description=row.description[:200],
                    payment_asset_id=data.asset_id,
                    source="import",
                    import_key=row.key,
                )
            )
            counts["expenses"] += 1
        else:
            if row.income_source_id is None:
                raise HTTPException(422, f"Elige la fuente de ingreso para «{row.description}»")
            get_or_404(session, IncomeSource, row.income_source_id)
            session.add(
                IncomeEntry(
                    source_id=row.income_source_id,
                    date=row.date,
                    gross_amount=abs(row.amount),
                    notes=f"{INCOME_NOTE}{row.key}",
                )
            )
            counts["income"] += 1
        known.add(row.key)
    session.commit()
    return counts
