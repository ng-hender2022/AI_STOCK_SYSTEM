"""
V4S Expert Writer
Ghi output vao signals.db -> expert_signals.
Doc universe tu MASTER_UNIVERSE.md.
"""

import json
import sqlite3
from pathlib import Path

from .feature_builder import SectorFeatureBuilder, SectorFeatures, load_universe, load_sector_mapping
from .signal_logic import SectorSignalLogic, SectorOutput


class SectorExpertWriter:
    """
    End-to-end V4S pipeline.

    Usage:
        writer = SectorExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2026-03-16")
        results = writer.run_all("2026-03-16")
    """

    EXPERT_ID = "V4S"

    def __init__(self, market_db: str | Path, signals_db: str | Path,
                 sector_mapping: dict[str, str] | None = None):
        self.market_db = str(market_db)
        self.signals_db = str(signals_db)
        self.sector_mapping = sector_mapping or load_sector_mapping()
        self.feature_builder = SectorFeatureBuilder(market_db, self.sector_mapping)
        self.signal_logic = SectorSignalLogic()

    def _connect_signals(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _write_output(self, conn: sqlite3.Connection, output: SectorOutput,
                      features: SectorFeatures) -> None:
        metadata = {
            "sector_name": features.sector_name,
            "sector_rank_20d": features.sector_rank_20d,
            "sector_vs_market_20d": round(features.sector_vs_market_20d, 6),
            "sector_return_20d": round(features.sector_return_20d, 6),
            "sector_momentum": round(features.sector_momentum, 6),
            "sector_pct_above_sma50": round(features.sector_pct_above_sma50, 4),
            "sector_rank_change_10d": features.sector_rank_change_10d,
            "is_sector_leader": bool(features.is_sector_leader),
            "is_sector_laggard": bool(features.is_sector_laggard),
            "stock_vs_sector_20d": round(features.stock_vs_sector_20d, 6),
            "sector_norm": round(output.sector_norm, 6),
        }

        conn.execute(
            """INSERT OR REPLACE INTO expert_signals
               (symbol, date, snapshot_time, expert_id,
                primary_score, secondary_score,
                signal_code, signal_quality, metadata_json)
               VALUES (?, ?, 'EOD', ?, ?, ?, ?, ?, ?)""",
            (
                output.symbol, output.date, self.EXPERT_ID,
                output.sector_score, output.sector_norm,
                output.signal_code, output.signal_quality,
                json.dumps(metadata),
            ),
        )

    def run_symbol(self, symbol: str, target_date: str) -> SectorOutput:
        """Run V4S for a single symbol. Needs all sector data."""
        all_symbols = list(self.sector_mapping.keys())
        if "VNINDEX" not in all_symbols:
            all_symbols.append("VNINDEX")

        features_list = self.feature_builder.build_all(
            all_symbols, target_date, self.sector_mapping
        )
        # Find this symbol's features
        target_feat = None
        for feat in features_list:
            if feat.symbol == symbol:
                target_feat = feat
                break

        if target_feat is None:
            return SectorOutput(symbol=symbol, date=target_date, data_cutoff_date="")

        output = self.signal_logic.compute(target_feat)

        conn = self._connect_signals()
        try:
            if output.has_sufficient_data:
                self._write_output(conn, output, target_feat)
            conn.commit()
        finally:
            conn.close()

        return output

    def run_all(
        self, target_date: str, symbols: list[str] | None = None
    ) -> list[SectorOutput]:
        """Run V4S for all symbols."""
        if symbols is None:
            symbols = load_universe()

        features_list = self.feature_builder.build_all(
            symbols, target_date, self.sector_mapping
        )

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
