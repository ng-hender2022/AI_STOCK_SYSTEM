"""
V4PIVOT Expert Writer
Ghi output vao signals.db -> expert_signals.
Doc universe tu MASTER_UNIVERSE.md.
"""

import json
import re
import sqlite3
from pathlib import Path

from .feature_builder import PivotFeatureBuilder
from .signal_logic import PivotSignalLogic, PivotOutput

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


class PivotExpertWriter:
    """
    End-to-end V4PIVOT pipeline.

    Usage:
        writer = PivotExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4PIVOT"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = PivotFeatureBuilder(market_db)
        self.signal_logic = PivotSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(self, conn: sqlite3.Connection, output: PivotOutput, features) -> None:
        metadata = {
            "pivot": round(float(features.pivot), 4),
            "r1": round(float(features.r1), 4),
            "r2": round(float(features.r2), 4),
            "s1": round(float(features.s1), 4),
            "s2": round(float(features.s2), 4),
            "weekly_pivot": round(float(features.weekly_pivot), 4),
            "monthly_pivot": round(float(features.monthly_pivot), 4),
            "position_score": round(float(output.position_score), 4),
            "confluence_score": round(float(output.confluence_score), 4),
            "alignment_score": round(float(output.alignment_score), 4),
            "pivot_norm": round(float(output.pivot_norm), 6),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.pivot_score, output.pivot_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> PivotOutput:
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
    ) -> list[PivotOutput]:
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
