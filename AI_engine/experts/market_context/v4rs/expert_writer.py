"""
V4RS Expert Writer
Ghi output vao signals.db -> expert_signals.
Doc universe tu MASTER_UNIVERSE.md.
"""

import json
import re
import sqlite3
from pathlib import Path

import numpy as np

from .feature_builder import RSFeatureBuilder, RSFeatures
from .signal_logic import RSSignalLogic, RSOutput

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


def _safe_json_value(val):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        v = float(val)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(val, float):
        if np.isnan(val) or np.isinf(val):
            return None
        return val
    if isinstance(val, bool):
        return val
    return val


class RSExpertWriter:
    """
    End-to-end V4RS pipeline.

    Usage:
        writer = RSExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4RS"

    def __init__(self, market_db: str | Path, signals_db: str | Path):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.feature_builder = RSFeatureBuilder(market_db)
        self.signal_logic = RSSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(self, conn: sqlite3.Connection, output: RSOutput, features: RSFeatures) -> None:
        metadata = {
            "rs_5d": _safe_json_value(round(features.rs_5d, 6)) if not np.isnan(features.rs_5d) else None,
            "rs_20d": _safe_json_value(round(features.rs_20d, 6)) if not np.isnan(features.rs_20d) else None,
            "rs_60d": _safe_json_value(round(features.rs_60d, 6)) if not np.isnan(features.rs_60d) else None,
            "rs_rank_20d": _safe_json_value(round(features.rs_rank_20d, 2)),
            "rs_decile": int(features.rs_decile),
            "rs_trend": features.rs_trend,
            "rs_rank_change_10d": _safe_json_value(round(features.rs_rank_change_10d, 2)),
            "rs_norm": _safe_json_value(round(output.rs_norm, 4)),
            "rs_slope": _safe_json_value(round(features.rs_slope, 6)),
            "rs_acceleration": _safe_json_value(round(features.rs_acceleration, 6)),
            "all_periods_agree": bool(features.all_periods_agree),
            "vnindex_flat": bool(features.vnindex_flat),
            "primary_score": _safe_json_value(output.primary_score),
            "modifier_rank_change": _safe_json_value(output.modifier_rank_change),
            "modifier_all_agree": _safe_json_value(output.modifier_all_agree),
            "modifier_acceleration": _safe_json_value(output.modifier_acceleration),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.rs_score, output.rs_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str, universe: list[str] | None = None) -> RSOutput:
        """Run for a single symbol. Fetches full universe for ranking."""
        if universe is None:
            try:
                universe = load_universe()
            except RuntimeError:
                universe = [symbol]
        if symbol not in universe:
            universe = [symbol] + universe
        # Ensure VNINDEX is in the list
        benchmark = self.feature_builder.cfg["benchmark"]
        if benchmark not in universe:
            universe = [benchmark] + universe

        features_list = self.feature_builder.build_batch(universe, target_date)
        conn = self._connect_signals()
        try:
            result = None
            for feat in features_list:
                output = self.signal_logic.compute(feat)
                if feat.symbol == symbol:
                    result = output
                if output.has_sufficient_data:
                    self._write_output(conn, output, feat)
            conn.commit()
        finally:
            conn.close()

        if result is None:
            return RSOutput(symbol=symbol, date=target_date, data_cutoff_date="")
        return result

    def run_all(
        self, target_date: str, symbols: list[str] | None = None
    ) -> list[RSOutput]:
        """Run for all symbols in universe."""
        if symbols is None:
            symbols = load_universe()
        # Ensure VNINDEX is included
        benchmark = self.feature_builder.cfg["benchmark"]
        if benchmark not in symbols:
            symbols = [benchmark] + symbols

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
