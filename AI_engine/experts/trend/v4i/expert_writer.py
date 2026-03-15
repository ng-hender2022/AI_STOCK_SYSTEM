"""
V4I Ichimoku Expert Writer
Ghi output vào signals.db → expert_signals table.
Đọc universe từ MASTER_UNIVERSE.md.
"""

import re
import sqlite3
from pathlib import Path

from .feature_builder import IchimokuFeatureBuilder
from .signal_logic import IchimokuSignalLogic, IchimokuOutput

MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def load_universe() -> list[str]:
    """Load symbol list from MASTER_UNIVERSE.md."""
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")

    # Extract the sorted A-Z block between ``` markers
    match = re.search(r"## DANH SÁCH ĐẦY ĐỦ.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Cannot parse universe from {MASTER_UNIVERSE_PATH}")

    raw = match.group(1)
    symbols = [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]
    return symbols


class IchimokuExpertWriter:
    """
    End-to-end V4I pipeline: build features → score → write to signals.db.

    Usage:
        writer = IchimokuExpertWriter(
            market_db="D:/AI/AI_data/market.db",
            signals_db="D:/AI/AI_data/signals.db",
        )
        # Single symbol
        output = writer.run_symbol("VNM", "2026-03-15")

        # All universe
        results = writer.run_all("2026-03-15")

        # Date range
        results = writer.run_range("2026-01-01", "2026-03-15")
    """

    EXPERT_ID = "V4I"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = IchimokuFeatureBuilder(market_db)
        self.signal_logic = IchimokuSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _write_output(
        self, conn: sqlite3.Connection, output: IchimokuOutput
    ) -> None:
        """Write single output to expert_signals."""
        import json

        metadata = {
            "cloud_position": output.cloud_position,
            "tk_signal": output.tk_signal,
            "chikou_confirm": output.chikou_confirm,
            "future_cloud": output.future_cloud,
            "time_resonance": output.time_resonance,
            "near_cycle": output.near_cycle,
            "days_since_pivot": output.days_since_pivot,
            "ichimoku_norm": output.ichimoku_norm,
            "cloud_position_score": output.cloud_position_score,
            "tk_signal_score": output.tk_signal_score,
            "chikou_confirm_score": output.chikou_confirm_score,
            "future_cloud_score": output.future_cloud_score,
        }

        conn.execute(
            """
            INSERT OR REPLACE INTO expert_signals (
                symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json
            ) VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)
            """,
            (
                output.symbol,
                output.date,
                self.EXPERT_ID,
                output.ichimoku_score,       # primary = raw score -4..+4
                output.ichimoku_norm,        # secondary = normalized -1..+1
                output.signal_code,
                output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> IchimokuOutput:
        """Run V4I for a single symbol on target_date."""
        features = self.feature_builder.build(symbol, target_date)
        output = self.signal_logic.compute(features)

        conn = self._connect_signals()
        try:
            self._write_output(conn, output)
            conn.commit()
        finally:
            conn.close()

        return output

    def run_all(
        self, target_date: str, symbols: list[str] | None = None
    ) -> list[IchimokuOutput]:
        """
        Run V4I for all symbols in universe on target_date.

        Args:
            target_date: YYYY-MM-DD
            symbols: optional override list; if None, loads from MASTER_UNIVERSE
        """
        if symbols is None:
            symbols = load_universe()

        features_list = self.feature_builder.build_batch(symbols, target_date)
        results = []

        conn = self._connect_signals()
        try:
            for features in features_list:
                output = self.signal_logic.compute(features)
                if output.has_sufficient_data:
                    self._write_output(conn, output)
                results.append(output)
            conn.commit()
        finally:
            conn.close()

        return results

    def run_range(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> dict[str, list[IchimokuOutput]]:
        """
        Run V4I for date range. Returns {date: [outputs]}.
        """
        if symbols is None:
            symbols = load_universe()

        # Get trading dates from market.db
        conn = sqlite3.connect(self.market_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT DISTINCT date FROM prices_daily
            WHERE symbol = 'VNINDEX' AND date >= ? AND date <= ?
            ORDER BY date
            """,
            (start_date, end_date),
        ).fetchall()
        conn.close()

        trading_dates = [r["date"] for r in rows]
        all_results = {}

        for td in trading_dates:
            all_results[td] = self.run_all(td, symbols)

        return all_results
