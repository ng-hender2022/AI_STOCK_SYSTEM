"""
Label Builder
Tính labels (UP / DOWN / NEUTRAL) cho training data.

Uses trading calendar for T+1/T+5/T+10/T+20 (trading days, not calendar days).
Enforces DATA_LEAKAGE_PREVENTION: feature_date < label_available_date.

Labels:
    UP      : return >= +0.5%
    DOWN    : return <= -0.5%
    NEUTRAL : -0.5% < return < +0.5%
"""

import sqlite3
from pathlib import Path

try:
    from .calendar_builder import CalendarBuilder
except ImportError:
    from calendar_builder import CalendarBuilder

# Thresholds
LABEL_UP_THRESHOLD = 0.005      # +0.5%
LABEL_DOWN_THRESHOLD = -0.005   # -0.5%

HORIZONS = [1, 5, 10, 20]


class LabelBuilder:
    """
    Build return labels using trading calendar.

    Usage:
        lb = LabelBuilder("D:/AI/AI_data/market.db")
        labels = lb.compute_labels("FPT", "2026-03-10")
        batch = lb.compute_labels_range("FPT", "2026-01-01", "2026-03-10")
    """

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)
        self.calendar = CalendarBuilder(market_db)
        self._ftd_cache: dict[str, str | None] = {}

    def _get_first_trading_date(
        self, conn: sqlite3.Connection, symbol: str
    ) -> str | None:
        """Get first_trading_date for symbol from symbols_master."""
        if symbol in self._ftd_cache:
            return self._ftd_cache[symbol]

        # Check if column exists
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" not in cols:
            self._ftd_cache[symbol] = None
            return None

        row = conn.execute(
            "SELECT first_trading_date FROM symbols_master WHERE symbol=?",
            (symbol,),
        ).fetchone()
        ftd = row["first_trading_date"] if row else None
        self._ftd_cache[symbol] = ftd
        return ftd

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_close(self, conn: sqlite3.Connection, symbol: str, d: str) -> float | None:
        """Get close price for symbol on date d."""
        row = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol=? AND date=?",
            (symbol, d),
        ).fetchone()
        return float(row["close"]) if row else None

    def compute_labels(
        self,
        symbol: str,
        feature_date: str,
        check_leak: bool = True,
    ) -> dict | None:
        """
        Compute labels for a single symbol on feature_date.

        Labels use trading-day offsets (not calendar days).
        Only attaches label if label_available_date <= today's max data date.

        Args:
            symbol: stock symbol
            feature_date: the date T
            check_leak: if True, verify no leakage

        Returns:
            dict with keys: feature_date, symbol, close_t,
                            t{N}_date, t{N}_close, t{N}_return, t{N}_label
                            for N in [1, 5, 10, 20]
            or None if insufficient data
        """
        conn = self._connect()
        try:
            # Check first_trading_date — no labels before listing
            ftd = self._get_first_trading_date(conn, symbol)
            if ftd and feature_date < ftd:
                return None  # symbol not yet listed on this date

            close_t = self._get_close(conn, symbol, feature_date)
            if close_t is None or close_t <= 0:
                return None

            result = {
                "feature_date": feature_date,
                "symbol": symbol,
                "close_t": close_t,
            }

            for h in HORIZONS:
                label_date = self.calendar.offset_trading_day(feature_date, h)
                result[f"t{h}_date"] = label_date
                result[f"t{h}_close"] = None
                result[f"t{h}_return"] = None
                result[f"t{h}_label"] = None

                if label_date is None:
                    continue

                # LEAKAGE CHECK: feature_date must be < label_date
                if check_leak and feature_date >= label_date:
                    raise LeakageError(
                        f"Leakage: feature_date={feature_date} >= "
                        f"label_date(t{h})={label_date}"
                    )

                future_close = self._get_close(conn, symbol, label_date)
                if future_close is None:
                    continue

                ret = (future_close - close_t) / close_t
                label = _classify_return(ret)

                result[f"t{h}_close"] = future_close
                result[f"t{h}_return"] = round(ret, 6)
                result[f"t{h}_label"] = label

            return result
        finally:
            conn.close()

    def compute_labels_range(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Compute labels for a date range."""
        trading_dates = self.calendar.get_trading_dates(start_date, end_date)
        results = []
        for d in trading_dates:
            row = self.compute_labels(symbol, d, check_leak=True)
            if row:
                results.append(row)
        return results


def _classify_return(ret: float) -> str:
    """Classify return into UP / DOWN / NEUTRAL."""
    if ret >= LABEL_UP_THRESHOLD:
        return "UP"
    elif ret <= LABEL_DOWN_THRESHOLD:
        return "DOWN"
    else:
        return "NEUTRAL"


class LeakageError(Exception):
    """Raised when data leakage is detected in label building."""
    pass
