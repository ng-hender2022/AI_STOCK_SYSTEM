"""
V4P Expert Writer
Ghi output vao signals.db -> expert_signals.
Doc universe tu MASTER_UNIVERSE.md.
"""

import json
import re
import sqlite3
from pathlib import Path

from .feature_builder import PAFeatureBuilder
from .signal_logic import PASignalLogic, PAOutput

MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def load_universe() -> list[str]:
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SACH DAY DU.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"## DANH S.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Cannot parse universe from {MASTER_UNIVERSE_PATH}")
    raw = match.group(1)
    return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]


class PAExpertWriter:
    """
    End-to-end V4P pipeline.

    Usage:
        writer = PAExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4P"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = PAFeatureBuilder(market_db)
        self.signal_logic = PASignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(self, conn: sqlite3.Connection, output: PAOutput, features) -> None:
        metadata = {
            "trend_structure": features.trend_structure,
            "hh_count": int(features.hh_count),
            "hl_count": int(features.hl_count),
            "lh_count": int(features.lh_count),
            "ll_count": int(features.ll_count),
            "range_position": round(float(features.range_position), 6),
            "sma20": round(float(features.sma20), 4),
            "sma20_slope": round(float(features.sma20_slope), 6),
            "high20": round(float(features.high20), 4),
            "low20": round(float(features.low20), 4),
            "breakout_flag": bool(features.breakout_flag),
            "breakdown_flag": bool(features.breakdown_flag),
            "price_action_norm": round(float(output.price_action_norm), 6),
            "trend_score": round(float(output.trend_score), 4),
            "range_score": round(float(output.range_score), 4),
            "sma20_score": round(float(output.sma20_score), 4),
            "trend_persistence": round(float(features.trend_persistence), 6),
            "ret_1d": round(float(features.ret_1d), 6),
            "ret_5d": round(float(features.ret_5d), 6),
            "ret_10d": round(float(features.ret_10d), 6),
            "ret_20d": round(float(features.ret_20d), 6),
            "gap_ret": round(float(features.gap_ret), 6),
            "breakout60_flag": bool(features.breakout60_flag),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.price_action_score, output.price_action_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> PAOutput:
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
    ) -> list[PAOutput]:
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
