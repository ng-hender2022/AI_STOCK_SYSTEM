"""
V4P Price Action Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.price_structure.v4p.feature_builder import (
    PAFeatureBuilder,
    PAFeatures,
    _detect_swing_highs,
    _detect_swing_lows,
    _count_hh_hl_lh_ll,
)
from AI_engine.experts.price_structure.v4p.signal_logic import PASignalLogic, PAOutput
from AI_engine.experts.price_structure.v4p.expert_writer import PAExpertWriter


def _create_test_db(db_path: str, num_days=400, trend="up"):
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
# Swing Detection Unit Tests
# ---------------------------------------------------------------------------

class TestSwingDetection:

    def test_swing_high_basic(self):
        highs = np.array([1, 2, 5, 2, 1, 3, 7, 3, 1, 2])
        idx = _detect_swing_highs(highs, window=2)
        assert 2 in idx  # 5 is a swing high
        assert 6 in idx  # 7 is a swing high

    def test_swing_low_basic(self):
        lows = np.array([5, 3, 1, 3, 5, 4, 2, 4, 6, 3])
        idx = _detect_swing_lows(lows, window=2)
        assert 2 in idx  # 1 is a swing low
        assert 6 in idx  # 2 is a swing low

    def test_no_swings_flat(self):
        highs = np.array([5, 5, 5, 5, 5, 5, 5])
        idx = _detect_swing_highs(highs, window=2)
        assert len(idx) == 0

    def test_hh_hl_count_uptrend(self):
        # Simulated uptrend: higher highs, higher lows
        highs = np.array([1, 3, 5, 3, 1, 2, 4, 7, 4, 2, 3, 5, 9, 5, 3])
        lows = np.array([0, 1, 2, 1, 0, 1, 2, 3, 2, 1, 2, 3, 4, 3, 2])
        sh = _detect_swing_highs(highs, 2)
        sl = _detect_swing_lows(lows, 2)
        hh, hl, lh, ll = _count_hh_hl_lh_ll(highs, lows, sh, sl)
        assert hh >= 1  # should have higher highs
        assert hl >= 0

    def test_lh_ll_count_downtrend(self):
        # Simulated downtrend: lower highs, lower lows
        highs = np.array([10, 8, 9, 7, 5, 6, 7, 5, 3, 4, 5, 3, 1, 2, 3])
        lows = np.array([8, 6, 7, 5, 3, 4, 5, 3, 1, 2, 3, 1, -1, 0, 1])
        sh = _detect_swing_highs(highs, 2)
        sl = _detect_swing_lows(lows, 2)
        hh, hl, lh, ll = _count_hh_hl_lh_ll(highs, lows, sh, sl)
        assert lh >= 1  # should have lower highs
        assert ll >= 0


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestPAFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.close > 0
        assert f.sma20 > 0
        assert f.high20 > 0
        assert f.low20 > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_range_position_bounds(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert 0.0 <= f.range_position <= 1.0

    def test_high20_ge_low20(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.high20 >= f.low20

    def test_swing_counts_nonnegative(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.hh_count >= 0
        assert f.hl_count >= 0
        assert f.lh_count >= 0
        assert f.ll_count >= 0

    def test_trend_structure_valid(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.trend_structure in ("UPTREND", "DOWNTREND", "CONSOLIDATION")

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = PAFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_sma20_slope_type(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert isinstance(f.sma20_slope, float)


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestPASignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PASignalLogic().compute(f)
        assert -4.0 <= o.price_action_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PASignalLogic().compute(f)
        assert abs(o.price_action_norm - o.price_action_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PASignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = PASignalLogic().compute(f)
        assert o.signal_code.startswith("V4P_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = PAFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = PASignalLogic().compute(f)
        o2 = PASignalLogic().compute(f)
        assert o1.price_action_score == o2.price_action_score

    def test_strong_uptrend(self):
        logic = PASignalLogic()
        f = PAFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=110.0, high=111.0, low=109.0,
            hh_count=3, hl_count=3, lh_count=0, ll_count=0,
            trend_structure="UPTREND",
            sma20=105.0, sma20_slope=0.02,
            high20=109.5, low20=95.0,
            range_position=0.95,
            breakout_flag=True, breakdown_flag=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.price_action_score == 4.0  # trend(+2) + breakout(+1) + sma(+1) = 4
        assert o.signal_quality == 4
        assert o.signal_code == "V4P_BULL_BREAK"

    def test_strong_downtrend(self):
        logic = PASignalLogic()
        f = PAFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=85.0, high=86.0, low=84.0,
            hh_count=0, hl_count=0, lh_count=3, ll_count=3,
            trend_structure="DOWNTREND",
            sma20=90.0, sma20_slope=-0.02,
            high20=100.0, low20=85.5,
            range_position=0.03,
            breakout_flag=False, breakdown_flag=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.price_action_score == -4.0  # trend(-2) + breakdown(-1) + sma(-1)
        assert o.signal_quality == 4
        assert o.signal_code == "V4P_BEAR_BREAK"

    def test_consolidation(self):
        logic = PASignalLogic()
        f = PAFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0, high=101.0, low=99.0,
            hh_count=1, hl_count=1, lh_count=1, ll_count=1,
            trend_structure="CONSOLIDATION",
            sma20=100.0, sma20_slope=0.0,
            high20=105.0, low20=95.0,
            range_position=0.5,
            breakout_flag=False, breakdown_flag=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.price_action_score == 0.0
        assert o.signal_code == "V4P_NEUT_CONSOLIDATION"

    def test_bull_reversal(self):
        """Breakout during downtrend = reversal signal."""
        logic = PASignalLogic()
        f = PAFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=106.0, high=107.0, low=105.0,
            hh_count=0, hl_count=0, lh_count=2, ll_count=2,
            trend_structure="DOWNTREND",
            sma20=104.0, sma20_slope=0.01,
            high20=105.5, low20=95.0,
            range_position=0.95,
            breakout_flag=True, breakdown_flag=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4P_BULL_REVERSAL"

    def test_bear_reversal(self):
        """Breakdown during uptrend = reversal signal."""
        logic = PASignalLogic()
        f = PAFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=94.0, high=95.0, low=93.0,
            hh_count=2, hl_count=2, lh_count=0, ll_count=0,
            trend_structure="UPTREND",
            sma20=96.0, sma20_slope=-0.01,
            high20=105.0, low20=94.5,
            range_position=0.05,
            breakout_flag=False, breakdown_flag=True,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4P_BEAR_REVERSAL"

    def test_insufficient_data_returns_zero(self):
        logic = PASignalLogic()
        f = PAFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.price_action_score == 0.0
        assert not o.has_sufficient_data

    def test_valid_signal_codes(self, test_dbs):
        mdb, _ = test_dbs
        valid_codes = {
            "V4P_BULL_BREAK", "V4P_BEAR_BREAK",
            "V4P_BULL_REVERSAL", "V4P_BEAR_REVERSAL",
            "V4P_BULL_TREND", "V4P_BEAR_TREND",
            "V4P_NEUT_CONSOLIDATION",
        }
        for sym in ["FPT", "VNM", "HPG"]:
            f = PAFeatureBuilder(mdb).build(sym, "2025-02-01")
            o = PASignalLogic().compute(f)
            assert o.signal_code in valid_codes, f"{sym}: {o.signal_code}"


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestPAExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = PAExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, PAOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4P'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = PAExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals "
            "WHERE symbol='FPT' AND expert_id='V4P'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_metadata_fields(self, test_dbs):
        mdb, sdb = test_dbs
        w = PAExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4P'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "trend_structure", "hh_count", "hl_count", "lh_count", "ll_count",
            "range_position", "sma20", "sma20_slope", "high20", "low20",
            "breakout_flag", "breakdown_flag", "price_action_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_json_types(self, test_dbs):
        """Ensure numpy types are cast to native Python types for JSON."""
        mdb, sdb = test_dbs
        w = PAExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4P'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        # breakout_flag and breakdown_flag must be native bool (not numpy bool_)
        assert isinstance(meta["breakout_flag"], bool)
        assert isinstance(meta["breakdown_flag"], bool)
        # counts must be int
        assert isinstance(meta["hh_count"], int)
        assert isinstance(meta["hl_count"], int)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = PAExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = PAExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4P'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_bearish_market(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = PAExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        # In a bearish market, score should lean negative
        assert o.price_action_score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
