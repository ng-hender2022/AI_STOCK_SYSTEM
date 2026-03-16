"""
V4LIQ Liquidity Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.market_context.v4liq.feature_builder import LiqFeatureBuilder, LiqFeatures
from AI_engine.experts.market_context.v4liq.signal_logic import LiqSignalLogic, LiqOutput
from AI_engine.experts.market_context.v4liq.expert_writer import LiqExpertWriter


def _create_test_db(
    db_path: str,
    num_days=400,
    base_price=50000.0,
    base_vol=500_000,
    vol_pattern="normal",
    spread_pct=1.0,
):
    """Create test market.db with price and volume data.

    base_price: in VND (e.g. 50000 = 50,000 VND)
    base_vol: base share volume per day
    vol_pattern:
        normal   - random volume around base_vol
        mega     - very high volume (institutional grade)
        illiquid - very low volume
        zero     - many zero-volume days
        surge    - last 5 days 5x normal
        drought  - last 5 days very low
    spread_pct: controls H-L spread as percentage of close
    """
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
            (s, s, "HOSE", None, None, t, "2025-01-01", None),
        )

    base = date(2024, 1, 1)
    np.random.seed(42)

    for s in ["FPT", "VNM", "HPG", "VNINDEX"]:
        price = base_price if s != "VNINDEX" else 1200000.0
        day_count = 0
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            day_count += 1

            price *= 1 + 0.0002 + np.random.normal(0, 0.008)
            half_spread = spread_pct / 100.0 / 2.0
            h = price * (1 + half_spread)
            l = price * (1 - half_spread)

            # Volume pattern
            if vol_pattern == "mega":
                vol = int(np.random.uniform(800_000, 1_200_000))
            elif vol_pattern == "illiquid":
                vol = int(np.random.uniform(50, 200))
            elif vol_pattern == "zero":
                if day_count % 3 == 0:
                    vol = 0
                else:
                    vol = int(np.random.uniform(50, 200))
            elif vol_pattern == "surge" and day_count > (num_days * 0.7 - 5):
                vol = int(np.random.uniform(base_vol * 4, base_vol * 6))
            elif vol_pattern == "drought" and day_count > (num_days * 0.7 - 5):
                vol = int(np.random.uniform(10, 50))
            else:
                vol = int(np.random.uniform(base_vol * 0.7, base_vol * 1.3))

            # value = volume * close (in VND)
            value = vol * price

            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (
                    s, d.isoformat(),
                    round(price * 1.001, 2), round(h, 2), round(l, 2), round(price, 2),
                    vol, round(value, 2),
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_dbs(tmp_path):
    """Normal liquidity: base_price=50000, base_vol=500000 => ADTV ~25B VND."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, base_price=50000.0, base_vol=500_000, spread_pct=1.0)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def mega_dbs(tmp_path):
    """Mega liquidity: high price * high volume => ADTV > 50B."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, base_price=80000.0, base_vol=1_000_000, spread_pct=0.5)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def illiquid_dbs(tmp_path):
    """Very illiquid: tiny volume."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, base_price=10000.0, base_vol=100, vol_pattern="illiquid", spread_pct=8.0)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def zero_vol_dbs(tmp_path):
    """Many zero-volume days."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, base_price=10000.0, base_vol=100, vol_pattern="zero", spread_pct=8.0)
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def no_value_col_dbs(tmp_path):
    """DB without 'value' column — must compute volume*close."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, base_price=50000.0, base_vol=500_000, spread_pct=1.0)
    # Drop value column by recreating table without it
    conn = sqlite3.connect(mdb)
    conn.executescript("""
        CREATE TABLE prices_daily_new (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, date)
        );
        INSERT INTO prices_daily_new
            SELECT symbol, date, open, high, low, close, volume, created_at
            FROM prices_daily;
        DROP TABLE prices_daily;
        ALTER TABLE prices_daily_new RENAME TO prices_daily;
    """)
    conn.commit()
    conn.close()
    _create_signals_db(sdb)
    return mdb, sdb


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestLiqFeatureBuilder:

    def test_build_basic(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.adtv_20d > 0
        assert f.adtv_60d > 0
        assert f.adtv_ratio > 0

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.data_cutoff_date < "2025-02-01"

    def test_adtv_ratio(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        expected = f.adtv_20d / f.adtv_60d if f.adtv_60d > 0 else 1.0
        assert abs(f.adtv_ratio - expected) < 1e-6

    def test_volume_cv_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.volume_cv > 0

    def test_hl_spread_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.hl_spread_avg > 0

    def test_insufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2024-01-10")
        assert not f.has_sufficient_data

    def test_batch(self, test_dbs):
        mdb, _ = test_dbs
        results = LiqFeatureBuilder(mdb).build_batch(["FPT", "VNM", "HPG"], "2025-02-01")
        assert len(results) == 3
        for r in results:
            assert r.has_sufficient_data

    def test_no_value_column_fallback(self, no_value_col_dbs):
        """When 'value' column is missing, compute volume * close / 1e9."""
        mdb, _ = no_value_col_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.adtv_20d > 0

    def test_zero_volume_days_count(self, zero_vol_dbs):
        mdb, _ = zero_vol_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert f.has_sufficient_data
        assert f.zero_volume_days > 0

    def test_pct_days_above_1b(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        assert 0.0 <= f.pct_days_above_1b <= 100.0


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestLiqSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = LiqSignalLogic().compute(f)
        assert -4.0 <= o.liq_score <= 4.0

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = LiqSignalLogic().compute(f)
        assert abs(o.liq_norm - o.liq_score / 4.0) < 1e-4

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = LiqSignalLogic().compute(f)
        assert 0 <= o.signal_quality <= 4

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = LiqSignalLogic().compute(f)
        assert o.signal_code.startswith("LIQ_")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o1 = LiqSignalLogic().compute(f)
        o2 = LiqSignalLogic().compute(f)
        assert o1.liq_score == o2.liq_score

    def test_mega_liquid(self):
        """High ADTV, low CV, tight spread, stable trend => high score."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=60.0, adtv_60d=55.0, adtv_ratio=60.0 / 55.0,
            volume_cv=0.4, zero_volume_days=0, pct_days_above_1b=100.0,
            hl_spread_avg=0.8,
            has_recent_breakout=False, has_recent_drought=False,
            today_value=58.0, today_vs_avg=58.0 / 60.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.adtv_sub == 4.0
        assert o.consistency_sub == 4.0
        assert o.spread_sub == 4.0
        assert o.liq_score > 3.0
        assert o.signal_code.startswith("LIQ_")
        assert o.signal_quality >= 3

    def test_untradeable_override(self):
        """ADTV < 0.1B => forced to -4 regardless of other metrics."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=0.05, adtv_60d=0.04, adtv_ratio=1.25,
            volume_cv=0.3, zero_volume_days=0, pct_days_above_1b=0.0,
            hl_spread_avg=0.5,
            has_recent_breakout=False, has_recent_drought=False,
            today_value=0.04, today_vs_avg=0.8,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.liq_score == -4.0
        assert o.signal_code.startswith("LIQ_")
        assert o.signal_quality == 0 or o.liq_score == -4.0

    def test_zero_vol_override(self):
        """Zero volume days >= 15 => forced to -4."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=5.0, adtv_60d=5.0, adtv_ratio=1.0,
            volume_cv=2.5, zero_volume_days=16, pct_days_above_1b=20.0,
            hl_spread_avg=3.0,
            has_recent_breakout=False, has_recent_drought=False,
            today_value=5.0, today_vs_avg=1.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.liq_score == -4.0

    def test_illiquid_score(self, illiquid_dbs):
        """Very illiquid stock should get strongly negative score."""
        mdb, _ = illiquid_dbs
        f = LiqFeatureBuilder(mdb).build("FPT", "2025-02-01")
        o = LiqSignalLogic().compute(f)
        assert o.liq_score <= -3.0

    def test_adtv_tier_sub_scores(self):
        """Test each ADTV tier boundary."""
        logic = LiqSignalLogic()
        base = LiqFeatures(
            symbol="T", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_60d=10.0, adtv_ratio=1.0,
            volume_cv=0.5, zero_volume_days=0, pct_days_above_1b=100.0,
            hl_spread_avg=1.0, has_sufficient_data=True,
            has_recent_breakout=False, has_recent_drought=False,
            today_value=10.0, today_vs_avg=1.0,
        )
        cases = [
            (55.0, 4), (25.0, 3), (15.0, 2), (7.0, 1),
            (3.0, 0), (1.5, -1), (0.7, -2), (0.3, -3), (0.05, -4),
        ]
        for adtv, expected_sub in cases:
            base.adtv_20d = adtv
            assert logic._adtv_tier(base) == expected_sub, f"ADTV={adtv} expected sub={expected_sub}"

    def test_spread_sub_scores(self):
        """Test spread tier boundaries."""
        logic = LiqSignalLogic()
        base = LiqFeatures(
            symbol="T", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=10.0, adtv_60d=10.0, adtv_ratio=1.0,
            volume_cv=0.5, zero_volume_days=0, pct_days_above_1b=100.0,
            has_sufficient_data=True,
            has_recent_breakout=False, has_recent_drought=False,
            today_value=10.0, today_vs_avg=1.0,
        )
        cases = [
            (0.5, 4), (1.2, 2), (2.0, 1), (3.0, 0),
            (4.0, -1), (6.0, -2), (8.0, -3), (12.0, -4),
        ]
        for spread, expected_sub in cases:
            base.hl_spread_avg = spread
            assert logic._spread(base) == expected_sub, f"Spread={spread}% expected sub={expected_sub}"

    def test_trend_sub_scores(self):
        """Test trend sub-score boundaries."""
        logic = LiqSignalLogic()
        base = LiqFeatures(
            symbol="T", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=10.0, adtv_60d=10.0,
            volume_cv=0.5, zero_volume_days=0, pct_days_above_1b=100.0,
            hl_spread_avg=1.0, has_sufficient_data=True,
            has_recent_breakout=False, has_recent_drought=False,
            today_value=10.0, today_vs_avg=1.0,
        )
        cases = [
            (1.35, False, 3),   # > 1.3
            (1.20, False, 2),   # > 1.15
            (1.10, False, 1),   # > 1.05
            (1.00, False, 0),   # 0.90 - 1.05
            (0.85, False, -1),  # 0.75 - 0.90
            (0.70, False, -2),  # 0.60 - 0.75
            (0.50, False, -3),  # < 0.60
        ]
        for ratio, breakout, expected in cases:
            base.adtv_ratio = ratio
            base.has_recent_breakout = breakout
            assert logic._trend(base) == expected, f"Ratio={ratio} expected={expected}"

    def test_trend_surge(self):
        """ADTV_Ratio > 1.5 with recent breakout => +4."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="T", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=10.0, adtv_60d=10.0, adtv_ratio=1.6,
            volume_cv=0.5, zero_volume_days=0, pct_days_above_1b=100.0,
            hl_spread_avg=1.0, has_sufficient_data=True,
            has_recent_breakout=True, has_recent_drought=False,
            today_value=10.0, today_vs_avg=1.0,
        )
        assert logic._trend(f) == 4.0

    def test_trend_severe_drought(self):
        """ADTV_Ratio < 0.4 with recent drought => -4."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="T", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=10.0, adtv_60d=10.0, adtv_ratio=0.35,
            volume_cv=0.5, zero_volume_days=0, pct_days_above_1b=100.0,
            hl_spread_avg=1.0, has_sufficient_data=True,
            has_recent_breakout=False, has_recent_drought=True,
            today_value=10.0, today_vs_avg=1.0,
        )
        assert logic._trend(f) == -4.0

    def test_score_clamp(self):
        """Score must be clamped to -4..+4."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="T", date="2025-02-01", data_cutoff_date="2025-01-31",
            adtv_20d=60.0, adtv_60d=30.0, adtv_ratio=2.0,
            volume_cv=0.3, zero_volume_days=0, pct_days_above_1b=100.0,
            hl_spread_avg=0.5, has_sufficient_data=True,
            has_recent_breakout=True, has_recent_drought=False,
            today_value=60.0, today_vs_avg=1.0,
        )
        o = logic.compute(f)
        assert -4.0 <= o.liq_score <= 4.0

    def test_insufficient_data_zero(self):
        """Insufficient data should return zero scores."""
        logic = LiqSignalLogic()
        f = LiqFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.liq_score == 0.0
        assert not o.has_sufficient_data


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestLiqExpertWriter:

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = LiqExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", "2025-02-01")
        assert isinstance(o, LiqOutput)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4LIQ'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required fields."""
        mdb, sdb = test_dbs
        w = LiqExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4LIQ'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required = [
            "adtv_20d", "adtv_60d", "adtv_ratio", "volume_cv",
            "zero_volume_days", "hl_spread_avg",
            "adtv_sub", "consistency_sub", "spread_sub", "trend_sub",
            "liq_norm",
        ]
        for key in required:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_types(self, test_dbs):
        """Ensure numpy bools/ints are cast to Python types for JSON."""
        mdb, sdb = test_dbs
        w = LiqExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4LIQ'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        assert isinstance(meta["zero_volume_days"], int)
        assert isinstance(meta["adtv_20d"], float)
        assert isinstance(meta["liq_norm"], float)

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = LiqExpertWriter(mdb, sdb)
        results = w.run_all("2025-02-01", symbols=["FPT", "VNM"])
        assert len(results) == 2

    def test_idempotent(self, test_dbs):
        mdb, sdb = test_dbs
        w = LiqExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")
        w.run_symbol("FPT", "2025-02-01")
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date='2025-02-01' AND expert_id='V4LIQ'"
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_secondary_score_is_norm(self, test_dbs):
        """secondary_score in DB must equal liq_norm = liq_score / 4."""
        mdb, sdb = test_dbs
        w = LiqExpertWriter(mdb, sdb)
        w.run_symbol("FPT", "2025-02-01")

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals WHERE symbol='FPT' AND expert_id='V4LIQ'"
        ).fetchone()
        conn.close()
        assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
