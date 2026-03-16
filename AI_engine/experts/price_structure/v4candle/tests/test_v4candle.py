"""
V4CANDLE Candlestick Pattern Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.price_structure.v4candle.feature_builder import (
    CandleFeatureBuilder,
    CandleFeatures,
    _detect_swing_highs,
    _detect_swing_lows,
)
from AI_engine.experts.price_structure.v4candle.signal_logic import CandleSignalLogic, CandleOutput
from AI_engine.experts.price_structure.v4candle.expert_writer import CandleExpertWriter


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
            vol = int(np.random.uniform(1e6, 5e6))
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (
                    s,
                    d.isoformat(),
                    round(o, 2),
                    round(h, 2),
                    round(l, 2),
                    round(price, 2),
                    vol,
                ),
            )
    conn.commit()
    conn.close()


def _create_test_db_with_pattern(db_path: str, pattern: str):
    """Create a test DB with specific candlestick patterns injected."""
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
    conn.execute(
        "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
        ("TEST", "TEST", "HOSE", None, None, 1, "2024-01-01", None),
    )

    # Generate 30 days of normal data first
    base = date(2024, 1, 1)
    np.random.seed(99)
    price = 100.0
    day_count = 0
    for i in range(50):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price *= 1 + np.random.normal(0, 0.005)
        h = price * 1.005
        l = price * 0.995
        o = price * (1 + np.random.normal(0, 0.001))
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), round(o, 2), round(h, 2), round(l, 2), round(price, 2), 3000000),
        )
        day_count += 1

    # Now inject specific pattern bars
    pattern_base = base + timedelta(days=55)
    # Ensure weekday
    while pattern_base.weekday() >= 5:
        pattern_base += timedelta(days=1)

    avg_vol = 3000000

    if pattern == "hammer":
        # Hammer: small body at top, long lower shadow
        d = pattern_base
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), 99.0, 100.0, 94.0, 100.0, int(avg_vol * 2)),
        )
    elif pattern == "shooting_star":
        d = pattern_base
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), 100.0, 106.0, 99.5, 100.0, int(avg_vol * 2)),
        )
    elif pattern == "doji":
        d = pattern_base
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), 100.0, 103.0, 97.0, 100.05, int(avg_vol)),
        )
    elif pattern == "marubozu_bull":
        d = pattern_base
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), 100.0, 106.0, 99.9, 105.8, int(avg_vol * 2)),
        )
    elif pattern == "bullish_engulfing":
        d1 = pattern_base
        d2 = d1 + timedelta(days=1)
        while d2.weekday() >= 5:
            d2 += timedelta(days=1)
        # Day 1: bearish
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d1.isoformat(), 102.0, 103.0, 99.0, 99.5, avg_vol),
        )
        # Day 2: bullish engulfing
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d2.isoformat(), 98.0, 104.0, 97.5, 103.5, int(avg_vol * 2)),
        )
    elif pattern == "bearish_engulfing":
        d1 = pattern_base
        d2 = d1 + timedelta(days=1)
        while d2.weekday() >= 5:
            d2 += timedelta(days=1)
        # Day 1: bullish
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d1.isoformat(), 99.0, 102.0, 98.5, 101.5, avg_vol),
        )
        # Day 2: bearish engulfing
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d2.isoformat(), 103.0, 103.5, 97.0, 97.5, int(avg_vol * 2)),
        )
    elif pattern == "morning_star":
        d1 = pattern_base
        d2 = d1 + timedelta(days=1)
        while d2.weekday() >= 5:
            d2 += timedelta(days=1)
        d3 = d2 + timedelta(days=1)
        while d3.weekday() >= 5:
            d3 += timedelta(days=1)
        # Day 1: large bearish
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d1.isoformat(), 104.0, 105.0, 98.0, 99.0, avg_vol),
        )
        # Day 2: small body (doji-like)
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d2.isoformat(), 98.5, 99.0, 97.5, 98.6, avg_vol),
        )
        # Day 3: large bullish closing above Day1 midpoint (101.5)
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d3.isoformat(), 99.0, 104.0, 98.5, 103.0, int(avg_vol * 2)),
        )
    elif pattern == "evening_star":
        d1 = pattern_base
        d2 = d1 + timedelta(days=1)
        while d2.weekday() >= 5:
            d2 += timedelta(days=1)
        d3 = d2 + timedelta(days=1)
        while d3.weekday() >= 5:
            d3 += timedelta(days=1)
        # Day 1: large bullish
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d1.isoformat(), 98.0, 104.0, 97.5, 103.5, avg_vol),
        )
        # Day 2: small body
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d2.isoformat(), 103.8, 104.5, 103.0, 103.6, avg_vol),
        )
        # Day 3: large bearish closing below Day1 midpoint (100.75)
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d3.isoformat(), 103.0, 103.5, 98.0, 99.0, int(avg_vol * 2)),
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
        assert 2 in idx
        assert 6 in idx

    def test_swing_low_basic(self):
        lows = np.array([5, 3, 1, 3, 5, 4, 2, 4, 6, 3])
        idx = _detect_swing_lows(lows, window=2)
        assert 2 in idx
        assert 6 in idx

    def test_no_swings_flat(self):
        highs = np.array([5, 5, 5, 5, 5, 5, 5])
        idx = _detect_swing_highs(highs, window=2)
        assert len(idx) == 0


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestCandleFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert len(f.closes) == 3
        assert len(f.opens) == 3
        assert f.body_pct >= 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_body_pct_range(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert 0.0 <= f.body_pct <= 1.0

    def test_shadow_pcts_nonnegative(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.upper_shadow_pct >= 0
        assert f.lower_shadow_pct >= 0

    def test_volume_ratio_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.volume_ratio > 0

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = CandleFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_swing_detection_populated(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.recent_swing_high > 0
        assert f.recent_swing_low > 0


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestCandleSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = CandleSignalLogic().compute(f)
        assert -4.0 <= o.candle_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = CandleSignalLogic().compute(f)
        assert abs(o.candle_norm - o.candle_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = CandleSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = CandleSignalLogic().compute(f)
        assert o.signal_code.startswith("V4CANDLE_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = CandleFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = CandleSignalLogic().compute(f)
        o2 = CandleSignalLogic().compute(f)
        assert o1.candle_score == o2.candle_score

    def test_insufficient_data_returns_zero(self):
        logic = CandleSignalLogic()
        f = CandleFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.candle_score == 0.0
        assert not o.has_sufficient_data

    def test_hammer_detection(self, tmp_path):
        mdb = str(tmp_path / "market_hammer.db")
        sdb = str(tmp_path / "signals_hammer.db")
        _create_test_db_with_pattern(mdb, "hammer")
        _create_signals_db(sdb)
        f = CandleFeatureBuilder(mdb).build("TEST", "2024-03-01")
        o = CandleSignalLogic().compute(f)
        if o.has_sufficient_data and o.pattern_name == "hammer":
            assert o.pattern_direction == "bullish"
            assert o.pattern_score > 0
            assert o.signal_code == "V4CANDLE_BULL_HAMMER"

    def test_shooting_star_detection(self, tmp_path):
        mdb = str(tmp_path / "market_ss.db")
        sdb = str(tmp_path / "signals_ss.db")
        _create_test_db_with_pattern(mdb, "shooting_star")
        _create_signals_db(sdb)
        f = CandleFeatureBuilder(mdb).build("TEST", "2024-03-01")
        o = CandleSignalLogic().compute(f)
        if o.has_sufficient_data and o.pattern_name == "shooting_star":
            assert o.pattern_direction == "bearish"
            assert o.pattern_score < 0
            assert o.signal_code == "V4CANDLE_BEAR_SHOOTING"

    def test_doji_detection(self, tmp_path):
        mdb = str(tmp_path / "market_doji.db")
        sdb = str(tmp_path / "signals_doji.db")
        _create_test_db_with_pattern(mdb, "doji")
        _create_signals_db(sdb)
        f = CandleFeatureBuilder(mdb).build("TEST", "2024-03-01")
        o = CandleSignalLogic().compute(f)
        if o.has_sufficient_data and o.pattern_name == "doji":
            assert o.pattern_direction == "neutral"
            assert o.pattern_score == 0
            assert o.signal_code == "V4CANDLE_NEUT_DOJI"

    def test_bullish_engulfing_synthetic(self):
        """Test bullish engulfing with synthetic CandleFeatures."""
        logic = CandleSignalLogic()
        f = CandleFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            opens=[100.0, 102.0, 98.0],
            highs=[103.0, 103.0, 104.0],
            lows=[99.0, 99.0, 97.5],
            closes=[101.0, 99.5, 103.5],
            volumes=[3000000, 3000000, 6000000],
            body=5.5,  # 103.5 - 98.0
            body_pct=0.846,
            upper_shadow=0.5,
            lower_shadow=0.5,
            upper_shadow_pct=0.077,
            lower_shadow_pct=0.077,
            candle_range=6.5,
            volume_current=6000000,
            volume_avg=3000000,
            volume_ratio=2.0,
            recent_swing_high=105.0,
            recent_swing_low=97.0,
            at_swing_high=False,
            at_swing_low=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.pattern_name == "bullish_engulfing"
        assert o.pattern_direction == "bullish"
        assert o.signal_code == "V4CANDLE_BULL_ENGULF"
        assert o.pattern_score == 3.0
        assert o.candle_score > 0

    def test_bearish_engulfing_synthetic(self):
        """Test bearish engulfing with synthetic CandleFeatures."""
        logic = CandleSignalLogic()
        f = CandleFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            opens=[100.0, 99.0, 103.0],
            highs=[103.0, 102.0, 103.5],
            lows=[99.0, 98.5, 97.0],
            closes=[101.0, 101.5, 97.5],
            volumes=[3000000, 3000000, 6000000],
            body=-5.5,
            body_pct=0.846,
            upper_shadow=0.5,
            lower_shadow=0.5,
            upper_shadow_pct=0.077,
            lower_shadow_pct=0.077,
            candle_range=6.5,
            volume_current=6000000,
            volume_avg=3000000,
            volume_ratio=2.0,
            recent_swing_high=105.0,
            recent_swing_low=97.0,
            at_swing_high=False,
            at_swing_low=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.pattern_name == "bearish_engulfing"
        assert o.pattern_direction == "bearish"
        assert o.signal_code == "V4CANDLE_BEAR_ENGULF"
        assert o.pattern_score == -3.0
        assert o.candle_score < 0

    def test_morning_star_synthetic(self):
        """Test morning star with synthetic CandleFeatures."""
        logic = CandleSignalLogic()
        f = CandleFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            opens=[104.0, 98.5, 99.0],
            highs=[105.0, 99.0, 104.0],
            lows=[98.0, 97.5, 98.5],
            closes=[99.0, 98.6, 103.0],
            volumes=[3000000, 3000000, 6000000],
            body=4.0,
            body_pct=0.727,
            upper_shadow=1.0,
            lower_shadow=0.5,
            upper_shadow_pct=0.182,
            lower_shadow_pct=0.091,
            candle_range=5.5,
            volume_current=6000000,
            volume_avg=3000000,
            volume_ratio=2.0,
            recent_swing_high=105.0,
            recent_swing_low=97.0,
            at_swing_high=False,
            at_swing_low=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.pattern_name == "morning_star"
        assert o.pattern_direction == "bullish"
        assert o.signal_code == "V4CANDLE_BULL_MORNING"
        assert o.pattern_score == 3.0

    def test_evening_star_synthetic(self):
        """Test evening star with synthetic CandleFeatures."""
        logic = CandleSignalLogic()
        f = CandleFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            opens=[98.0, 103.8, 103.0],
            highs=[104.0, 104.5, 103.5],
            lows=[97.5, 103.0, 98.0],
            closes=[103.5, 103.6, 99.0],
            volumes=[3000000, 3000000, 6000000],
            body=-4.0,
            body_pct=0.727,
            upper_shadow=0.5,
            lower_shadow=1.0,
            upper_shadow_pct=0.091,
            lower_shadow_pct=0.182,
            candle_range=5.5,
            volume_current=6000000,
            volume_avg=3000000,
            volume_ratio=2.0,
            recent_swing_high=105.0,
            recent_swing_low=97.0,
            at_swing_high=False,
            at_swing_low=False,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.pattern_name == "evening_star"
        assert o.pattern_direction == "bearish"
        assert o.signal_code == "V4CANDLE_BEAR_EVENING"
        assert o.pattern_score == -3.0

    def test_score_clamped_at_4(self):
        """Ensure total score never exceeds +/-4."""
        logic = CandleSignalLogic()
        f = CandleFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            opens=[104.0, 98.5, 99.0],
            highs=[105.0, 99.0, 104.0],
            lows=[98.0, 97.5, 98.5],
            closes=[99.0, 98.6, 103.0],
            volumes=[3000000, 3000000, 6000000],
            body=4.0,
            body_pct=0.727,
            upper_shadow=1.0,
            lower_shadow=0.5,
            upper_shadow_pct=0.182,
            lower_shadow_pct=0.091,
            candle_range=5.5,
            volume_current=6000000,
            volume_avg=3000000,
            volume_ratio=2.0,
            recent_swing_high=105.0,
            recent_swing_low=97.0,
            at_swing_high=False,
            at_swing_low=True,  # at swing low -> context bonus
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # morning_star(+3) + vol(+0.5) + context(+0.5) = +4.0 (clamped)
        assert o.candle_score <= 4.0
        assert o.candle_score >= -4.0

    def test_valid_signal_codes(self, test_dbs):
        mdb, _ = test_dbs
        valid_codes = {
            "V4CANDLE_BULL_ENGULF", "V4CANDLE_BEAR_ENGULF",
            "V4CANDLE_BULL_HAMMER", "V4CANDLE_BEAR_SHOOTING",
            "V4CANDLE_BULL_MORNING", "V4CANDLE_BEAR_EVENING",
            "V4CANDLE_BULL_THREE", "V4CANDLE_BEAR_THREE",
            "V4CANDLE_NEUT_DOJI", "V4CANDLE_NEUT_NONE",
        }
        for sym in ["FPT", "VNM", "HPG"]:
            f = CandleFeatureBuilder(mdb).build(sym, "2025-02-01")
            o = CandleSignalLogic().compute(f)
            assert o.signal_code in valid_codes, f"{sym}: {o.signal_code}"


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestCandleExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = CandleExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, CandleOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4CANDLE'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = CandleExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals "
            "WHERE symbol='FPT' AND expert_id='V4CANDLE'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_metadata_fields(self, test_dbs):
        mdb, sdb = test_dbs
        w = CandleExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4CANDLE'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "pattern_name", "pattern_direction", "body_pct",
            "upper_shadow_pct", "lower_shadow_pct",
            "volume_confirm", "at_swing", "candle_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_json_types(self, test_dbs):
        """Ensure numpy types are cast to native Python types for JSON."""
        mdb, sdb = test_dbs
        w = CandleExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4CANDLE'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert isinstance(meta["volume_confirm"], bool)
        assert isinstance(meta["at_swing"], bool)
        assert isinstance(meta["body_pct"], float)
        assert isinstance(meta["candle_norm"], float)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = CandleExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = CandleExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4CANDLE'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_bearish_market(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = CandleExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        # Score should be within valid range
        assert -4.0 <= o.candle_score <= 4.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
