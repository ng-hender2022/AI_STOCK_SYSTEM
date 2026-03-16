"""
V4SR Expert Writer
Writes output to signals.db -> expert_signals.
Reads universe from MASTER_UNIVERSE.md.
"""

import json
import re
import sqlite3
from pathlib import Path

from .feature_builder import SRFeatureBuilder
from .signal_logic import SRSignalLogic, SROutput

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


class SRExpertWriter:
    """
    End-to-end V4SR pipeline.

    Usage:
        writer = SRExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4SR"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = SRFeatureBuilder(market_db)
        self.signal_logic = SRSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(self, conn: sqlite3.Connection, output: SROutput,
                      features) -> None:
        metadata = {
            "nearest_support": round(float(features.nearest_support), 4),
            "nearest_resistance": round(float(features.nearest_resistance), 4),
            "nearest_support_strength": round(float(features.nearest_support_strength), 4),
            "nearest_resistance_strength": round(float(features.nearest_resistance_strength), 4),
            "dist_to_support": round(float(features.dist_to_support), 6),
            "dist_to_resistance": round(float(features.dist_to_resistance), 6),
            "num_sr_zones": int(features.num_sr_zones),
            "atr_value": round(float(features.atr_value), 4),
            "sr_norm": round(float(output.sr_norm), 6),
            "position_score": round(float(output.position_score), 4),
            "strength_score": round(float(output.strength_score), 4),
            "context_score": round(float(output.context_score), 4),
            "breakout_above_resistance": bool(features.breakout_above_resistance),
            "breakdown_below_support": bool(features.breakdown_below_support),
            "price_bouncing": bool(features.price_bouncing),
            "price_rejecting": bool(features.price_rejecting),
            "volume_rising": bool(features.volume_rising),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.sr_score, output.sr_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> SROutput:
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
    ) -> list[SROutput]:
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
