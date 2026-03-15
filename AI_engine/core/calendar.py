"""
AI_STOCK Vietnam Market Calendar
Quản lý ngày giao dịch, ngày nghỉ lễ HOSE/HNX.
"""

from datetime import date, timedelta
from typing import Optional


# Ngày nghỉ lễ cố định (tháng, ngày) — áp dụng mọi năm
FIXED_HOLIDAYS_VN = [
    (1, 1),     # Tết Dương lịch
    (4, 30),    # Giải phóng miền Nam
    (5, 1),     # Quốc tế Lao động
    (9, 2),     # Quốc khánh
]

# Ngày nghỉ Tết Nguyên đán (cần cập nhật hàng năm)
# Format: (year, [(month, day), ...])
TET_HOLIDAYS = {
    2025: [(1, d) for d in range(27, 32)] + [(2, d) for d in range(1, 4)],
    2026: [(2, d) for d in range(14, 22)],
    2027: [(2, d) for d in range(3, 11)],
}

# Ngày nghỉ bù và nghỉ đặc biệt (cập nhật khi có thông báo)
SPECIAL_HOLIDAYS = {
    2026: [
        (1, 2),     # Nghỉ bù Tết Dương lịch
        (4, 29),    # Nghỉ bù 30/4
        (9, 3),     # Nghỉ bù Quốc khánh
    ],
}


class VNMarketCalendar:
    """
    Vietnam stock market calendar.

    Usage:
        cal = VNMarketCalendar()
        cal.is_trading_day(date(2026, 3, 15))    # True/False
        cal.next_trading_day(date(2026, 3, 13))   # date(2026, 3, 16)
        cal.prev_trading_day(date(2026, 3, 16))   # date(2026, 3, 13)
        cal.trading_days_between(start, end)       # list of dates
    """

    def __init__(self):
        self._holiday_cache: dict[int, set[date]] = {}

    def _build_holidays_for_year(self, year: int) -> set[date]:
        """Build set of holidays for a given year."""
        if year in self._holiday_cache:
            return self._holiday_cache[year]

        holidays = set()

        # Fixed holidays
        for month, day in FIXED_HOLIDAYS_VN:
            try:
                holidays.add(date(year, month, day))
            except ValueError:
                pass

        # Tet holidays
        if year in TET_HOLIDAYS:
            for month, day in TET_HOLIDAYS[year]:
                try:
                    holidays.add(date(year, month, day))
                except ValueError:
                    pass

        # Special holidays
        if year in SPECIAL_HOLIDAYS:
            for month, day in SPECIAL_HOLIDAYS[year]:
                try:
                    holidays.add(date(year, month, day))
                except ValueError:
                    pass

        self._holiday_cache[year] = holidays
        return holidays

    def is_holiday(self, d: date) -> bool:
        """Check if date is a VN market holiday."""
        holidays = self._build_holidays_for_year(d.year)
        return d in holidays

    def is_weekend(self, d: date) -> bool:
        """Check if date is Saturday or Sunday."""
        return d.weekday() >= 5

    def is_trading_day(self, d: date) -> bool:
        """Check if date is a trading day (not weekend, not holiday)."""
        return not self.is_weekend(d) and not self.is_holiday(d)

    def next_trading_day(self, d: date) -> date:
        """Get next trading day after d (exclusive)."""
        current = d + timedelta(days=1)
        while not self.is_trading_day(current):
            current += timedelta(days=1)
        return current

    def prev_trading_day(self, d: date) -> date:
        """Get previous trading day before d (exclusive)."""
        current = d - timedelta(days=1)
        while not self.is_trading_day(current):
            current -= timedelta(days=1)
        return current

    def trading_days_between(
        self, start: date, end: date, inclusive: bool = True
    ) -> list[date]:
        """
        List trading days between start and end.

        Args:
            start: Start date
            end: End date
            inclusive: Include start and end if they are trading days
        """
        result = []
        current = start if inclusive else start + timedelta(days=1)
        end_date = end if inclusive else end - timedelta(days=1)

        while current <= end_date:
            if self.is_trading_day(current):
                result.append(current)
            current += timedelta(days=1)
        return result

    def count_trading_days(self, start: date, end: date) -> int:
        """Count trading days between start and end (inclusive)."""
        return len(self.trading_days_between(start, end))

    def offset_trading_days(self, d: date, offset: int) -> date:
        """
        Move forward/backward by N trading days.

        Args:
            d: Starting date
            offset: +N for forward, -N for backward
        """
        if offset == 0:
            return d

        step = 1 if offset > 0 else -1
        remaining = abs(offset)
        current = d

        while remaining > 0:
            current += timedelta(days=step)
            if self.is_trading_day(current):
                remaining -= 1

        return current
