from typing import Annotated, TypeVar

from fastapi import Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlmodel import Session, SQLModel

from mamoney.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]

T = TypeVar("T", bound=SQLModel)


def get_or_404[T: SQLModel](session: Session, model: type[T], obj_id: int) -> T:
    obj = session.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {obj_id} no existe")
    return obj


def apply_update[T: SQLModel](obj: T, changes: BaseModel, validator: type[SQLModel]) -> T:
    """Aplica un PATCH y revalida el resultado con las reglas del modelo base."""
    data = obj.model_dump()
    data.update(changes.model_dump(exclude_unset=True))
    try:
        validated = validator.model_validate(data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    for key, value in validated.model_dump().items():
        setattr(obj, key, value)
    return obj


def save[T: SQLModel](session: Session, obj: T) -> T:
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
