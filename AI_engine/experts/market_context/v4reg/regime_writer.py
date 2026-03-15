"""
V4REG Regime Writer
Ghi regime output vào market.db → market_regime table.
Đọc previous smooth score để truyền vào signal_logic.
"""

import sqlite3
from pathlib import Path
from datetime import date

from .feature_builder import RegimeFeatureBuilder
from .signal_logic import RegimeSignalLogic, RegimeOutput


class RegimeWriter:
    """
    End-to-end V4REG pipeline: build features → score → write to DB.

    Usage:
        writer = RegimeWriter(db_path="D:/AI/AI_data/market.db")
        output = writer.run(target_date="2026-03-15")
        writer.run_range(start_date="2026-01-01", end_date="2026-03-15")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.feature_builder = RegimeFeatureBuilder(db_path)
        self.signal_logic = RegimeSignalLogic()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        """Add extra columns if they don't exist (schema evolution)."""
        existing = set()
        for row in conn.execute("PRAGMA table_info(market_regime)"):
            existing.add(row["name"])

        extras = {
            "trend_regime_score_raw": "REAL",
            "liquidity_score": "REAL",
            "regime_confidence": "REAL",
            "panic_triggered": "INTEGER DEFAULT 0",
            "blowoff_triggered": "INTEGER DEFAULT 0",
        }
        for col, col_type in extras.items():
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE market_regime ADD COLUMN {col} {col_type}"
                )

    def _get_prev_smooth_score(
        self, conn: sqlite3.Connection, before_date: str
    ) -> float | None:
        """Get most recent smoothed trend regime score before given date."""
        row = conn.execute(
            """
            SELECT regime_score FROM market_regime
            WHERE date < ? AND snapshot_time = 'EOD'
            ORDER BY date DESC LIMIT 1
            """,
            (before_date,),
        ).fetchone()
        return float(row["regime_score"]) if row else None

    def _write_output(
        self, conn: sqlite3.Connection, output: RegimeOutput
    ) -> None:
        """Write regime output to market_regime table."""
        conn.execute(
            """
            INSERT OR REPLACE INTO market_regime (
                date, snapshot_time,
                regime_score, regime_label,
                breadth_score, volatility_score, trend_score,
                trend_regime_score_raw, liquidity_score,
                regime_confidence,
                panic_triggered, blowoff_triggered
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                output.date,
                "EOD",
                output.trend_regime_score,       # main score (smoothed)
                output.regime_label,
                output.breadth_score,
                output.vol_regime_score,
                output.trend_structure_score,
                output.trend_regime_score_raw,
                output.liquidity_regime_score,
                output.regime_confidence,
                1 if output.panic_triggered else 0,
                1 if output.blowoff_triggered else 0,
            ),
        )

    def run(self, target_date: str) -> RegimeOutput:
        """
        Run V4REG for a single date.

        Args:
            target_date: YYYY-MM-DD format

        Returns:
            RegimeOutput with all scores
        """
        conn = self._connect()
        try:
            self._ensure_columns(conn)

            # Build features (data leakage safe: uses only data < target_date)
            features = self.feature_builder.build(target_date)

            # Get previous smoothed score for continuity
            prev_smooth = self._get_prev_smooth_score(conn, target_date)

            # Compute scores
            output = self.signal_logic.compute(features, prev_smooth)

            # Write to DB
            self._write_output(conn, output)
            conn.commit()

            return output
        finally:
            conn.close()

    def run_range(
        self, start_date: str, end_date: str
    ) -> list[RegimeOutput]:
        """
        Run V4REG for a date range. Processes chronologically
        so smoothing carries forward correctly.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD

        Returns:
            List of RegimeOutput, one per trading day
        """
        conn = self._connect()
        try:
            self._ensure_columns(conn)

            # Get all trading dates in range (dates with VNINDEX data)
            rows = conn.execute(
                """
                SELECT DISTINCT date FROM prices_daily
                WHERE symbol = 'VNINDEX' AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (start_date, end_date),
            ).fetchall()
            trading_dates = [r["date"] for r in rows]
        finally:
            conn.close()

        results = []
        for td in trading_dates:
            output = self.run(td)
            results.append(output)

        return results
