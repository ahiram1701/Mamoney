from datetime import date

import pytest

from mamoney.models import Frequency
from mamoney.services.scheduling import last_n_months, monthly_amount, occurrences


@pytest.mark.parametrize(
    ("frequency", "expected"),
    [
        (Frequency.monthly, 1200),
        (Frequency.annual, 100),
        (Frequency.bimonthly, 600),
        (Frequency.biweekly, 2400),
        (Frequency.weekly, 1200 * 52 / 12),
        (Frequency.once, 0),
    ],
)
def test_monthly_amount(frequency: Frequency, expected: float) -> None:
    assert monthly_amount(1200, frequency) == pytest.approx(expected)


def test_monthly_clamps_to_month_end() -> None:
    dates = list(
        occurrences(Frequency.monthly, date(2026, 1, 1), 31, date(2026, 1, 1), date(2026, 4, 30))
    )
    assert dates == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_bimonthly_keeps_alignment_with_start() -> None:
    dates = list(
        occurrences(Frequency.bimonthly, date(2025, 1, 10), 10, date(2026, 1, 1), date(2026, 6, 30))
    )
    assert dates == [date(2026, 1, 10), date(2026, 3, 10), date(2026, 5, 10)]


def test_first_due_after_start_date() -> None:
    dates = list(
        occurrences(Frequency.monthly, date(2026, 3, 20), 5, date(2026, 3, 1), date(2026, 5, 31))
    )
    assert dates == [date(2026, 4, 5), date(2026, 5, 5)]


def test_end_date_stops_occurrences() -> None:
    dates = list(
        occurrences(
            Frequency.monthly,
            date(2026, 1, 1),
            1,
            date(2026, 1, 1),
            date(2026, 12, 31),
            end=date(2026, 3, 15),
        )
    )
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_weekly_and_biweekly() -> None:
    weekly = list(
        occurrences(Frequency.weekly, date(2026, 1, 2), 1, date(2026, 1, 10), date(2026, 1, 31))
    )
    assert weekly == [date(2026, 1, 16), date(2026, 1, 23), date(2026, 1, 30)]
    biweekly = list(
        occurrences(Frequency.biweekly, date(2026, 1, 1), 1, date(2026, 2, 1), date(2026, 3, 20))
    )
    assert biweekly == [date(2026, 2, 15), date(2026, 2, 28), date(2026, 3, 15)]


def test_once() -> None:
    window = (date(2026, 1, 1), date(2026, 12, 31))
    assert list(occurrences(Frequency.once, date(2026, 5, 5), 1, *window)) == [date(2026, 5, 5)]
    assert list(occurrences(Frequency.once, date(2025, 5, 5), 1, *window)) == []


def test_last_n_months_crosses_year() -> None:
    assert last_n_months(date(2026, 2, 10), 3) == [(2025, 12), (2026, 1), (2026, 2)]
