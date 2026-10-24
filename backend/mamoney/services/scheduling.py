"""Recurrencias: mensualización de frecuencias y cálculo de vencimientos."""

import calendar
from collections.abc import Iterator
from datetime import date, timedelta

from mamoney.models import Frequency

MONTHLY_FACTOR: dict[Frequency, float] = {
    Frequency.once: 0.0,
    Frequency.weekly: 52 / 12,
    Frequency.biweekly: 2.0,
    Frequency.monthly: 1.0,
    Frequency.bimonthly: 1 / 2,
    Frequency.quarterly: 1 / 3,
    Frequency.semiannual: 1 / 6,
    Frequency.annual: 1 / 12,
}

_MONTH_STEP: dict[Frequency, int] = {
    Frequency.monthly: 1,
    Frequency.bimonthly: 2,
    Frequency.quarterly: 3,
    Frequency.semiannual: 6,
    Frequency.annual: 12,
}


def monthly_amount(amount: float, frequency: Frequency) -> float:
    """Equivalente mensual de un monto recurrente."""
    return amount * MONTHLY_FACTOR[frequency]


def add_months(year: int, month: int, months: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + months
    return total // 12, total % 12 + 1


def clamp_day(year: int, month: int, day: int) -> date:
    """Fecha con el día ajustado al último del mes (p. ej. día 31 en febrero)."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def occurrences(
    frequency: Frequency,
    start: date,
    due_day: int,
    window_start: date,
    window_end: date,
    end: date | None = None,
) -> Iterator[date]:
    """Fechas de vencimiento dentro de [window_start, window_end] (inclusive)."""
    last = min(window_end, end) if end else window_end
    if last < window_start:
        return

    if frequency == Frequency.once:
        if window_start <= start <= last:
            yield start
        return

    if frequency == Frequency.weekly:
        current = start
        if current < window_start:
            skip = (window_start - current).days // 7
            current += timedelta(weeks=skip)
        while current <= last:
            if current >= window_start:
                yield current
            current += timedelta(weeks=1)
        return

    if frequency == Frequency.biweekly:
        year, month = window_start.year, window_start.month
        while True:
            for candidate in (clamp_day(year, month, 15), clamp_day(year, month, 31)):
                if candidate > last:
                    return
                if candidate >= window_start and candidate >= start:
                    yield candidate
            year, month = add_months(year, month, 1)

    step = _MONTH_STEP[frequency]
    year, month = start.year, start.month
    first = clamp_day(year, month, due_day)
    if first < start:
        year, month = add_months(year, month, step)
    # Avanza directamente hasta cerca de la ventana para no iterar años de historial.
    gap = (window_start.year - year) * 12 + (window_start.month - month)
    if gap > step:
        year, month = add_months(year, month, (gap // step - 1) * step)
    while True:
        candidate = clamp_day(year, month, due_day)
        if candidate > last:
            return
        if candidate >= window_start:
            yield candidate
        year, month = add_months(year, month, step)


def month_range(day: date) -> tuple[date, date]:
    return date(day.year, day.month, 1), clamp_day(day.year, day.month, 31)


def last_n_months(today: date, n: int) -> list[tuple[int, int]]:
    """Lista de (año, mes) desde hace n-1 meses hasta el mes actual."""
    return [add_months(today.year, today.month, -i) for i in range(n - 1, -1, -1)]
