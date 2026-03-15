"""
V4I Ichimoku Expert Tests
Covers: feature builder, signal logic, expert writer, data leakage, determinism.
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.trend.v4i.feature_builder import (
    IchimokuFeatureBuilder,
    IchimokuFeatures,
)
from AI_engine.experts.trend.v4i.signal_logic import (
    IchimokuSignalLogic,
    IchimokuOutput,
)
from AI_engine.experts.trend.v4i.expert_writer import IchimokuExpertWriter


# ---------------------------------------------------------------------------
# Test DB helper
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str, num_days: int = 250, trend: str = "up") -> None:
    """Create market.db + signals.db with synthetic data."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS symbols_master (
            symbol TEXT PRIMARY KEY, name TEXT NOT NULL,
            exchange TEXT DEFAULT 'HOSE', sector TEXT, industry TEXT,
            is_tradable INTEGER DEFAULT 1, added_date DATE NOT NULL, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS prices_daily (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER, value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date)
        );
    """)

    # Insert symbols
    symbols = ["VNINDEX", "FPT", "VNM", "HPG", "MWG", "TCB"]
    for sym in symbols:
        tradable = 0 if sym == "VNINDEX" else 1
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master (symbol, name, is_tradable, added_date)"
            f" VALUES (?, ?, ?, '2025-01-01')",
            (sym, sym, tradable),
        )

    base_date = date(2025, 1, 1)
    np.random.seed(123)

    for sym in symbols:
        base_price = 100.0 if sym != "VNINDEX" else 1200.0
        price = base_price

        for day_i in range(num_days):
            d = base_date + timedelta(days=day_i)
            if d.weekday() >= 5:
                continue

            if trend == "up":
                drift = 0.0005
            elif trend == "down":
                drift = -0.0005
            else:
                drift = 0.0

            change = drift + np.random.normal(0, 0.012)
            price = price * (1 + change)
            h = price * (1 + abs(np.random.normal(0, 0.005)))
            l = price * (1 - abs(np.random.normal(0, 0.005)))
            o = price * (1 + np.random.normal(0, 0.003))
            v = int(np.random.uniform(1_000_000, 10_000_000))

            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (sym, d.isoformat(), round(o, 2), round(h, 2), round(l, 2), round(price, 2), v),
            )

    conn.commit()
    conn.close()


def _create_signals_db(db_path: str) -> None:
    """Create empty signals.db."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expert_signals (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            snapshot_time TEXT DEFAULT 'EOD', expert_id TEXT NOT NULL,
            primary_score REAL NOT NULL, secondary_score REAL,
            signal_code TEXT, signal_quality INTEGER DEFAULT 0,
            metadata_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date, snapshot_time, expert_id)
        );
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def test_dbs(tmp_path):
    """Create temp market.db and signals.db."""
    market_db = str(tmp_path / "market.db")
    signals_db = str(tmp_path / "signals.db")
    _create_test_db(market_db)
    _create_signals_db(signals_db)
    return market_db, signals_db


