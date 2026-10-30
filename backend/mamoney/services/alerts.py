"""Alertas: pagos por vencer o vencidos, presupuesto excedido y metas atrasadas."""

import datetime as dt
from typing import Any

from sqlmodel import Session, col, select

from mamoney.models import Budget, Goal
from mamoney.services import analytics as an
from mamoney.settings_store import get_setting, set_setting

CATEGORY_LABELS = {
    "groceries": "Súper",
    "restaurants": "Restaurantes",
    "transport": "Transporte",
    "shopping": "Compras",
    "entertainment": "Entretenimiento",
    "health": "Salud",
    "home": "Hogar",
    "travel": "Viajes",
    "education": "Educación",
    "personal": "Cuidado personal",
    "gifts": "Regalos",
    "services": "Servicios",
    "other": "Otros",
}


def build_alerts(session: Session, today: dt.date | None = None) -> list[dict[str, Any]]:
    snap = an.Snapshot.load(session, today)
    days = int(get_setting(session, "alert_days") or 3)
    alerts: list[dict[str, Any]] = []

    # Vencidos solo de la última semana: si no marcas pagos, no se acumulan avisos viejos.
    for item in an.upcoming_payments(snap, days=days, past_days=7):
        if item["status"] == "paid":
            continue
        due = dt.date.fromisoformat(str(item["due_date"]))
        overdue = item["status"] == "overdue"
        when = (
            f"venció el {due:%d/%m}"
            if overdue
            else ("vence hoy" if due == snap.today else f"vence el {due:%d/%m}")
        )
        alerts.append(
            {
                "key": f"pay:{item['expense_id']}:{due.isoformat()}",
                "kind": "payment",
                "severity": "critical" if overdue else "warning",
                "title": f"{item['name']} {when}",
                "detail": f"{item['amount']:,.2f} {item['currency']}",
                "link": "/gastos",
            }
        )

    limits = {str(b.category): b.monthly_limit for b in session.exec(select(Budget)).all()}
    report = an.budget_report(snap, limits, snap.today.year, snap.today.month)
    for row in report["categories"]:
        if row["status"] not in {"over", "warning"}:
            continue
        name = CATEGORY_LABELS.get(str(row["category"]), str(row["category"]))
        over = row["status"] == "over"
        alerts.append(
            {
                "key": f"budget:{row['category']}:{report['month']}:{row['status']}",
                "kind": "budget",
                "severity": "critical" if over else "warning",
                "title": (
                    f"Presupuesto de {name} excedido"
                    if over
                    else f"Presupuesto de {name} al {row['used_pct']:.0f} %"
                ),
                "detail": f"{row['spent']:,.2f} de {row['limit']:,.2f} MXN"
                + ("" if over else f"; al ritmo actual cerrarías en {row['projected']:,.0f}"),
                "link": "/gastos?tab=variables",
            }
        )

    savings = float(an.summary(snap)["free_cash_flow"])
    for goal in session.exec(select(Goal).where(col(Goal.archived).is_(False))).all():
        progress = an.goal_progress(snap, goal, savings)
        detail = f"Llevas {progress['pct']:.0f} %; faltan {progress['remaining']:,.0f} MXN"
        if progress["status"] in {"overdue", "behind"}:
            alerts.append(
                {
                    "key": f"goal:{goal.id}:{progress['status']}:{snap.today:%Y-%m}",
                    "kind": "goal",
                    "severity": "warning",
                    "title": (
                        f"La meta «{goal.name}» pasó su fecha"
                        if progress["status"] == "overdue"
                        else f"La meta «{goal.name}» va atrasada"
                    ),
                    "detail": detail,
                    "link": "/analisis",
                }
            )

    severity = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: (severity[a["severity"]], a["kind"]))
    return alerts


def take_new_alerts(session: Session, today: dt.date | None = None) -> list[dict[str, Any]]:
    """Alertas que aún no se notificaron en la bandeja (cada una se avisa una sola vez)."""
    today = today or dt.date.today()
    if not get_setting(session, "alerts_enabled"):
        return []
    notified: dict[str, str] = get_setting(session, "notified_alerts") or {}
    cutoff = (today - dt.timedelta(days=60)).isoformat()
    notified = {k: v for k, v in notified.items() if v >= cutoff}
    fresh = [a for a in build_alerts(session, today) if a["key"] not in notified]
    for alert in fresh:
        notified[alert["key"]] = today.isoformat()
    set_setting(session, "notified_alerts", notified)
    return fresh
