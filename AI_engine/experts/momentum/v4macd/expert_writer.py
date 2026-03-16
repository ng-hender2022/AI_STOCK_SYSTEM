"""
V4MACD Expert Writer
Ghi output vao signals.db -> expert_signals.
Doc universe tu MASTER_UNIVERSE.md.
"""

import json
import re
import sqlite3
from pathlib import Path

from .feature_builder import MACDFeatureBuilder
from .signal_logic import MACDSignalLogic, MACDOutput

MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def load_universe() -> list[str]:
    """Parse sorted A-Z symbol block between ``` markers in MASTER_UNIVERSE.md."""
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SACH DAY DU.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"## DANH S.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Cannot parse universe from {MASTER_UNIVERSE_PATH}")
    raw = match.group(1)
    return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]


class MACDExpertWriter:
    """
    End-to-end V4MACD pipeline.

    Usage:
        writer = MACDExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4MACD"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = MACDFeatureBuilder(market_db)
        self.signal_logic = MACDSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(
        self, conn: sqlite3.Connection, output: MACDOutput, features
    ) -> None:
        metadata = {
            "macd_value": round(features.macd_value, 6),
            "signal_value": round(features.signal_value, 6),
            "histogram_value": round(features.histogram_value, 6),
            "macd_slope": round(features.macd_slope, 6),
            "histogram_slope": round(features.histogram_slope, 6),
            "macd_above_signal": features.macd_above_signal,
            "macd_above_zero": features.macd_above_zero,
            "divergence_flag": features.divergence_flag,
            "cross_score": round(output.cross_score, 4),
            "zero_line_score": round(output.zero_line_score, 4),
            "histogram_score": round(output.histogram_score, 4),
            "divergence_score": round(output.divergence_score, 4),
            "macd_norm": round(output.macd_norm, 6),
            "macd_cross_flag": 1 if features.bull_cross else (-1 if features.bear_cross else 0),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.macd_score, output.macd_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> MACDOutput:
        """Run V4MACD for a single symbol and write to signals.db."""
        features = self.feature_builder.build(symbol, target_date)
        output = self.signal_logic.compute(features)
        conn = self._connect_signals()
        try:
            if output.has_sufficient_data:
                self._write_output(conn, output, features)
            conn.commit()
        finally:
            conn.close()
        return output

    def run_all(
        self, target_date: str, symbols: list[str] | None = None
    ) -> list[MACDOutput]:
        """Run V4MACD for all symbols in the universe."""
        if symbols is None:
            symbols = load_universe()
        features_list = self.feature_builder.build_batch(symbols, target_date)
        results = []
        conn = self._connect_signals()
        try:
            for feat in features_list:
                output = self.signal_logic.compute(feat)
                if output.has_sufficient_data:
                    self._write_output(conn, output, feat)
                results.append(output)
            conn.commit()
        finally:
            conn.close()
        return results
