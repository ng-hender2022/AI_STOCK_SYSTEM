"""
V4SR Support/Resistance Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.price_structure.v4sr.feature_builder import (
    SRFeatureBuilder,
    SRFeatures,
    _detect_swing_highs,
    _detect_swing_lows,
    _atr,
)
from AI_engine.experts.price_structure.v4sr.signal_logic import SRSignalLogic, SROutput
from AI_engine.experts.price_structure.v4sr.expert_writer import SRExpertWriter


def _create_test_db(db_path: str, num_days=500, trend="up"):
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
    for s in ["VNINDEX", "FPT", "VNM", "HPG"]:
        t = 0 if s == "VNINDEX" else 1
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
            (s, s, "HOSE", None, None, t, "2024-01-01", None),
        )

    base = date(2024, 1, 1)
    np.random.seed(42)
    for s in ["FPT", "VNM", "HPG", "VNINDEX"]:
        price = 100.0 if s != "VNINDEX" else 1200.0
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            drift = 0.0006 if trend == "up" else (-0.0006 if trend == "down" else 0)
            price *= 1 + drift + np.random.normal(0, 0.012)
            h = price * (1 + abs(np.random.normal(0, 0.005)) + 0.002)
            l = price * (1 - abs(np.random.normal(0, 0.005)) - 0.002)
            o = price * (1 + np.random.normal(0, 0.003))
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (
                    s,
                    d.isoformat(),
                    round(o, 2),
                    round(h, 2),
                    round(l, 2),
                    round(price, 2),
                    int(np.random.uniform(1e6, 5e6)),
                ),
            )
    conn.commit()
    conn.close()


def _create_signals_db(db_path: str):
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
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def bearish_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, trend="down")
    _create_signals_db(sdb)
    return mdb, sdb


# ---------------------------------------------------------------------------
# ATR Unit Tests
# ---------------------------------------------------------------------------

class TestATR:

    def test_atr_basic(self):
        highs = np.array([12, 13, 14, 13, 15, 14, 16, 15, 14, 13,
                          12, 13, 14, 15, 16], dtype=float)
        lows = np.array([10, 11, 12, 11, 13, 12, 14, 13, 12, 11,
                         10, 11, 12, 13, 14], dtype=float)
        closes = np.array([11, 12, 13, 12, 14, 13, 15, 14, 13, 12,
                           11, 12, 13, 14, 15], dtype=float)
        atr_arr = _atr(highs, lows, closes, 14)
        assert not np.isnan(atr_arr[13])  # first valid at index 13
        assert atr_arr[13] > 0

    def test_atr_nan_padding(self):
        highs = np.array([10, 11, 12, 13, 14], dtype=float)
        lows = np.array([9, 10, 11, 12, 13], dtype=float)
        closes = np.array([9.5, 10.5, 11.5, 12.5, 13.5], dtype=float)
        atr_arr = _atr(highs, lows, closes, 14)
        # Not enough data for ATR(14) with only 5 bars
        assert np.all(np.isnan(atr_arr))


# ---------------------------------------------------------------------------
# Swing Detection Unit Tests
# ---------------------------------------------------------------------------

class TestSwingDetection:

    def test_swing_high_basic(self):
        highs = np.array([1, 2, 3, 5, 3, 2, 1, 3, 7, 3, 1, 2, 3])
        idx = _detect_swing_highs(highs, window=3)
        assert 3 in idx  # 5 is a swing high with 3 bars each side
        assert 8 in idx  # 7 is a swing high

    def test_swing_low_basic(self):
        lows = np.array([5, 4, 3, 1, 3, 4, 5, 4, 2, 4, 6, 5, 4])
        idx = _detect_swing_lows(lows, window=3)
        assert 3 in idx  # 1 is a swing low with 3 bars each side

    def test_no_swings_flat(self):
        highs = np.array([5, 5, 5, 5, 5, 5, 5, 5, 5])
        idx = _detect_swing_highs(highs, window=3)
        assert len(idx) == 0


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestSRFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.has_sufficient_data
        assert f.close > 0
        assert f.atr_value > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_sr_zones_detected(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.num_sr_zones > 0

    def test_support_below_close(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        if f.nearest_support > 0:
            assert f.nearest_support <= f.close

    def test_resistance_above_close(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        if f.nearest_resistance > 0:
            assert f.nearest_resistance >= f.close

    def test_dist_nonnegative(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.dist_to_support >= 0
        assert f.dist_to_resistance >= 0

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2024-03-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = SRFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-06-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_atr_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.atr_value > 0


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestSRSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = SRSignalLogic().compute(f)
        assert -4.0 <= o.sr_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = SRSignalLogic().compute(f)
        assert abs(o.sr_norm - o.sr_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = SRSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = SRSignalLogic().compute(f)
        assert o.signal_code.startswith("V4SR_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = SRFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o1 = SRSignalLogic().compute(f)
        o2 = SRSignalLogic().compute(f)
        assert o1.sr_score == o2.sr_score

    def test_at_strong_support(self):
        logic = SRSignalLogic()
        f = SRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            close=100.0, atr_value=2.0,
            nearest_support=100.0, nearest_resistance=110.0,
            nearest_support_strength=4.0, nearest_resistance_strength=2.0,
            dist_to_support=0.0, dist_to_resistance=0.1,
            num_sr_zones=5,
            support_zone_upper=101.0, support_zone_lower=99.0,
            resistance_zone_upper=111.0, resistance_zone_lower=109.0,
            price_bouncing=True, price_rejecting=False, volume_rising=True,
            breakout_above_resistance=False, breakdown_below_support=False,
            avg_volume=3e6, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == 2.0  # at strong support
        assert o.strength_score > 0     # bullish strength
        assert o.context_score == 1.0   # bounce + volume
        assert o.sr_score >= 3.0
        assert o.signal_code == "V4SR_BULL_BOUNCE"

    def test_at_strong_resistance(self):
        logic = SRSignalLogic()
        f = SRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            close=110.0, atr_value=2.0,
            nearest_support=100.0, nearest_resistance=110.0,
            nearest_support_strength=2.0, nearest_resistance_strength=4.0,
            dist_to_support=0.1, dist_to_resistance=0.0,
            num_sr_zones=5,
            support_zone_upper=101.0, support_zone_lower=99.0,
            resistance_zone_upper=111.0, resistance_zone_lower=109.0,
            price_bouncing=False, price_rejecting=True, volume_rising=True,
            breakout_above_resistance=False, breakdown_below_support=False,
            avg_volume=3e6, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == -2.0  # at strong resistance
        assert o.strength_score < 0      # bearish strength
        assert o.context_score == -1.0   # rejection + volume
        assert o.sr_score <= -3.0
        assert o.signal_code == "V4SR_BEAR_REJECT"

    def test_breakout_above_resistance(self):
        logic = SRSignalLogic()
        f = SRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            close=112.0, atr_value=2.0,
            nearest_support=100.0, nearest_resistance=110.0,
            nearest_support_strength=2.0, nearest_resistance_strength=3.0,
            dist_to_support=0.12, dist_to_resistance=0.0,
            num_sr_zones=4,
            support_zone_upper=101.0, support_zone_lower=99.0,
            resistance_zone_upper=111.0, resistance_zone_lower=109.0,
            price_bouncing=False, price_rejecting=False, volume_rising=False,
            breakout_above_resistance=True, breakdown_below_support=False,
            avg_volume=3e6, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == 2.0
        assert o.signal_code == "V4SR_BULL_BREAK_RESISTANCE"

    def test_breakdown_below_support(self):
        logic = SRSignalLogic()
        f = SRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            close=98.0, atr_value=2.0,
            nearest_support=100.0, nearest_resistance=110.0,
            nearest_support_strength=3.0, nearest_resistance_strength=2.0,
            dist_to_support=0.02, dist_to_resistance=0.12,
            num_sr_zones=4,
            support_zone_upper=101.0, support_zone_lower=99.0,
            resistance_zone_upper=111.0, resistance_zone_lower=109.0,
            price_bouncing=False, price_rejecting=False, volume_rising=False,
            breakout_above_resistance=False, breakdown_below_support=True,
            avg_volume=3e6, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.position_score == -2.0
        assert o.signal_code == "V4SR_BEAR_BREAK_SUPPORT"

    def test_between_levels(self):
        logic = SRSignalLogic()
        f = SRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="2025-05-30",
            close=105.0, atr_value=2.0,
            nearest_support=95.0, nearest_resistance=115.0,
            nearest_support_strength=2.0, nearest_resistance_strength=2.0,
            dist_to_support=0.095, dist_to_resistance=0.095,
            num_sr_zones=4,
            support_zone_upper=96.0, support_zone_lower=94.0,
            resistance_zone_upper=116.0, resistance_zone_lower=114.0,
            price_bouncing=False, price_rejecting=False, volume_rising=False,
            breakout_above_resistance=False, breakdown_below_support=False,
            avg_volume=3e6, has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.sr_score == 0.0
        assert o.signal_code == "V4SR_NEUT_BETWEEN_LEVELS"

    def test_insufficient_data_returns_zero(self):
        logic = SRSignalLogic()
        f = SRFeatures(
            symbol="TEST", date="2025-06-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.sr_score == 0.0
        assert not o.has_sufficient_data

    def test_valid_signal_codes(self, test_dbs):
        mdb, _ = test_dbs
        valid_codes = {
            "V4SR_BULL_AT_SUPPORT", "V4SR_BEAR_AT_RESISTANCE",
            "V4SR_BULL_BREAK_RESISTANCE", "V4SR_BEAR_BREAK_SUPPORT",
            "V4SR_BULL_BOUNCE", "V4SR_BEAR_REJECT",
            "V4SR_NEUT_BETWEEN_LEVELS",
        }
        for sym in ["FPT", "VNM", "HPG"]:
            f = SRFeatureBuilder(mdb).build(sym, "2025-06-01")
            o = SRSignalLogic().compute(f)
            assert o.signal_code in valid_codes, f"{sym}: {o.signal_code}"


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestSRExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = SRExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        assert isinstance(o, SROutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4SR'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = SRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals "
            "WHERE symbol='FPT' AND expert_id='V4SR'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_metadata_fields(self, test_dbs):
        mdb, sdb = test_dbs
        w = SRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4SR'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "nearest_support", "nearest_resistance",
            "nearest_support_strength", "nearest_resistance_strength",
            "dist_to_support", "dist_to_resistance",
            "num_sr_zones", "atr_value", "sr_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_json_types(self, test_dbs):
        """Ensure numpy types are cast to native Python types for JSON."""
        mdb, sdb = test_dbs
        w = SRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4SR'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        # Boolean fields must be native bool (not numpy bool_)
        assert isinstance(meta["breakout_above_resistance"], bool)
        assert isinstance(meta["breakdown_below_support"], bool)
        assert isinstance(meta["volume_rising"], bool)
        # int fields
        assert isinstance(meta["num_sr_zones"], int)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = SRExpertWriter(mdb, sdb)
        results = w.run_all("2025-06-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = SRExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        w.run_symbol("FPT", "2025-06-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' "
            "AND date='2025-06-01' AND expert_id='V4SR'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_bearish_market(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = SRExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        # In a bearish market, score should lean negative or neutral
        assert o.sr_score <= 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
