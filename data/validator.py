"""
Data Validator
Check for: missing data, spikes >15% vs RefPrice, duplicates, OHLC inconsistency.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationReport:
    """Validation results."""
    total_rows: int = 0
    duplicates: int = 0
    missing_close: int = 0
    ohlc_inconsistencies: int = 0
    spike_violations: int = 0
    negative_volumes: int = 0
    missing_dates_per_symbol: dict = field(default_factory=dict)
    details: list = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return (
            self.duplicates == 0
            and self.missing_close == 0
            and self.ohlc_inconsistencies == 0
            and self.spike_violations == 0
            and self.negative_volumes == 0
        )


class Validator:
    """
    Validate market.db data quality.

    Usage:
        v = Validator("D:/AI/AI_data/market.db")
        report = v.validate_all()
        print(report.is_clean)
    """

    SPIKE_THRESHOLD = 0.15  # 15% deviation from ref_price

    def __init__(self, market_db: str | Path):
        self.market_db = str(market_db)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def validate_all(self) -> ValidationReport:
        """Run all validation checks."""
        report = ValidationReport()
        conn = self._connect()

        report.total_rows = conn.execute(
            "SELECT COUNT(*) FROM prices_daily"
        ).fetchone()[0]

        self._check_duplicates(conn, report)
        self._check_missing_close(conn, report)
        self._check_ohlc_consistency(conn, report)
        self._check_spikes(conn, report)
        self._check_negative_volume(conn, report)

        conn.close()
        return report

    def _check_duplicates(
        self, conn: sqlite3.Connection, report: ValidationReport
    ) -> None:
        """Check for duplicate (symbol, date) rows."""
        rows = conn.execute("""
            SELECT symbol, date, COUNT(*) as cnt
            FROM prices_daily
            GROUP BY symbol, date
            HAVING cnt > 1
        """).fetchall()
        report.duplicates = len(rows)
        for r in rows:
            report.details.append(
                f"DUPLICATE: {r['symbol']} {r['date']} ({r['cnt']} rows)"
            )

    def _check_missing_close(
        self, conn: sqlite3.Connection, report: ValidationReport
    ) -> None:
        """Check for NULL or zero close prices."""
        rows = conn.execute("""
            SELECT symbol, date FROM prices_daily
            WHERE close IS NULL OR close <= 0
        """).fetchall()
        report.missing_close = len(rows)
        for r in rows[:20]:  # limit output
            report.details.append(
                f"MISSING_CLOSE: {r['symbol']} {r['date']}"
            )

    def _check_ohlc_consistency(
        self, conn: sqlite3.Connection, report: ValidationReport
    ) -> None:
        """
        Check OHLC rules:
          - high >= low
          - high >= open AND high >= close
          - low <= open AND low <= close
        """
        rows = conn.execute("""
            SELECT symbol, date, open, high, low, close FROM prices_daily
            WHERE (high < low)
               OR (high < open) OR (high < close)
               OR (low > open) OR (low > close)
        """).fetchall()
        report.ohlc_inconsistencies = len(rows)
        for r in rows[:20]:
            report.details.append(
                f"OHLC_BAD: {r['symbol']} {r['date']} "
                f"O={r['open']} H={r['high']} L={r['low']} C={r['close']}"
            )

    def _check_spikes(
        self, conn: sqlite3.Connection, report: ValidationReport
    ) -> None:
        """Check if close deviates >15% from ref_price (if available)."""
        # Check if ref_price column exists
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(prices_daily)")}
        if "ref_price" not in cols:
            return

        rows = conn.execute("""
            SELECT symbol, date, close, ref_price FROM prices_daily
            WHERE ref_price IS NOT NULL AND ref_price > 0
              AND ABS(close - ref_price) / ref_price > ?
        """, (self.SPIKE_THRESHOLD,)).fetchall()

        report.spike_violations = len(rows)
        for r in rows[:20]:
            pct = abs(r["close"] - r["ref_price"]) / r["ref_price"] * 100
            report.details.append(
                f"SPIKE: {r['symbol']} {r['date']} "
                f"close={r['close']} ref={r['ref_price']} ({pct:.1f}%)"
            )

    def _check_negative_volume(
        self, conn: sqlite3.Connection, report: ValidationReport
    ) -> None:
        """Check for negative volumes."""
        rows = conn.execute(
            "SELECT symbol, date, volume FROM prices_daily WHERE volume < 0"
        ).fetchall()
        report.negative_volumes = len(rows)
        for r in rows[:20]:
            report.details.append(
                f"NEG_VOL: {r['symbol']} {r['date']} vol={r['volume']}"
            )
