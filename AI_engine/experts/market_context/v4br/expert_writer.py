"""
V4BR Expert Writer
Computes breadth once for target_date, then writes the SAME breadth score
for every symbol in the universe to signals.db -> expert_signals.

MARKET-WIDE expert: reads ALL stocks from prices_daily,
outputs per-symbol rows (same score for all symbols on a given date).
"""

import json
import re
import sqlite3
from pathlib import Path

from .feature_builder import BreadthFeatureBuilder
from .signal_logic import BreadthSignalLogic, BreadthOutput

MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def load_universe() -> list[str]:
    """Parse tradable symbol list from MASTER_UNIVERSE.md."""
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SACH DAY DU.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"## DANH S.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Cannot parse universe from {MASTER_UNIVERSE_PATH}")
    raw = match.group(1)
    symbols = [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]
    # Exclude VNINDEX (not tradable)
    return [s for s in symbols if s != "VNINDEX"]


class BreadthExpertWriter:
    """
    End-to-end V4BR pipeline.

    KEY DIFFERENCE from per-symbol experts:
    - Computes breadth ONCE across all stocks
    - Writes the SAME breadth score for EVERY symbol in the universe

    Usage:
        writer = BreadthExpertWriter(market_db, signals_db)
        output = writer.run(target_date="2026-03-15")
    """

    EXPERT_ID = "V4BR"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = BreadthFeatureBuilder(market_db)
        self.signal_logic = BreadthSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _build_metadata(self, output: BreadthOutput) -> str:
        """Build JSON metadata for expert_signals row."""
        metadata = {
            "pct_above_sma50": round(output.pct_above_sma50, 2),
            "ad_ratio": round(output.ad_ratio, 4),
            "net_new_highs": int(output.net_new_highs),
            "breadth_momentum": round(output.breadth_momentum, 2),
            "score_pct_above_sma50": output.score_pct_above_sma50,
            "score_ad_ratio": output.score_ad_ratio,
            "score_net_new_highs": output.score_net_new_highs,
            "score_breadth_momentum": output.score_breadth_momentum,
            "neg_divergence": bool(output.neg_divergence),
            "pos_divergence": bool(output.pos_divergence),
            "total_stocks": output.total_stocks,
        }
        return json.dumps(metadata)

    def _write_output_for_symbol(
        self,
        conn: sqlite3.Connection,
        symbol: str,
        output: BreadthOutput,
        metadata_json: str,
    ) -> None:
        """Write one row to expert_signals for a given symbol."""
        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                symbol,
                output.date,
                self.EXPERT_ID,
                output.breadth_score,
                output.breadth_norm,
                output.signal_code,
                output.signal_quality,
                metadata_json,
            ),
        )

    def run(
        self, target_date: str, symbols: list[str] | None = None
    ) -> BreadthOutput:
        """
        Run V4BR for a single date.
        Computes breadth ONCE, then writes for all symbols.

        Args:
            target_date: YYYY-MM-DD format
            symbols: optional list of symbols to write for (default: full universe)

        Returns:
            BreadthOutput with breadth scores
        """
        if symbols is None:
            symbols = load_universe()

        # Step 1: Compute breadth features (reads ALL stocks)
        features = self.feature_builder.build(target_date)

        # Step 2: Compute signal
        output = self.signal_logic.compute(features)

        # Step 3: Write same score for every symbol
        if output.has_sufficient_data:
            metadata_json = self._build_metadata(output)
            conn = self._connect_signals()
            try:
                for symbol in symbols:
                    self._write_output_for_symbol(
                        conn, symbol, output, metadata_json,
                    )
                conn.commit()
            finally:
                conn.close()

        return output

    def run_range(
        self, start_date: str, end_date: str, symbols: list[str] | None = None
    ) -> list[BreadthOutput]:
        """
        Run V4BR for a date range.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            symbols: optional symbol list

        Returns:
            List of BreadthOutput, one per trading day
        """
        if symbols is None:
            symbols = load_universe()

        # Get trading dates from market DB
        conn = sqlite3.connect(self.market_db, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
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
            output = self.run(td, symbols=symbols)
            results.append(output)

        return results
