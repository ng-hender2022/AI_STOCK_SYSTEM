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


class LabelWriter:
    """
    Batch compute labels for all symbols and write to signals.db → training_labels.

    Usage:
        writer = LabelWriter("D:/AI/AI_data/market.db", "D:/AI/AI_data/signals.db")
        stats = writer.build_all()
    """

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.label_builder = LabelBuilder(market_db)

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_labels (
                symbol          TEXT NOT NULL,
                feature_date    DATE NOT NULL,
                close_t         REAL,
                t1_date         DATE,
                t1_return       REAL,
                t1_label        TEXT,
                t5_date         DATE,
                t5_return       REAL,
                t5_label        TEXT,
                t10_date        DATE,
                t10_return      REAL,
                t10_label       TEXT,
                t20_date        DATE,
                t20_return      REAL,
                t20_label       TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, feature_date)
            )
        """)

    def build_all(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """
        Build labels for all symbols across full date range.
        Optimized: pre-loads trading calendar + prices into memory.
        Skips dates without T+1 future data.

        Returns:
            dict with stats
        """
        mconn = sqlite3.connect(self.market_db, timeout=30)
        mconn.row_factory = sqlite3.Row

        if symbols is None:
            symbols = [
                r[0] for r in mconn.execute(
                    "SELECT symbol FROM symbols_master WHERE is_tradable = 1 ORDER BY symbol"
                ).fetchall()
            ]

        # Pre-load trading calendar as sorted list
        cal = CalendarBuilder(self.market_db)
        all_dates = cal.get_trading_dates(start_date, end_date)
        date_to_idx = {d: i for i, d in enumerate(all_dates)}

        # Pre-load first_trading_dates
        ftd_map = {}
        cols = {row[1] for row in mconn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" in cols:
            for r in mconn.execute("SELECT symbol, first_trading_date FROM symbols_master"):
                if r[1]:
                    ftd_map[r[0]] = r[1]

        # Open signals.db
        sconn = sqlite3.connect(self.signals_db, timeout=30)
        self._ensure_table(sconn)

        stats = {"symbols": 0, "rows_written": 0, "rows_skipped": 0}
        batch = []
        n_dates = len(all_dates)

        for sym_i, sym in enumerate(symbols):
            # Pre-load all closes for this symbol into dict
            rows = mconn.execute(
                "SELECT date, close FROM prices_daily WHERE symbol=? ORDER BY date",
                (sym,),
            ).fetchall()
            closes = {r[0]: r[1] for r in rows if r[1] and r[1] > 0}

            ftd = ftd_map.get(sym)
            sym_count = 0

            for d in all_dates:
                # Skip before listing
                if ftd and d < ftd:
                    continue

                close_t = closes.get(d)
                if close_t is None:
                    stats["rows_skipped"] += 1
                    continue

                idx = date_to_idx.get(d)
                if idx is None:
                    continue

                # Compute labels using index offsets (fast)
                row_data = [sym, d, close_t]
                has_t1 = False

                for h in HORIZONS:
                    target_idx = idx + h
                    if target_idx < n_dates:
                        label_date = all_dates[target_idx]
                        future_close = closes.get(label_date)
                        if future_close is not None:
                            ret = (future_close - close_t) / close_t
                            label = _classify_return(ret)
                            row_data.extend([label_date, round(ret, 6), label])
                            if h == 1:
                                has_t1 = True
                            continue
                    row_data.extend([None, None, None])

                if not has_t1:
                    stats["rows_skipped"] += 1
                    continue

                batch.append(tuple(row_data))
                sym_count += 1

                if len(batch) >= 10000:
                    sconn.executemany(
                        """INSERT OR REPLACE INTO training_labels
                           (symbol, feature_date, close_t,
                            t1_date, t1_return, t1_label,
                            t5_date, t5_return, t5_label,
                            t10_date, t10_return, t10_label,
                            t20_date, t20_return, t20_label)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        batch,
                    )
                    batch = []

            if sym_count > 0:
                stats["symbols"] += 1

            if (sym_i + 1) % 10 == 0:
                print(f"  [{sym_i+1}/{len(symbols)}] {sym}: {sym_count} labels")

        if batch:
            sconn.executemany(
                """INSERT OR REPLACE INTO training_labels
                   (symbol, feature_date, close_t,
                    t1_date, t1_return, t1_label,
                    t5_date, t5_return, t5_label,
                    t10_date, t10_return, t10_label,
                    t20_date, t20_return, t20_label)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                batch,
            )

        sconn.commit()
        stats["rows_written"] = sconn.execute("SELECT COUNT(*) FROM training_labels").fetchone()[0]
        sconn.close()
        mconn.close()

        return stats


class LeakageError(Exception):
    """Raised when data leakage is detected in label building."""
    pass
