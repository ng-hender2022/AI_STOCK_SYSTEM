"""
vnstock Updater
Fetch OHLCV daily + intraday 15min from vnstock API.
Only updates from the day after the last date in market.db.

Writes to: market.db → prices_daily, prices_intraday
"""

import sqlite3
import re
from datetime import date, datetime, timedelta
from pathlib import Path

_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def _load_universe() -> list[str]:
    text = _UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SÁCH ĐẦY ĐỦ.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        return []
    raw = match.group(1)
    return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]


class VnstockUpdater:
    """
    Incremental updater using vnstock API.

    Usage:
        updater = VnstockUpdater("D:/AI/AI_data/market.db")
        stats = updater.update_daily()
        stats = updater.update_intraday()
    """

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _get_last_date(self, conn: sqlite3.Connection, symbol: str) -> str | None:
        """Get the last date in prices_daily for a symbol."""
        row = conn.execute(
            "SELECT MAX(date) as d FROM prices_daily WHERE symbol = ?",
            (symbol,),
        ).fetchone()
        return row[0] if row and row[0] else None

    def update_daily(
        self,
        symbols: list[str] | None = None,
        end_date: str | None = None,
    ) -> dict:
        """
        Fetch daily OHLCV from vnstock for all symbols.
        Only fetches data AFTER the last date in market.db.

        Returns:
            dict with stats: {updated_symbols, new_rows, errors, skipped}
        """
        try:
            from vnstock import Vnstock
        except ImportError:
            return {"error": "vnstock not installed. Run: pip install vnstock"}

        if symbols is None:
            symbols = _load_universe()
        if end_date is None:
            end_date = date.today().isoformat()

        conn = self._connect()
        stats = {"updated_symbols": 0, "new_rows": 0, "errors": [], "skipped": 0}

        for sym in symbols:
            try:
                last_date = self._get_last_date(conn, sym)

                if last_date:
                    start = (
                        datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
                    ).strftime("%Y-%m-%d")
                    if start > end_date:
                        stats["skipped"] += 1
                        continue
                else:
                    start = "2020-01-01"

                # vnstock fetch
                stock = Vnstock().stock(symbol=sym, source="VCI")
                df = stock.quote.history(start=start, end=end_date)

                if df is None or df.empty:
                    stats["skipped"] += 1
                    continue

                batch = []
                for _, row in df.iterrows():
                    d = row.get("time") or row.get("date")
                    if hasattr(d, "strftime"):
                        d = d.strftime("%Y-%m-%d")
                    else:
                        d = str(d)[:10]

                    batch.append((
                        sym, d,
                        float(row.get("open", 0)),
                        float(row.get("high", 0)),
                        float(row.get("low", 0)),
                        float(row.get("close", 0)),
                        int(row.get("volume", 0)),
                        float(row.get("value", 0)) if "value" in row else None,
                    ))

                if batch:
                    conn.executemany(
                        """INSERT OR REPLACE INTO prices_daily
                           (symbol, date, open, high, low, close, volume, value)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch,
                    )
                    stats["new_rows"] += len(batch)
                    stats["updated_symbols"] += 1

            except Exception as e:
                stats["errors"].append(f"{sym}: {e}")

        conn.commit()
        conn.close()
        return stats

    def update_intraday(
        self,
        symbols: list[str] | None = None,
        target_date: str | None = None,
    ) -> dict:
        """
        Fetch intraday 15-min snapshots from vnstock.

        Returns:
            dict with stats
        """
        try:
            from vnstock import Vnstock
        except ImportError:
            return {"error": "vnstock not installed. Run: pip install vnstock"}

        if symbols is None:
            symbols = _load_universe()
        if target_date is None:
            target_date = date.today().isoformat()

        conn = self._connect()
        stats = {"updated_symbols": 0, "new_rows": 0, "errors": []}

        for sym in symbols:
            if sym == "VNINDEX":
                continue
            try:
                stock = Vnstock().stock(symbol=sym, source="VCI")
                df = stock.quote.intraday(symbol=sym)

                if df is None or df.empty:
                    continue

                batch = []
                for _, row in df.iterrows():
                    t = row.get("time", "")
                    if hasattr(t, "strftime"):
                        snapshot_time = t.strftime("%H:%M")
                        d = t.strftime("%Y-%m-%d")
                    else:
                        snapshot_time = str(t)[-5:]
                        d = target_date

                    batch.append((
                        sym, d, snapshot_time,
                        float(row.get("open", 0)),
                        float(row.get("high", 0)),
                        float(row.get("low", 0)),
                        float(row.get("close", 0)),
                        int(row.get("volume", 0)),
                        float(row.get("value", 0)) if "value" in row else None,
                    ))

                if batch:
                    conn.executemany(
                        """INSERT OR REPLACE INTO prices_intraday
                           (symbol, date, snapshot_time, open, high, low, close, volume, value)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch,
                    )
                    stats["new_rows"] += len(batch)
                    stats["updated_symbols"] += 1

            except Exception as e:
                stats["errors"].append(f"{sym}: {e}")

        conn.commit()
        conn.close()
        return stats