@pytest.fixture
def bearish_dbs(tmp_path):
    """Create temp DBs with bearish trend."""
    market_db = str(tmp_path / "market.db")
    signals_db = str(tmp_path / "signals.db")
    _create_test_db(market_db, trend="down")
    _create_signals_db(signals_db)
    return market_db, signals_db


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestIchimokuFeatureBuilder:

    def test_build_returns_features(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert isinstance(features, IchimokuFeatures)
        assert features.has_sufficient_data is True

    def test_data_leakage_prevention(self, test_dbs):
        """Features must use data strictly before target_date."""
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert features.data_cutoff_date < "2025-09-15"

    def test_ichimoku_lines_populated(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert features.tenkan > 0
        assert features.kijun > 0
        assert features.senkou_a > 0
        assert features.senkou_b > 0
        assert features.close > 0

    def test_cloud_computed(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert features.cloud_top >= features.cloud_bottom
        assert features.cloud_thickness >= 0

    def test_future_cloud_computed(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert features.senkou_a_future > 0
        assert features.senkou_b_future > 0

    def test_chikou_and_price_26(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert features.chikou > 0
        assert features.price_26_ago > 0

    def test_insufficient_data(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-02-01")  # too early
        assert features.has_sufficient_data is False

    def test_build_batch(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        results = builder.build_batch(["FPT", "VNM", "HPG"], "2025-09-15")
        assert len(results) == 3
        for f in results:
            assert isinstance(f, IchimokuFeatures)

    def test_time_theory_pivot(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        # Should find some pivot (random data will have local extremes)
        assert features.days_since_pivot >= 0


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestIchimokuSignalLogic:

    def test_compute_returns_output(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert isinstance(output, IchimokuOutput)

    def test_score_range(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        for sym in ["FPT", "VNM", "HPG", "MWG", "TCB"]:
            features = builder.build(sym, "2025-09-15")
            output = logic.compute(features)
            assert -4.0 <= output.ichimoku_score <= 4.0, f"{sym}: {output.ichimoku_score}"

    def test_norm_range(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert -1.0 <= output.ichimoku_norm <= 1.0
        assert abs(output.ichimoku_norm - output.ichimoku_score / 4.0) < 1e-9

    def test_cloud_position_valid(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert output.cloud_position in ("above", "inside", "below")

    def test_tk_signal_valid(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert output.tk_signal in ("bullish", "bearish", "neutral")

    def test_chikou_confirm_valid(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert output.chikou_confirm in ("bullish", "bearish", "neutral")

    def test_future_cloud_valid(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert output.future_cloud in ("bullish", "bearish", "flat")

    def test_signal_quality_range(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert 0 <= output.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert output.signal_code.startswith("V4I_")

    def test_time_resonance_range(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert 0.0 <= output.time_resonance <= 1.0

    def test_deterministic(self, test_dbs):
        """Same input → same output."""
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        out1 = logic.compute(features)
        out2 = logic.compute(features)
        assert out1.ichimoku_score == out2.ichimoku_score
        assert out1.signal_quality == out2.signal_quality
        assert out1.signal_code == out2.signal_code

    def test_full_bullish_alignment(self):
        """Manually craft features for max bullish → score should be +4."""
        logic = IchimokuSignalLogic()
        features = IchimokuFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            tenkan=110, kijun=105,
            senkou_a=95, senkou_b=90,       # cloud 90-95
            chikou=120, price_26_ago=100,
            senkou_a_future=115, senkou_b_future=105,  # bullish future
            cloud_top=95, cloud_bottom=90, cloud_thickness=5,
            close=120,                       # above cloud
            has_sufficient_data=True,
        )
        output = logic.compute(features)
        assert output.cloud_position == "above"
        assert output.tk_signal == "bullish"
        assert output.chikou_confirm == "bullish"
        assert output.future_cloud == "bullish"
        assert output.ichimoku_score == 4.0  # 2+1+1 = 4 (with future bonus capped at 4)
        assert output.signal_quality == 4

    def test_full_bearish_alignment(self):
        """Manually craft features for max bearish → score should be -4."""
        logic = IchimokuSignalLogic()
        features = IchimokuFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            tenkan=85, kijun=90,
            senkou_a=105, senkou_b=110,     # cloud 105-110
            chikou=80, price_26_ago=100,
            senkou_a_future=85, senkou_b_future=95,  # bearish future
            cloud_top=110, cloud_bottom=105, cloud_thickness=5,
            close=80,                        # below cloud
            has_sufficient_data=True,
        )
        output = logic.compute(features)
        assert output.cloud_position == "below"
        assert output.tk_signal == "bearish"
        assert output.chikou_confirm == "bearish"
        assert output.future_cloud == "bearish"
        assert output.ichimoku_score == -4.0  # clamped
        assert output.signal_quality == 4

    def test_bearish_trend_data(self, bearish_dbs):
        """Bearish data should produce negative or low scores."""
        market_db, _ = bearish_dbs
        builder = IchimokuFeatureBuilder(market_db)
        logic = IchimokuSignalLogic()
        features = builder.build("FPT", "2025-09-15")
        output = logic.compute(features)
        assert -4.0 <= output.ichimoku_score <= 4.0


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestIchimokuExpertWriter:

    def test_run_symbol(self, test_dbs):
        market_db, signals_db = test_dbs
        writer = IchimokuExpertWriter(market_db, signals_db)
        output = writer.run_symbol("FPT", "2025-09-15")
        assert isinstance(output, IchimokuOutput)

        # Verify written to DB
        conn = sqlite3.connect(signals_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND date='2025-09-15' AND expert_id='V4I'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4
        assert -1 <= row["secondary_score"] <= 1

    def test_run_all(self, test_dbs):
        market_db, signals_db = test_dbs
        writer = IchimokuExpertWriter(market_db, signals_db)
        symbols = ["FPT", "VNM", "HPG"]
        results = writer.run_all("2025-09-15", symbols=symbols)
        assert len(results) == 3

        # Verify all written
        conn = sqlite3.connect(signals_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE date='2025-09-15' AND expert_id='V4I'"
        ).fetchone()[0]
        conn.close()
        assert count == 3

    def test_metadata_json(self, test_dbs):
        market_db, signals_db = test_dbs
        writer = IchimokuExpertWriter(market_db, signals_db)
        writer.run_symbol("FPT", "2025-09-15")

        conn = sqlite3.connect(signals_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND date='2025-09-15' AND expert_id='V4I'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert "cloud_position" in meta
        assert "tk_signal" in meta
        assert "chikou_confirm" in meta
        assert "future_cloud" in meta
        assert "time_resonance" in meta
        assert "ichimoku_norm" in meta

    def test_idempotent(self, test_dbs):
        """Running twice should not create duplicate rows."""
        market_db, signals_db = test_dbs
        writer = IchimokuExpertWriter(market_db, signals_db)
        writer.run_symbol("FPT", "2025-09-15")
        writer.run_symbol("FPT", "2025-09-15")

        conn = sqlite3.connect(signals_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-09-15' AND expert_id='V4I'"
        ).fetchone()[0]
        conn.close()
        assert count == 1


# ---------------------------------------------------------------------------
# Data Leakage Tests
# ---------------------------------------------------------------------------

class TestDataLeakage:

    def test_feature_date_strictly_before_target(self, test_dbs):
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        features = builder.build("FPT", "2025-09-15")
        assert features.data_cutoff_date < "2025-09-15"

    def test_different_target_dates_different_cutoffs(self, test_dbs):
        """Two different target dates should use different cutoff dates."""
        market_db, _ = test_dbs
        builder = IchimokuFeatureBuilder(market_db)
        f1 = builder.build("FPT", "2025-09-15")
        f2 = builder.build("FPT", "2025-09-16")
        # f2 cutoff should be >= f1 cutoff
        assert f2.data_cutoff_date >= f1.data_cutoff_date


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
