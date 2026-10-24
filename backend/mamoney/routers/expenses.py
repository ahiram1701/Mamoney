from fastapi import APIRouter, HTTPException
from sqlmodel import select

from mamoney.models import ExpensePayment, FixedExpense, FixedExpenseBase
from mamoney.routers.common import SessionDep, apply_update, get_or_404, save
from mamoney.schemas import (
    FixedExpenseCreate,
    FixedExpenseRead,
    FixedExpenseUpdate,
    PaymentCreate,
    PaymentRead,
)

router = APIRouter(prefix="/api/expenses", tags=["gastos fijos"])


@router.get("", response_model=list[FixedExpenseRead])
def list_expenses(session: SessionDep) -> list[FixedExpense]:
    return list(session.exec(select(FixedExpense).order_by(FixedExpense.name)).all())


@router.post("", response_model=FixedExpenseRead, status_code=201)
def create_expense(data: FixedExpenseCreate, session: SessionDep) -> FixedExpense:
    return save(session, FixedExpense.model_validate(data.model_dump()))


@router.patch("/{expense_id}", response_model=FixedExpenseRead)
def update_expense(expense_id: int, data: FixedExpenseUpdate, session: SessionDep) -> FixedExpense:
    expense = get_or_404(session, FixedExpense, expense_id)
    return save(session, apply_update(expense, data, FixedExpenseBase))


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, FixedExpense, expense_id))
    session.commit()


@router.get("/{expense_id}/payments", response_model=list[PaymentRead])
def list_payments(expense_id: int, session: SessionDep) -> list[ExpensePayment]:
    get_or_404(session, FixedExpense, expense_id)
    query = (
        select(ExpensePayment)
        .where(ExpensePayment.expense_id == expense_id)
        .order_by(ExpensePayment.due_date.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(query).all())


@router.post("/payments", response_model=PaymentRead, status_code=201)
def mark_paid(data: PaymentCreate, session: SessionDep) -> ExpensePayment:
    get_or_404(session, FixedExpense, data.expense_id)
    duplicate = session.exec(
        select(ExpensePayment).where(
            ExpensePayment.expense_id == data.expense_id,
            ExpensePayment.due_date == data.due_date,
        )
    ).first()
    if duplicate:
        raise HTTPException(409, "Ese vencimiento ya está marcado como pagado")
    return save(session, ExpensePayment.model_validate(data.model_dump()))


@router.delete("/payments/{payment_id}", status_code=204)
def unmark_paid(payment_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, ExpensePayment, payment_id))
    session.commit()
