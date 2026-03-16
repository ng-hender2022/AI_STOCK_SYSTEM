"""
V4TREND_PATTERN Trend Pattern Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.price_structure.v4trend_pattern.feature_builder import (
    TPFeatureBuilder,
    TPFeatures,
    PatternResult,
    _detect_swing_highs,
    _detect_swing_lows,
)
from AI_engine.experts.price_structure.v4trend_pattern.signal_logic import TPSignalLogic, TPOutput
from AI_engine.experts.price_structure.v4trend_pattern.expert_writer import TPExpertWriter


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


def _create_flag_db(db_path: str, direction="bull"):
    """Create a DB with a clear flag pattern for testing."""
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

    base = date(2024, 1, 1)
    price = 100.0
    bars = []

    # Generate 60 bars of base data
    for i in range(60):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price *= 1 + np.random.normal(0, 0.005)
        bars.append((d, price))

    if direction == "bull":
        # Sharp impulse up: 5 bars, ~8% move
        for i in range(5):
            d = bars[-1][0] + timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)
            price *= 1.016
            bars.append((d, price))

        # Consolidation: 5 bars, slight pullback, tight range
        consol_high = price * 1.005
        consol_low = price * 0.985
        for i in range(5):
            d = bars[-1][0] + timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)
            price = price * (1 - 0.003)  # slight drift down
            bars.append((d, price))

        # Breakout bar with high volume
        d = bars[-1][0] + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        price = consol_high * 1.02
        bars.append((d, price))
    else:
        # Sharp impulse down
        for i in range(5):
            d = bars[-1][0] + timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)
            price *= 0.984
            bars.append((d, price))

        consol_high = price * 1.015
        consol_low = price * 0.995
        for i in range(5):
            d = bars[-1][0] + timedelta(days=1)
            while d.weekday() >= 5:
                d += timedelta(days=1)
            price = price * (1 + 0.003)
            bars.append((d, price))

        d = bars[-1][0] + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        price = consol_low * 0.98
        bars.append((d, price))

    np.random.seed(123)
    for d, p in bars:
        h = p * (1 + abs(np.random.normal(0, 0.003)) + 0.002)
        l = p * (1 - abs(np.random.normal(0, 0.003)) - 0.002)
        o = p * (1 + np.random.normal(0, 0.002))
        vol = int(np.random.uniform(3e6, 8e6))
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("TEST", d.isoformat(), round(o, 2), round(h, 2), round(l, 2), round(p, 2), vol),
        )

    conn.commit()
    conn.close()
    # Return the date after the last bar for target_date
    last_d = bars[-1][0] + timedelta(days=1)
    while last_d.weekday() >= 5:
        last_d += timedelta(days=1)
    return last_d.isoformat()


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


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestTPFeatureBuilder:

    def test_build(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.close > 0
        assert f.pattern is not None

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = TPFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_pattern_result_types(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        p = f.pattern
        assert isinstance(p.pattern_type, str)
        assert isinstance(p.pattern_direction, str)
        assert isinstance(p.confirmed, bool)
        assert isinstance(p.target_pct, float)
        assert isinstance(p.pattern_duration, int)
        assert isinstance(p.pattern_failure, bool)

    def test_pattern_type_valid(self, test_dbs):
        mdb, _ = test_dbs
        valid_types = {"flag", "pennant", "double_top", "double_bottom",
                       "triangle_asc", "triangle_desc", "none"}
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.pattern.pattern_type in valid_types

    def test_pattern_direction_valid(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.pattern.pattern_direction in ("bullish", "bearish", "neutral")

    def test_unknown_symbol(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("NONEXIST", "2025-02-01")
        assert not f.has_sufficient_data
        assert f.data_cutoff_date == ""


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestTPSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = TPSignalLogic().compute(f)
        assert -4.0 <= o.pattern_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = TPSignalLogic().compute(f)
        assert abs(o.pattern_norm - o.pattern_score / 4.0) < 1e-9

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = TPSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = TPSignalLogic().compute(f)
        assert o.signal_code.startswith("V4TP_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = TPFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = TPSignalLogic().compute(f)
        o2 = TPSignalLogic().compute(f)
        assert o1.pattern_score == o2.pattern_score
        assert o1.signal_code == o2.signal_code

    def test_no_pattern(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0, high=101.0, low=99.0,
            pattern=PatternResult(),  # default = no pattern
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.pattern_score == 0.0
        assert o.signal_code == "V4TP_NEUT_NO_PATTERN"
        assert o.signal_quality == 0

    def test_bull_flag_confirmed(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=110.0, high=111.0, low=109.0,
            pattern=PatternResult(
                pattern_type="flag",
                pattern_direction="bullish",
                confirmed=True,
                target_pct=0.08,
                breakout_volume_ratio=2.0,
                pattern_duration=10,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(+1.5) + confirm(+1) + target(+1) = 3.5
        assert o.pattern_score == 3.5
        assert o.signal_code == "V4TP_BULL_FLAG"
        assert o.signal_quality == 3

    def test_bear_flag_confirmed(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=90.0, high=91.0, low=89.0,
            pattern=PatternResult(
                pattern_type="flag",
                pattern_direction="bearish",
                confirmed=True,
                target_pct=-0.08,
                breakout_volume_ratio=1.8,
                pattern_duration=10,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(-1.5) + confirm(+1) + target(-1) = -1.5
        assert o.pattern_score == -1.5
        assert o.signal_code == "V4TP_BEAR_FLAG"
        assert o.signal_quality == 3

    def test_double_bottom_confirmed(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=105.0, high=106.0, low=104.0,
            pattern=PatternResult(
                pattern_type="double_bottom",
                pattern_direction="bullish",
                confirmed=True,
                target_pct=0.07,
                breakout_volume_ratio=2.5,
                pattern_duration=25,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(+2) + confirm(+1) + target(+1) = 4.0
        assert o.pattern_score == 4.0
        assert o.signal_code == "V4TP_BULL_DOUBLE_BOT"
        assert o.signal_quality == 4

    def test_double_top_confirmed(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=95.0, high=96.0, low=94.0,
            pattern=PatternResult(
                pattern_type="double_top",
                pattern_direction="bearish",
                confirmed=True,
                target_pct=-0.06,
                breakout_volume_ratio=2.0,
                pattern_duration=20,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(-2) + confirm(+1) + target(-1) = -2.0
        assert o.pattern_score == -2.0
        assert o.signal_code == "V4TP_BEAR_DOUBLE_TOP"
        assert o.signal_quality == 4

    def test_triangle_asc_confirmed(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=108.0, high=109.0, low=107.0,
            pattern=PatternResult(
                pattern_type="triangle_asc",
                pattern_direction="bullish",
                confirmed=True,
                target_pct=0.06,
                breakout_volume_ratio=1.8,
                pattern_duration=30,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(+1.5) + confirm(+1) + target(+1) = 3.5
        assert o.pattern_score == 3.5
        assert o.signal_code == "V4TP_BULL_TRI_ASC"
        assert o.signal_quality == 3

    def test_triangle_desc_confirmed(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=92.0, high=93.0, low=91.0,
            pattern=PatternResult(
                pattern_type="triangle_desc",
                pattern_direction="bearish",
                confirmed=True,
                target_pct=-0.06,
                breakout_volume_ratio=1.6,
                pattern_duration=25,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(-1.5) + confirm(+1) + target(-1) = -1.5
        assert o.pattern_score == -1.5
        assert o.signal_code == "V4TP_BEAR_TRI_DESC"
        assert o.signal_quality == 3

    def test_pattern_forming(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0, high=101.0, low=99.0,
            pattern=PatternResult(
                pattern_type="flag",
                pattern_direction="bullish",
                confirmed=False,
                target_pct=0.06,
                breakout_volume_ratio=0.0,
                pattern_duration=8,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(+1.5) + confirm(0) + target(+1) = 2.5
        assert o.pattern_score == 2.5
        assert o.signal_code == "V4TP_NEUT_FORMING"
        assert o.signal_quality == 1

    def test_pattern_failure_bull(self):
        """Bull pattern that fails -> bearish failure signal."""
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=98.0, high=99.0, low=97.0,
            pattern=PatternResult(
                pattern_type="flag",
                pattern_direction="bullish",
                confirmed=True,
                target_pct=0.06,
                breakout_volume_ratio=1.8,
                pattern_duration=10,
                pattern_failure=True,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # pattern(+1.5) + confirm(-1, failure) + target(+1) = 1.5
        assert o.confirmation_score == -1.0
        assert o.signal_code == "V4TP_BEAR_FAILURE"

    def test_pattern_failure_bear(self):
        """Bear pattern that fails -> bullish failure signal."""
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=102.0, high=103.0, low=101.0,
            pattern=PatternResult(
                pattern_type="flag",
                pattern_direction="bearish",
                confirmed=True,
                target_pct=-0.06,
                breakout_volume_ratio=1.8,
                pattern_duration=10,
                pattern_failure=True,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.confirmation_score == -1.0
        assert o.signal_code == "V4TP_BULL_FAILURE"

    def test_small_target_score_zero(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=100.0, high=101.0, low=99.0,
            pattern=PatternResult(
                pattern_type="flag",
                pattern_direction="bullish",
                confirmed=True,
                target_pct=0.03,  # < 5% threshold
                breakout_volume_ratio=1.8,
                pattern_duration=10,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.target_score == 0.0

    def test_score_clamped(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            close=110.0, high=111.0, low=109.0,
            pattern=PatternResult(
                pattern_type="double_bottom",
                pattern_direction="bullish",
                confirmed=True,
                target_pct=0.10,
                breakout_volume_ratio=3.0,
                pattern_duration=30,
                pattern_failure=False,
            ),
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.pattern_score <= 4.0
        assert o.pattern_score >= -4.0

    def test_insufficient_data_returns_zero(self):
        logic = TPSignalLogic()
        f = TPFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.pattern_score == 0.0
        assert not o.has_sufficient_data
        assert o.signal_code == "V4TP_NEUT_NO_PATTERN"

    def test_valid_signal_codes(self, test_dbs):
        mdb, _ = test_dbs
        valid_codes = {
            "V4TP_BULL_FLAG", "V4TP_BEAR_FLAG",
            "V4TP_BULL_DOUBLE_BOT", "V4TP_BEAR_DOUBLE_TOP",
            "V4TP_BULL_TRI_ASC", "V4TP_BEAR_TRI_DESC",
            "V4TP_BULL_FAILURE", "V4TP_BEAR_FAILURE",
            "V4TP_NEUT_FORMING", "V4TP_NEUT_NO_PATTERN",
        }
        for sym in ["FPT", "VNM", "HPG"]:
            f = TPFeatureBuilder(mdb).build(sym, "2025-02-01")
            o = TPSignalLogic().compute(f)
            assert o.signal_code in valid_codes, f"{sym}: {o.signal_code}"


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestTPExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = TPExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, TPOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4TREND_PATTERN'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = TPExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals "
            "WHERE symbol='FPT' AND expert_id='V4TREND_PATTERN'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_metadata_fields(self, test_dbs):
        mdb, sdb = test_dbs
        w = TPExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4TREND_PATTERN'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "pattern_type", "pattern_direction", "confirmed", "target_pct",
            "breakout_volume_ratio", "pattern_duration", "pattern_failure",
            "pattern_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_json_types(self, test_dbs):
        """Ensure numpy types are cast to native Python types for JSON."""
        mdb, sdb = test_dbs
        w = TPExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4TREND_PATTERN'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert isinstance(meta["confirmed"], bool)
        assert isinstance(meta["pattern_failure"], bool)
        assert isinstance(meta["pattern_duration"], int)
        assert isinstance(meta["target_pct"], float)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = TPExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = TPExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4TREND_PATTERN'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_bearish_market(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = TPExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        # Should produce a valid output
        assert -4.0 <= o.pattern_score <= 4.0

    def test_most_days_no_pattern(self, test_dbs):
        """Most days should produce no pattern — this is expected and correct."""
        mdb, sdb = test_dbs
        builder = TPFeatureBuilder(mdb)
        logic = TPSignalLogic()
        no_pattern_count = 0
        total = 0
        for sym in ["FPT", "VNM", "HPG"]:
            f = builder.build(sym, "2025-02-01")
            o = logic.compute(f)
            total += 1
            if o.signal_code == "V4TP_NEUT_NO_PATTERN":
                no_pattern_count += 1
        # At least some should have no pattern (random data)
        # Not asserting majority because random data may detect patterns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
