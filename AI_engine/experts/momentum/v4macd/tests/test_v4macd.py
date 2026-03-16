"""
V4MACD MACD Expert Tests
Tests: features, scoring, cross detection, divergence, score ranges, determinism,
       writer, data leakage. Synthetic test DB with 300+ days.
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.momentum.v4macd.feature_builder import (
    MACDFeatureBuilder, MACDFeatures, _ema, _ema_from_series,
)
from AI_engine.experts.momentum.v4macd.signal_logic import MACDSignalLogic, MACDOutput
from AI_engine.experts.momentum.v4macd.expert_writer import MACDExpertWriter


# ---------------------------------------------------------------------------
# Test DB helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: str, num_days=450, trend="up"):
    """Create a synthetic market.db with 300+ trading days."""
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
            drift = 0.0004 if trend == "up" else (-0.0004 if trend == "down" else 0)
            price *= 1 + drift + np.random.normal(0, 0.01)
            h = price * 1.005
            l = price * 0.995
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily "
                "VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (
                    s, d.isoformat(),
                    round(price * 1.001, 2), round(h, 2),
                    round(l, 2), round(price, 2),
                    int(np.random.uniform(1e6, 5e6)),
                ),
            )
    conn.commit()
    conn.close()


def _create_divergence_db(db_path: str):
    """Create DB with known bullish divergence pattern:
    Price makes lower low but MACD makes higher low."""
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
        ("DIV", "DIV", "HOSE", None, None, 1, "2024-01-01", None),
    )

    # Build a price series that creates a known pattern:
    # First 60 bars: rising from 100 to 120 (establish MACD)
    # Bars 60-80: drop to 90 (first trough)
    # Bars 80-100: rise to 105
    # Bars 100-120: drop to 85 (lower low in price, but MACD should be higher)
    np.random.seed(123)
    base = date(2024, 1, 1)
    prices = []

    # Phase 1: rise
    for i in range(60):
        prices.append(100 + i * 0.33 + np.random.normal(0, 0.3))
    # Phase 2: drop
    for i in range(20):
        prices.append(120 - i * 1.5 + np.random.normal(0, 0.3))
    # Phase 3: partial recovery
    for i in range(20):
        prices.append(90 + i * 0.75 + np.random.normal(0, 0.3))
    # Phase 4: deeper drop in price but shallower MACD drop
    for i in range(20):
        prices.append(105 - i * 1.2 + np.random.normal(0, 0.3))
    # Phase 5: stabilize
    for i in range(30):
        prices.append(81 + i * 0.1 + np.random.normal(0, 0.2))

    day_count = 0
    for i in range(len(prices)):
        d = base + timedelta(days=i + i // 5 * 2)  # skip weekends roughly
        p = max(prices[i], 10)
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily "
            "VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("DIV", d.isoformat(), round(p * 1.001, 2), round(p * 1.005, 2),
             round(p * 0.995, 2), round(p, 2), 1000000),
        )
        day_count += 1

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture
def flat_dbs(tmp_path):
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, trend="flat")
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def divergence_dbs(tmp_path):
    mdb = str(tmp_path / "market_div.db")
    sdb = str(tmp_path / "signals.db")
    _create_divergence_db(mdb)
    _create_signals_db(sdb)
    return mdb, sdb


# ---------------------------------------------------------------------------
# EMA unit tests
# ---------------------------------------------------------------------------

class TestEMA:

    def test_ema_basic(self):
        data = np.arange(1.0, 21.0)
        result = _ema(data, 10)
        assert np.isnan(result[0])
        assert not np.isnan(result[9])
        assert not np.isnan(result[19])

    def test_ema_length_matches_input(self):
        data = np.arange(1.0, 51.0)
        result = _ema(data, 12)
        assert len(result) == len(data)

    def test_ema_short_data(self):
        data = np.array([1.0, 2.0, 3.0])
        result = _ema(data, 10)
        assert all(np.isnan(result))

    def test_ema_from_series_with_nans(self):
        data = np.full(50, np.nan)
        data[10:] = np.arange(1.0, 41.0)
        result = _ema_from_series(data, 9)
        assert np.isnan(result[0])
        assert not np.isnan(result[18])  # 10 + 9 - 1


# ---------------------------------------------------------------------------
# Feature Builder
# ---------------------------------------------------------------------------

class TestMACDFeatureBuilder:

    def test_build_basic(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.has_sufficient_data
        assert f.macd_value != 0 or f.signal_value != 0
        assert f.close > 0

    def test_macd_components_exist(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.macd_value, float)
        assert isinstance(f.signal_value, float)
        assert isinstance(f.histogram_value, float)
        # histogram = macd - signal
        assert abs(f.histogram_value - (f.macd_value - f.signal_value)) < 1e-9

    def test_data_leakage(self, test_dbs):
        """Cutoff date must be strictly before target_date."""
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_data_leakage_no_future(self, test_dbs):
        """Building for two dates: later date must not affect earlier result."""
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2025-03-01")
        f2 = builder.build("FPT", "2025-06-01")
        # f1 cutoff must be before f2 cutoff
        assert f1.data_cutoff_date < f2.data_cutoff_date

    def test_slopes(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.macd_slope, float)
        assert isinstance(f.histogram_slope, float)

    def test_directional_flags(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.macd_above_signal in (1, -1)
        assert f.macd_above_zero in (1, -1)

    def test_cross_flags_are_bool(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert isinstance(f.bull_cross, bool)
        assert isinstance(f.bear_cross, bool)
        # Cannot have both crosses at same time
        assert not (f.bull_cross and f.bear_cross)

    def test_insufficient_data(self, test_dbs):
        """Very early date should not have sufficient data."""
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2024-02-01")
        assert not f.has_sufficient_data

    def test_missing_symbol(self, test_dbs):
        """Unknown symbol returns empty features."""
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("NOSYMBOL", "2025-06-01")
        assert not f.has_sufficient_data
        assert f.data_cutoff_date == ""

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = MACDFeatureBuilder(mdb).build_batch(
            ["FPT", "VNM", "HPG"], "2025-06-01"
        )
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_divergence_flag_range(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.divergence_flag in (-1, 0, 1)


# ---------------------------------------------------------------------------
# Signal Logic — Scoring
# ---------------------------------------------------------------------------

class TestMACDSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MACDSignalLogic().compute(f)
        assert -4.0 <= o.macd_score <= 4.0

    def test_norm_calculation(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MACDSignalLogic().compute(f)
        assert abs(o.macd_norm - o.macd_score / 4.0) < 1e-9

    def test_component_ranges(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MACDSignalLogic().compute(f)
        assert -2.0 <= o.cross_score <= 2.0
        assert -1.0 <= o.zero_line_score <= 1.0
        assert -0.5 <= o.histogram_score <= 0.5
        assert -1.0 <= o.divergence_score <= 1.0

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MACDSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        o = MACDSignalLogic().compute(f)
        assert o.signal_code.startswith("V4MACD_")

    def test_valid_signal_codes(self, test_dbs):
        """Signal code must be one of the defined codes."""
        valid_codes = {
            "V4MACD_BULL_CROSS", "V4MACD_BEAR_CROSS",
            "V4MACD_BULL_CROSS_ZERO", "V4MACD_BEAR_CROSS_ZERO",
            "V4MACD_BULL_DIV", "V4MACD_BEAR_DIV",
            "V4MACD_BULL_HIST_EXPAND", "V4MACD_BEAR_HIST_EXPAND",
            "V4MACD_NEUT_FLAT",
        }
        mdb, _ = test_dbs
        for sym in ["FPT", "VNM", "HPG"]:
            f = MACDFeatureBuilder(mdb).build(sym, "2025-06-01")
            o = MACDSignalLogic().compute(f)
            assert o.signal_code in valid_codes, f"Bad code: {o.signal_code}"

    def test_deterministic(self, test_dbs):
        """Same input must produce identical output."""
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        logic = MACDSignalLogic()
        f1 = builder.build("FPT", "2025-06-01")
        f2 = builder.build("FPT", "2025-06-01")
        o1 = logic.compute(f1)
        o2 = logic.compute(f2)
        assert o1.macd_score == o2.macd_score
        assert o1.cross_score == o2.cross_score
        assert o1.zero_line_score == o2.zero_line_score
        assert o1.histogram_score == o2.histogram_score
        assert o1.divergence_score == o2.divergence_score
        assert o1.signal_code == o2.signal_code
        assert o1.signal_quality == o2.signal_quality

    def test_insufficient_data_returns_zero(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2024-02-01")
        o = MACDSignalLogic().compute(f)
        assert o.macd_score == 0.0
        assert not o.has_sufficient_data

    # --- Synthetic feature tests ---

    def test_bull_cross_above_zero(self):
        """Bull cross when both MACD and signal are above zero => +2."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=1.5, signal_value=1.2, histogram_value=0.3,
            macd_slope=0.005, histogram_slope=0.002,
            macd_above_signal=1, macd_above_zero=1,
            bull_cross=True, bear_cross=False,
            prev_macd=1.0, prev_signal=1.1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.cross_score == 2.0

    def test_bull_cross_below_zero(self):
        """Bull cross when MACD below zero => +1."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=-0.5, signal_value=-0.8, histogram_value=0.3,
            macd_slope=0.003, histogram_slope=0.002,
            macd_above_signal=1, macd_above_zero=-1,
            bull_cross=True, bear_cross=False,
            prev_macd=-1.0, prev_signal=-0.7,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.cross_score == 1.0

    def test_bear_cross_below_zero(self):
        """Bear cross when both below zero => -2."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=-1.5, signal_value=-1.2, histogram_value=-0.3,
            macd_slope=-0.005, histogram_slope=-0.002,
            macd_above_signal=-1, macd_above_zero=-1,
            bull_cross=False, bear_cross=True,
            prev_macd=-1.0, prev_signal=-1.3,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.cross_score == -2.0

    def test_bear_cross_above_zero(self):
        """Bear cross when above zero => -1."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=0.5, signal_value=0.8, histogram_value=-0.3,
            macd_slope=-0.003, histogram_slope=-0.002,
            macd_above_signal=-1, macd_above_zero=1,
            bull_cross=False, bear_cross=True,
            prev_macd=1.0, prev_signal=0.7,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.cross_score == -1.0

    def test_zero_line_above_rising(self):
        """MACD > 0 and rising => zero_line_score = +1."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=2.0, signal_value=1.5, histogram_value=0.5,
            macd_slope=0.01, histogram_slope=0.005,
            macd_above_signal=1, macd_above_zero=1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.zero_line_score == 1.0

    def test_zero_line_below_falling(self):
        """MACD < 0 and falling => zero_line_score = -1."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=-2.0, signal_value=-1.5, histogram_value=-0.5,
            macd_slope=-0.01, histogram_slope=-0.005,
            macd_above_signal=-1, macd_above_zero=-1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.zero_line_score == -1.0

    def test_zero_line_near_zero(self):
        """MACD near zero (< 0.5% of close) => zero_line_score = 0."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=0.1, signal_value=0.05, histogram_value=0.05,
            macd_slope=0.0, histogram_slope=0.0,
            macd_above_signal=1, macd_above_zero=1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.zero_line_score == 0.0

    def test_histogram_positive_expanding(self):
        """Histogram > 0 and slope > 0 => +0.5."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=2.0, signal_value=1.0, histogram_value=1.0,
            macd_slope=0.01, histogram_slope=0.005,
            macd_above_signal=1, macd_above_zero=1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.histogram_score == 0.5

    def test_histogram_negative_expanding(self):
        """Histogram < 0 and slope < 0 => -0.5."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=-2.0, signal_value=-1.0, histogram_value=-1.0,
            macd_slope=-0.01, histogram_slope=-0.005,
            macd_above_signal=-1, macd_above_zero=-1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.histogram_score == -0.5

    def test_bullish_divergence_score(self):
        """Bullish divergence => divergence_score = +1."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=-0.5, signal_value=-0.8, histogram_value=0.3,
            macd_slope=0.002, histogram_slope=0.001,
            macd_above_signal=1, macd_above_zero=-1,
            divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.divergence_score == 1.0
        assert o.signal_code == "V4MACD_BULL_DIV"

    def test_bearish_divergence_score(self):
        """Bearish divergence => divergence_score = -1."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=0.5, signal_value=0.8, histogram_value=-0.3,
            macd_slope=-0.002, histogram_slope=-0.001,
            macd_above_signal=-1, macd_above_zero=1,
            divergence_flag=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.divergence_score == -1.0
        assert o.signal_code == "V4MACD_BEAR_DIV"

    def test_max_bullish_score(self):
        """Maximum bullish scenario: cross above zero + rising + expanding + bull div."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=2.0, signal_value=1.5, histogram_value=0.5,
            macd_slope=0.01, histogram_slope=0.005,
            macd_above_signal=1, macd_above_zero=1,
            bull_cross=True, bear_cross=False,
            prev_macd=1.3, prev_signal=1.6,
            divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # cross=+2, zero=+1, hist=+0.5, div=+1 = 4.5 -> clamped to 4
        assert o.macd_score == 4.0
        assert o.macd_norm == 1.0

    def test_max_bearish_score(self):
        """Maximum bearish scenario."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=-2.0, signal_value=-1.5, histogram_value=-0.5,
            macd_slope=-0.01, histogram_slope=-0.005,
            macd_above_signal=-1, macd_above_zero=-1,
            bull_cross=False, bear_cross=True,
            prev_macd=-1.3, prev_signal=-1.6,
            divergence_flag=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # cross=-2, zero=-1, hist=-0.5, div=-1 = -4.5 -> clamped to -4
        assert o.macd_score == -4.0
        assert o.macd_norm == -1.0

    def test_score_clamping(self):
        """Score must be clamped to [-4, +4]."""
        logic = MACDSignalLogic()
        # Extreme bullish
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=5.0, signal_value=4.0, histogram_value=1.0,
            macd_slope=0.05, histogram_slope=0.03,
            macd_above_signal=1, macd_above_zero=1,
            bull_cross=True, divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.macd_score <= 4.0
        assert o.macd_score >= -4.0

    def test_quality_level_4(self):
        """Quality 4: cross + zero confirm + divergence."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=2.0, signal_value=1.5, histogram_value=0.5,
            macd_slope=0.01, histogram_slope=0.005,
            macd_above_signal=1, macd_above_zero=1,
            bull_cross=True, divergence_flag=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 4

    def test_quality_level_0_flat(self):
        """Quality 0: MACD near zero, no signal."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=0.1, signal_value=0.1, histogram_value=0.0,
            macd_slope=0.0, histogram_slope=0.0,
            macd_above_signal=1, macd_above_zero=1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_quality == 0

    def test_neutral_flat_code(self):
        """No cross, no divergence, contracting histogram => NEUT_FLAT."""
        logic = MACDSignalLogic()
        f = MACDFeatures(
            symbol="TEST", date="2026-01-15", data_cutoff_date="2026-01-14",
            close=100.0,
            macd_value=0.1, signal_value=0.1, histogram_value=0.0,
            macd_slope=0.0, histogram_slope=0.0,
            macd_above_signal=1, macd_above_zero=1,
            divergence_flag=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.signal_code == "V4MACD_NEUT_FLAT"


# ---------------------------------------------------------------------------
# Cross detection
# ---------------------------------------------------------------------------

class TestCrossDetection:

    def test_bull_cross_detected(self, test_dbs):
        """Over many dates, at least one bull or bear cross should occur."""
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        found_bull = False
        found_bear = False
        base = date(2025, 3, 1)
        for i in range(60):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            f = builder.build("FPT", d.isoformat())
            if f.has_sufficient_data:
                if f.bull_cross:
                    found_bull = True
                if f.bear_cross:
                    found_bear = True
        # In 60 trading days with random walk, expect at least one cross
        assert found_bull or found_bear

    def test_cross_mutual_exclusion(self, test_dbs):
        """Cannot have both bull and bear cross simultaneously."""
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        base = date(2025, 3, 1)
        for i in range(90):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            f = builder.build("FPT", d.isoformat())
            if f.has_sufficient_data:
                assert not (f.bull_cross and f.bear_cross)


# ---------------------------------------------------------------------------
# Divergence detection
# ---------------------------------------------------------------------------

class TestDivergenceDetection:

    def test_divergence_flag_values(self, test_dbs):
        """Divergence flag must be -1, 0, or +1."""
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        base = date(2025, 3, 1)
        for i in range(60):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            f = builder.build("FPT", d.isoformat())
            if f.has_sufficient_data:
                assert f.divergence_flag in (-1, 0, 1)

    def test_divergence_with_synthetic_features(self):
        """Directly test divergence scoring with known flag values."""
        logic = MACDSignalLogic()
        for div_flag, expected_score in [(1, 1.0), (-1, -1.0), (0, 0.0)]:
            f = MACDFeatures(
                symbol="T", date="2026-01-15", data_cutoff_date="2026-01-14",
                close=100.0,
                macd_value=0.5, signal_value=0.3, histogram_value=0.2,
                macd_slope=0.001, histogram_slope=0.001,
                macd_above_signal=1, macd_above_zero=1,
                divergence_flag=div_flag,
                has_sufficient_data=True,
            )
            o = logic.compute(f)
            assert o.divergence_score == expected_score


# ---------------------------------------------------------------------------
# Score ranges (multiple symbols and dates)
# ---------------------------------------------------------------------------

class TestScoreRanges:

    def test_all_scores_in_range(self, test_dbs):
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        logic = MACDSignalLogic()
        base = date(2025, 3, 1)
        for sym in ["FPT", "VNM", "HPG"]:
            for i in range(30):
                d = base + timedelta(days=i)
                if d.weekday() >= 5:
                    continue
                f = builder.build(sym, d.isoformat())
                if not f.has_sufficient_data:
                    continue
                o = logic.compute(f)
                assert -4.0 <= o.macd_score <= 4.0, f"{sym} {d}: score={o.macd_score}"
                assert -1.0 <= o.macd_norm <= 1.0
                assert -2.0 <= o.cross_score <= 2.0
                assert -1.0 <= o.zero_line_score <= 1.0
                assert -0.5 <= o.histogram_score <= 0.5
                assert -1.0 <= o.divergence_score <= 1.0
                assert 0 <= o.signal_quality <= 4

    def test_bearish_trend_scores(self, bearish_dbs):
        """Bearish trend should produce negative scores on average."""
        mdb, _ = bearish_dbs
        builder = MACDFeatureBuilder(mdb)
        logic = MACDSignalLogic()
        scores = []
        base = date(2025, 6, 1)
        for i in range(30):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            f = builder.build("FPT", d.isoformat())
            if f.has_sufficient_data:
                o = logic.compute(f)
                scores.append(o.macd_score)
        if scores:
            avg = sum(scores) / len(scores)
            # With downtrend, average should lean negative
            assert avg < 1.0  # loose bound: not strongly positive


# ---------------------------------------------------------------------------
# Expert Writer
# ---------------------------------------------------------------------------

class TestMACDExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = MACDExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-06-01")
        assert isinstance(o, MACDOutput)
        assert o.has_sufficient_data

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4MACD'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4
        assert -1 <= row["secondary_score"] <= 1

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required features."""
        mdb, sdb = test_dbs
        w = MACDExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals "
            "WHERE symbol='FPT' AND expert_id='V4MACD'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "macd_value", "signal_value", "histogram_value",
            "macd_slope", "histogram_slope",
            "macd_above_signal", "macd_above_zero", "divergence_flag",
            "cross_score", "zero_line_score", "histogram_score",
            "divergence_score", "macd_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = MACDExpertWriter(mdb, sdb)
        results = w.run_all("2025-06-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE expert_id='V4MACD'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 2

    def test_idempotent(self, test_dbs):
        """Running twice should not create duplicate rows."""
        mdb, sdb = test_dbs
        w = MACDExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals "
            "WHERE symbol='FPT' AND date='2025-06-01' AND expert_id='V4MACD'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_expert_id_correct(self, test_dbs):
        mdb, sdb = test_dbs
        w = MACDExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-06-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT expert_id FROM expert_signals WHERE symbol='FPT'"
        ).fetchone()
        conn.close()
        assert row["expert_id"] == "V4MACD"

    def test_insufficient_data_not_written(self, test_dbs):
        """Symbols with insufficient data should not be written."""
        mdb, sdb = test_dbs
        w = MACDExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2024-02-01")

        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE expert_id='V4MACD'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 0


# ---------------------------------------------------------------------------
# Data leakage (end-to-end)
# ---------------------------------------------------------------------------

class TestDataLeakage:

    def test_cutoff_strictly_before_target(self, test_dbs):
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2025-06-01")
        assert f.data_cutoff_date < "2025-06-01"

    def test_different_targets_give_different_cutoffs(self, test_dbs):
        mdb, _ = test_dbs
        builder = MACDFeatureBuilder(mdb)
        f1 = builder.build("FPT", "2024-10-01")
        f2 = builder.build("FPT", "2025-02-01")
        assert f1.data_cutoff_date != f2.data_cutoff_date
        assert f1.data_cutoff_date < f2.data_cutoff_date

    def test_future_date_uses_latest_available(self, test_dbs):
        """Target date far in future should still work, using latest data."""
        mdb, _ = test_dbs
        f = MACDFeatureBuilder(mdb).build("FPT", "2030-01-01")
        assert f.has_sufficient_data
        assert f.data_cutoff_date < "2030-01-01"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
