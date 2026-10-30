from typing import Any

from fastapi import APIRouter
from sqlmodel import col, select

from mamoney.models import Asset, Goal, GoalBase
from mamoney.routers.common import SessionDep, apply_update, get_or_404, save
from mamoney.schemas import partial
from mamoney.services import analytics as an

router = APIRouter(prefix="/api/goals", tags=["metas"])

GoalUpdate = partial(GoalBase, "GoalUpdate")


class GoalCreate(GoalBase):
    pass


def goals_report(session: SessionDep, include_archived: bool = False) -> list[dict[str, Any]]:
    snap = an.Snapshot.load(session)
    savings = float(an.summary(snap)["free_cash_flow"])
    query = select(Goal).order_by(
        col(Goal.target_date).is_(None), col(Goal.target_date), col(Goal.id)
    )
    if not include_archived:
        query = query.where(col(Goal.archived).is_(False))
    return [an.goal_progress(snap, g, savings) for g in session.exec(query).all()]


@router.get("")
def list_goals(session: SessionDep, include_archived: bool = False) -> list[dict[str, Any]]:
    return goals_report(session, include_archived)


@router.post("", status_code=201)
def create_goal(data: GoalCreate, session: SessionDep) -> Goal:
    if data.asset_id is not None:
        get_or_404(session, Asset, data.asset_id)
    return save(session, Goal.model_validate(data.model_dump()))


@router.patch("/{goal_id}")
def update_goal(goal_id: int, data: GoalUpdate, session: SessionDep) -> Goal:  # type: ignore[valid-type]
    return save(session, apply_update(get_or_404(session, Goal, goal_id), data, GoalBase))


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: SessionDep) -> None:
    session.delete(get_or_404(session, Goal, goal_id))
    session.commit()
