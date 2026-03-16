"""
AmiBroker CSV Importer
Reads multi-symbol CSV export from AmiBroker.

Expected CSV format:
    Ticker, Date (M/D/YYYY HH:MM:SS), Open, High, Low, Close, Volume, RefPrice
    (may have extra columns — they are ignored)

Writes to: market.db → prices_daily
"""

import csv
import sqlite3
import re
from datetime import datetime
from pathlib import Path

# Universe loader
_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def _load_universe_set() -> set[str]:
    text = _UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SÁCH ĐẦY ĐỦ.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        return set()
    raw = match.group(1)
    return {s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()}


def _parse_date(date_str: str) -> str:
    """Parse AmiBroker date format → YYYY-MM-DD."""
    date_str = date_str.strip()
    # Try M/D/YYYY HH:MM:SS
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{date_str}'")


class AmiBrokerImporter:
    """
    Import AmiBroker CSV into market.db.

    Usage:
        importer = AmiBrokerImporter("D:/AI/AI_data/market.db")
        stats = importer.import_file("D:/data/export.csv")
        stats = importer.import_directory("D:/data/")
    """

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)
        self.universe = _load_universe_set()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_ref_price_column(self, conn: sqlite3.Connection) -> None:
        """Add ref_price column if not exists."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(prices_daily)")}
        if "ref_price" not in cols:
            conn.execute("ALTER TABLE prices_daily ADD COLUMN ref_price REAL")

    def _ensure_first_trading_date_column(self, conn: sqlite3.Connection) -> None:
        """Add first_trading_date column to symbols_master if not exists."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(symbols_master)")}
        if "first_trading_date" not in cols:
            conn.execute(
                "ALTER TABLE symbols_master ADD COLUMN first_trading_date DATE"
            )

    def _update_first_trading_dates(self, conn: sqlite3.Connection) -> None:
        """
        Set first_trading_date for each symbol in symbols_master
        based on earliest date in prices_daily.
        """
        self._ensure_first_trading_date_column(conn)
        conn.execute("""
            UPDATE symbols_master
            SET first_trading_date = (
                SELECT MIN(date) FROM prices_daily
                WHERE prices_daily.symbol = symbols_master.symbol
            )
            WHERE EXISTS (
                SELECT 1 FROM prices_daily
                WHERE prices_daily.symbol = symbols_master.symbol
            )
        """)

    def import_file(
        self,
        csv_path: str | Path,
        filter_universe: bool = True,
    ) -> dict:
        """
        Import a single AmiBroker CSV file.

        Args:
            csv_path: path to CSV
            filter_universe: if True, skip symbols not in MASTER_UNIVERSE

        Returns:
            dict with stats: {imported, skipped, errors, symbols}
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        conn = self._connect()
        self._ensure_ref_price_column(conn)

        stats = {"imported": 0, "skipped": 0, "errors": 0, "symbols": set()}
        batch = []

        # Detect encoding
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

            for row_num, row in enumerate(reader, 1):
                if len(row) < 7:
                    stats["errors"] += 1
                    continue

                # Skip header
                if row[0].strip().upper() in ("TICKER", "SYMBOL", "<TICKER>"):
                    continue

                try:
                    ticker = row[0].strip().upper()

                    if filter_universe and ticker not in self.universe:
                        stats["skipped"] += 1
                        continue

                    date_str = _parse_date(row[1])
                    o = float(row[2])
                    h = float(row[3])
                    l = float(row[4])
                    c = float(row[5])
                    v = int(float(row[6]))
                    ref = float(row[7]) if len(row) > 7 and row[7].strip() else None

                    batch.append((ticker, date_str, o, h, l, c, v, ref))
                    stats["symbols"].add(ticker)

                    if len(batch) >= 5000:
                        self._flush_batch(conn, batch)
                        stats["imported"] += len(batch)
                        batch = []

                except (ValueError, IndexError) as e:
                    stats["errors"] += 1

        if batch:
            self._flush_batch(conn, batch)
            stats["imported"] += len(batch)

        # Update first_trading_date in symbols_master
        self._update_first_trading_dates(conn)

        conn.commit()
        conn.close()
        stats["symbols"] = len(stats["symbols"])
        return stats

    def _flush_batch(
        self, conn: sqlite3.Connection, batch: list[tuple]
    ) -> None:
        """Bulk insert batch into prices_daily."""
        conn.executemany(
            """
            INSERT OR REPLACE INTO prices_daily
                (symbol, date, open, high, low, close, volume, ref_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )

    def import_directory(
        self, dir_path: str | Path, filter_universe: bool = True
    ) -> dict:
        """Import all CSV files in a directory."""
        dir_path = Path(dir_path)
        total_stats = {"imported": 0, "skipped": 0, "errors": 0, "files": 0}

        for csv_file in sorted(dir_path.glob("*.csv")):
            stats = self.import_file(csv_file, filter_universe)
            total_stats["imported"] += stats["imported"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            total_stats["files"] += 1

        return total_stats
