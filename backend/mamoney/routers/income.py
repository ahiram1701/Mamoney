import datetime as dt

from fastapi import APIRouter
from sqlmodel import select

from mamoney.models import IncomeEntry, IncomeEntryBase, IncomeSource, IncomeSourceBase
from mamoney.routers.common import SessionDep, apply_update, get_or_404, save
from mamoney.schemas import (
    IncomeEntryCreate,
    IncomeEntryRead,
    IncomeEntryUpdate,
    IncomeSourceCreate,
    IncomeSourceRead,
    IncomeSourceUpdate,
)

router = APIRouter(prefix="/api/income", tags=["ingresos"])


def _entry_out(entry: IncomeEntry) -> IncomeEntryRead:
    return IncomeEntryRead(**entry.model_dump(), net_amount=entry.net_amount)


@router.get("/sources", response_model=list[IncomeSourceRead])
def list_sources(session: SessionDep) -> list[IncomeSource]:
    return list(session.exec(select(IncomeSource).order_by(IncomeSource.name)).all())


@router.post("/sources", response_model=IncomeSourceRead, status_code=201)
def create_source(data: IncomeSourceCreate, session: SessionDep) -> IncomeSource:
    return save(session, IncomeSource.model_validate(data.model_dump()))


@router.patch("/sources/{source_id}", response_model=IncomeSourceRead)
def update_source(source_id: int, data: IncomeSourceUpdate, session: SessionDep) -> IncomeSource:
    source = get_or_404(session, IncomeSource, source_id)
    return save(session, apply_update(source, data, IncomeSourceBase))


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, IncomeSource, source_id))
    session.commit()


@router.get("/entries", response_model=list[IncomeEntryRead])
def list_entries(
    session: SessionDep,
    source_id: int | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
) -> list[IncomeEntryRead]:
    query = select(IncomeEntry)
    if source_id is not None:
        query = query.where(IncomeEntry.source_id == source_id)
    if since:
        query = query.where(IncomeEntry.date >= since)
    if until:
        query = query.where(IncomeEntry.date <= until)
    entries = session.exec(query.order_by(IncomeEntry.date.desc())).all()  # type: ignore[attr-defined]
    return [_entry_out(e) for e in entries]


@router.post("/sources/{source_id}/entries", response_model=IncomeEntryRead, status_code=201)
def add_entry(source_id: int, data: IncomeEntryCreate, session: SessionDep) -> IncomeEntryRead:
    get_or_404(session, IncomeSource, source_id)
    entry = save(session, IncomeEntry(source_id=source_id, **data.model_dump()))
    return _entry_out(entry)


@router.patch("/entries/{entry_id}", response_model=IncomeEntryRead)
def update_entry(entry_id: int, data: IncomeEntryUpdate, session: SessionDep) -> IncomeEntryRead:
    entry = get_or_404(session, IncomeEntry, entry_id)
    return _entry_out(save(session, apply_update(entry, data, IncomeEntryBase)))


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, IncomeEntry, entry_id))
    session.commit()
