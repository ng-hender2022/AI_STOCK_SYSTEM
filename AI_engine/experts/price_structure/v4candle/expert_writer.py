"""
V4CANDLE Expert Writer
Ghi output vao signals.db -> expert_signals.
Doc universe tu MASTER_UNIVERSE.md.
"""

import json
import re
import sqlite3
from pathlib import Path

from .feature_builder import CandleFeatureBuilder
from .signal_logic import CandleSignalLogic, CandleOutput

MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def load_universe() -> list[str]:
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SACH DAY DU.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"## DANH S.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Cannot parse universe from {MASTER_UNIVERSE_PATH}")
    raw = match.group(1)
    symbols = [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]
    symbols.sort()
    return symbols


class CandleExpertWriter:
    """
    End-to-end V4CANDLE pipeline.

    Usage:
        writer = CandleExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4CANDLE"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = CandleFeatureBuilder(market_db)
        self.signal_logic = CandleSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(self, conn: sqlite3.Connection, output: CandleOutput, features) -> None:
        metadata = {
            "pattern_name": str(output.pattern_name),
            "pattern_direction": str(output.pattern_direction),
            "body_pct": round(float(features.body_pct), 6),
            "upper_shadow_pct": round(float(features.upper_shadow_pct), 6),
            "lower_shadow_pct": round(float(features.lower_shadow_pct), 6),
            "volume_confirm": bool(features.volume_ratio >= self.signal_logic.cfg["vol_confirm_ratio"]),
            "at_swing": bool(features.at_swing_high or features.at_swing_low),
            "candle_norm": round(float(output.candle_norm), 6),
            "volume_ratio": round(float(features.volume_ratio), 4),
            "pattern_score": round(float(output.pattern_score), 4),
            "volume_modifier": round(float(output.volume_modifier), 4),
            "context_modifier": round(float(output.context_modifier), 4),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.candle_score, output.candle_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> CandleOutput:
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
    ) -> list[CandleOutput]:
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
