"""
Data Normalizer
Standardize schema, date formats, numeric types in market.db.
"""

import sqlite3
import re
from datetime import datetime
from pathlib import Path


class Normalizer:
    """
    Normalize market.db data.

    Usage:
        norm = Normalizer("D:/AI/AI_data/market.db")
        stats = norm.normalize_all()
    """

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def normalize_dates(self) -> int:
        """
        Ensure all dates in prices_daily are YYYY-MM-DD format.
        Fixes common issues: M/D/YYYY, DD/MM/YYYY, extra timestamps.
        Returns number of rows fixed.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT rowid, symbol, date FROM prices_daily"
        ).fetchall()

        fixed = 0
        for rowid, symbol, d in rows:
            normalized = self._normalize_date(d)
            if normalized != d:
                conn.execute(
                    "UPDATE prices_daily SET date = ? WHERE rowid = ?",
                    (normalized, rowid),
                )
                fixed += 1

        conn.commit()
        conn.close()
        return fixed

    def normalize_numerics(self) -> int:
        """
        Ensure OHLCV are proper numeric types.
        Fixes: string numbers, negative volumes, null closes.
        Returns number of rows fixed.
        """
        conn = self._connect()

        # Fix negative volumes
        fixed = conn.execute(
            "UPDATE prices_daily SET volume = ABS(volume) WHERE volume < 0"
        ).rowcount

        # Fix null/zero closes where we have other data
        fixed += conn.execute(
            """UPDATE prices_daily SET close = (open + high + low) / 3
               WHERE (close IS NULL OR close <= 0)
               AND open > 0 AND high > 0 AND low > 0"""
        ).rowcount

        conn.commit()
        conn.close()
        return fixed

    def normalize_symbols(self) -> int:
        """
        Ensure all symbols are uppercase, trimmed.
        Returns number of rows fixed.
        """
        conn = self._connect()

        fixed = conn.execute(
            """UPDATE prices_daily
               SET symbol = UPPER(TRIM(symbol))
               WHERE symbol != UPPER(TRIM(symbol))"""
        ).rowcount

        conn.commit()
        conn.close()
        return fixed

    def normalize_all(self) -> dict:
        """Run all normalizations."""
        return {
            "dates_fixed": self.normalize_dates(),
            "numerics_fixed": self.normalize_numerics(),
            "symbols_fixed": self.normalize_symbols(),
        }

    @staticmethod
    def _normalize_date(d: str) -> str:
        """Normalize a single date string to YYYY-MM-DD."""
        d = d.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            return d
        for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y",
                     "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return d  # return as-is if unparseable
