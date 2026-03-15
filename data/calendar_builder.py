"""
Trading Calendar Builder
Reads TRADING_CALENDAR.csv (VNINDEX-only), extracts trading dates.

CSV format: Ticker, Date (M/D/YYYY HH:MM:SS), Close, Volume — VNINDEX only

Writes to:
    - D:\\AI\\AI_brain\\SYSTEM\\TRADING_CALENDAR_MASTER.csv (single source of truth)
    - market.db → trading_calendar table
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path


CALENDAR_MASTER_PATH = Path(
    r"D:\AI\AI_brain\SYSTEM\TRADING_CALENDAR_MASTER.csv"
)


def _parse_date(date_str: str) -> str:
    """Parse calendar CSV date → YYYY-MM-DD."""
    date_str = date_str.strip()
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{date_str}'")


class CalendarBuilder:
    """
    Build trading calendar from VNINDEX CSV.

    Usage:
        builder = CalendarBuilder("D:/AI/AI_data/market.db")
        stats = builder.build_from_csv("D:/data/TRADING_CALENDAR.csv")
        dates = builder.get_trading_dates()
        next_td = builder.offset_trading_day("2026-03-10", 5)
    """

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trading_calendar (
                date            DATE PRIMARY KEY,
                is_trading_day  INTEGER DEFAULT 1,
                vnindex_close   REAL,
                vnindex_volume  INTEGER,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def build_from_csv(self, csv_path: str | Path) -> dict:
        """
        Parse TRADING_CALENDAR.csv and write to DB + master CSV.

        Returns:
            dict with stats: {dates_parsed, written_db, written_csv}
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Calendar CSV not found: {csv_path}")

        rows_parsed = []

        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(csv_path, "r", encoding=enc) as f:
                    f.readline()
                encoding = enc
                break
            except UnicodeDecodeError:
                encoding = "latin-1"

        with open(csv_path, "r", encoding=encoding) as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 4:
                    continue
                ticker = row[0].strip().upper()
                if ticker in ("TICKER", "<TICKER>", "SYMBOL"):
                    continue
                # Only VNINDEX rows
                if ticker != "VNINDEX":
                    continue

                try:
                    d = _parse_date(row[1])
                    close_val = float(row[2]) if row[2].strip() else None
                    vol = int(float(row[3])) if row[3].strip() else None
                    rows_parsed.append((d, close_val, vol))
                except (ValueError, IndexError):
                    continue

        # Sort by date
        rows_parsed.sort(key=lambda x: x[0])

        # Write to market.db
        conn = self._connect()
        self._ensure_table(conn)
        conn.executemany(
            """INSERT OR REPLACE INTO trading_calendar
               (date, is_trading_day, vnindex_close, vnindex_volume)
               VALUES (?, 1, ?, ?)""",
            rows_parsed,
        )
        conn.commit()
        conn.close()

        # Write master CSV
        CALENDAR_MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CALENDAR_MASTER_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "vnindex_close", "vnindex_volume"])
            for d, c, v in rows_parsed:
                writer.writerow([d, c or "", v or ""])

        return {
            "dates_parsed": len(rows_parsed),
            "written_db": len(rows_parsed),
            "written_csv": str(CALENDAR_MASTER_PATH),
            "date_range": f"{rows_parsed[0][0]} → {rows_parsed[-1][0]}" if rows_parsed else "empty",
        }

    def build_from_db(self) -> dict:
        """
        Build calendar from existing VNINDEX data in prices_daily.
        Use when no separate calendar CSV is available.
        """
        conn = self._connect()
        self._ensure_table(conn)

        rows = conn.execute(
            """SELECT date, close, volume FROM prices_daily
               WHERE symbol = 'VNINDEX' ORDER BY date"""
        ).fetchall()

        batch = [(r[0], r[1], r[2]) for r in rows]
        conn.executemany(
            """INSERT OR REPLACE INTO trading_calendar
               (date, is_trading_day, vnindex_close, vnindex_volume)
               VALUES (?, 1, ?, ?)""",
            batch,
        )
        conn.commit()
        conn.close()

        return {"dates_from_db": len(batch)}

    def get_trading_dates(
        self, start: str | None = None, end: str | None = None
    ) -> list[str]:
        """Get list of trading dates from calendar."""
        conn = self._connect()
        self._ensure_table(conn)

        sql = "SELECT date FROM trading_calendar WHERE is_trading_day = 1"
        params = []
        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        sql += " ORDER BY date"

        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def offset_trading_day(self, from_date: str, offset: int) -> str | None:
        """
        Get the trading date that is `offset` trading days from from_date.
        Positive = forward, negative = backward.
        """
        dates = self.get_trading_dates()
        if not dates:
            return None

        try:
            idx = dates.index(from_date)
        except ValueError:
            # Find nearest
            for i, d in enumerate(dates):
                if d >= from_date:
                    idx = i
                    break
            else:
                return None

        target_idx = idx + offset
        if 0 <= target_idx < len(dates):
            return dates[target_idx]
        return None
