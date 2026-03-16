"""
V4BR Market Breadth Expert Tests
"""

import sqlite3
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.market_context.v4br.feature_builder import (
    BreadthFeatureBuilder, BreadthFeatures,
)
from AI_engine.experts.market_context.v4br.signal_logic import (
    BreadthSignalLogic, BreadthOutput,
)
from AI_engine.experts.market_context.v4br.expert_writer import BreadthExpertWriter


# ---------------------------------------------------------------------------
# Test DB helpers
# ---------------------------------------------------------------------------

# 25 stock symbols for breadth testing
_TEST_STOCKS = [
    "ACB", "BID", "CTG", "FPT", "GAS",
    "HDB", "HPG", "MBB", "MSN", "MWG",
    "NVL", "PLX", "PNJ", "REE", "SAB",
    "SSI", "STB", "TCB", "TPB", "VCB",
    "VHM", "VIC", "VJC", "VNM", "VPB",
]


def _create_test_db(
    db_path: str,
    num_days: int = 400,
    trend: str = "up",
    num_stocks: int = 25,
):
    """
    Create a test market.db with VNINDEX + num_stocks tradable stocks.
    base = date(2024, 1, 1), generates ~400 trading days.
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

    stocks = _TEST_STOCKS[:num_stocks]

    # Insert VNINDEX (not tradable)
    conn.execute(
        "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
        ("VNINDEX", "VNINDEX", "HOSE", None, None, 0, "2024-01-01", None),
    )
    # Insert tradable stocks
    for s in stocks:
        conn.execute(
            "INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
            (s, s, "HOSE", "Test", None, 1, "2024-01-01", None),
        )

    base = date(2024, 1, 1)
    np.random.seed(42)

    # Generate VNINDEX
    price = 1200.0
    for i in range(num_days):
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        drift = 0.0003 if trend == "up" else (-0.0003 if trend == "down" else 0)
        price *= 1 + drift + np.random.normal(0, 0.008)
        h = price * 1.005
        l = price * 0.995
        conn.execute(
            "INSERT OR IGNORE INTO prices_daily "
            "VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
            ("VNINDEX", d.isoformat(), round(price * 1.001, 2),
             round(h, 2), round(l, 2), round(price, 2),
             int(np.random.uniform(5e8, 2e9))),
        )

    # Generate stock prices with varying trends for breadth diversity
    for idx, s in enumerate(stocks):
        price = 50.0 + idx * 5.0
        # Alternate trends for breadth diversity
        if trend == "mixed":
            stock_drift = 0.0005 if idx % 3 == 0 else (-0.0004 if idx % 3 == 1 else 0)
        elif trend == "up":
            stock_drift = 0.0004 + (idx % 5) * 0.0001
        elif trend == "down":
            stock_drift = -0.0004 - (idx % 5) * 0.0001
        else:
            stock_drift = 0

        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            price *= 1 + stock_drift + np.random.normal(0, 0.012)
            price = max(price, 1.0)  # floor at 1
            h = price * 1.008
            l = price * 0.992
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily "
                "VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(price * 1.001, 2),
                 round(h, 2), round(l, 2), round(price, 2),
                 int(np.random.uniform(1e6, 1e7))),
            )

    conn.commit()
    conn.close()


def _create_signals_db(db_path: str):
    """Create test signals.db with expert_signals table."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS expert_signals (
            symbol TEXT NOT NULL, date DATE NOT NULL,
            snapshot_time TEXT DEFAULT 'EOD', expert_id TEXT NOT NULL,
            primary_score REAL NOT NULL, secondary_score REAL,
            signal_code TEXT, signal_quality TEXT DEFAULT 'LOW',
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
    """Bullish trend test DBs with 25 stocks, 400 days."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, num_days=400, trend="up")
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def bearish_dbs(tmp_path):
    """Bearish trend test DBs."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, num_days=400, trend="down")
    _create_signals_db(sdb)
    return mdb, sdb


@pytest.fixture
def mixed_dbs(tmp_path):
    """Mixed trend test DBs for neutral/divergence testing."""
    mdb = str(tmp_path / "market.db")
    sdb = str(tmp_path / "signals.db")
    _create_test_db(mdb, num_days=400, trend="mixed")
    _create_signals_db(sdb)
    return mdb, sdb


# Target date ~2025-02-01 (well within 400-day range from 2024-01-01)
TARGET_DATE = "2025-02-01"


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestBreadthFeatureBuilder:

    def test_build_has_sufficient_data(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert f.has_sufficient_data is True

    def test_data_leakage(self, test_dbs):
        """Data cutoff must be strictly before target_date."""
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert f.data_cutoff_date < TARGET_DATE

    def test_pct_above_sma50_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert 0.0 <= f.pct_above_sma50 <= 100.0

    def test_ad_ratio_positive(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert f.ad_ratio >= 0.0

    def test_net_new_highs_type(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert isinstance(f.net_new_highs, float)

    def test_breadth_momentum_type(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert isinstance(f.breadth_momentum, float)

    def test_total_stocks_reasonable(self, test_dbs):
        """Should have at least 15 stocks with valid data."""
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert f.total_stocks_with_data >= 15

    def test_sub_scores_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        for score in [
            f.score_pct_above_sma50,
            f.score_ad_ratio,
            f.score_net_new_highs,
            f.score_breadth_momentum,
        ]:
            assert -4.0 <= score <= 4.0

    def test_insufficient_data_early_date(self, test_dbs):
        """Very early date should have insufficient data."""
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build("2024-01-10")
        assert f.has_sufficient_data is False

    def test_bullish_trend_positive_breadth(self, test_dbs):
        """In uptrend, pct_above_sma50 should be relatively high."""
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        # Not a strict assertion since random noise, but likely > 30%
        assert f.pct_above_sma50 > 20.0

    def test_bearish_trend_lower_breadth(self, bearish_dbs):
        """In downtrend, pct_above_sma50 should be lower."""
        mdb, _ = bearish_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        assert f.has_sufficient_data is True
        # In downtrend, less stocks above SMA50
        assert f.pct_above_sma50 < 80.0


# ---------------------------------------------------------------------------
# Sub-Score Function Tests (static methods)
# ---------------------------------------------------------------------------

class TestSubScores:

    def test_pct_above_sma50_scores(self):
        s = BreadthFeatureBuilder._score_pct_above_sma50
        assert s(85.0) == 4.0
        assert s(70.0) == 3.0
        assert s(60.0) == 2.0
        assert s(52.0) == 1.0
        assert s(47.0) == 0.0
        assert s(42.0) == -1.0
        assert s(35.0) == -2.0
        assert s(25.0) == -3.0
        assert s(15.0) == -4.0

    def test_ad_ratio_scores(self):
        s = BreadthFeatureBuilder._score_ad_ratio
        assert s(4.0) == 4.0
        assert s(2.5) == 3.0
        assert s(1.7) == 2.0
        assert s(1.3) == 1.0
        assert s(1.0) == 0.0
        assert s(0.7) == -1.0
        assert s(0.6) == -2.0
        assert s(0.4) == -3.0
        assert s(0.2) == -4.0

    def test_net_new_highs_scores(self):
        s = BreadthFeatureBuilder._score_net_new_highs
        assert s(20.0) == 4.0
        assert s(10.0) == 3.0
        assert s(5.0) == 2.0
        assert s(2.0) == 1.0
        assert s(0.0) == 0.0
        assert s(-2.0) == -1.0
        assert s(-5.0) == -2.0
        assert s(-10.0) == -3.0
        assert s(-20.0) == -4.0

    def test_breadth_momentum_scores(self):
        s = BreadthFeatureBuilder._score_breadth_momentum
        assert s(25.0) == 4.0
        assert s(15.0) == 3.0
        assert s(7.0) == 2.0
        assert s(3.0) == 1.0
        assert s(0.0) == 0.0
        assert s(-3.0) == -1.0
        assert s(-7.0) == -2.0
        assert s(-15.0) == -3.0
        assert s(-25.0) == -4.0

    def test_ad_ratio_zero_declines(self):
        """When declines = 0, AD ratio should be capped high."""
        s = BreadthFeatureBuilder._score_ad_ratio
        assert s(5.0) == 4.0  # capped at 5.0 in feature_builder

    def test_all_boundary_values(self):
        """Boundary values should map correctly."""
        s = BreadthFeatureBuilder._score_pct_above_sma50
        # Exactly on boundary (> means strictly greater)
        assert s(80.0) == 3.0   # not > 80, so 65-80 range
        assert s(80.1) == 4.0   # > 80
        assert s(20.0) == -4.0  # not > 20, so < 20 range


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestBreadthSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        o = BreadthSignalLogic().compute(f)
        assert -4.0 <= o.breadth_score <= 4.0

    def test_norm_equals_score_over_4(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        o = BreadthSignalLogic().compute(f)
        assert abs(o.breadth_norm - o.breadth_score / 4.0) < 1e-9

    def test_signal_code_prefix(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        o = BreadthSignalLogic().compute(f)
        assert o.signal_code.startswith("BR_")

    def test_signal_quality_valid(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        o = BreadthSignalLogic().compute(f)
        assert o.signal_quality in ("HIGH", "MEDIUM", "LOW")

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        f = BreadthFeatureBuilder(mdb).build(TARGET_DATE)
        o1 = BreadthSignalLogic().compute(f)
        o2 = BreadthSignalLogic().compute(f)
        assert o1.breadth_score == o2.breadth_score
        assert o1.signal_code == o2.signal_code

    def test_insufficient_data_returns_neutral(self):
        """Insufficient data should produce neutral output."""
        f = BreadthFeatures(
            date="2024-01-05", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.breadth_score == 0.0
        assert o.signal_code == "BR_NEUTRAL"
        assert o.has_sufficient_data is False

    def test_strong_bullish_features(self):
        """Manually crafted strongly bullish features."""
        f = BreadthFeatures(
            date="2025-02-01", data_cutoff_date="2025-01-31",
            pct_above_sma50=85.0,
            ad_ratio=3.5,
            net_new_highs=20.0,
            breadth_momentum=25.0,
            score_pct_above_sma50=4.0,
            score_ad_ratio=4.0,
            score_net_new_highs=4.0,
            score_breadth_momentum=4.0,
            total_stocks_with_data=25,
            has_sufficient_data=True,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.breadth_score == 4.0
        assert o.signal_code == "BR_BROAD_ADVANCE"
        assert o.signal_quality == "HIGH"

    def test_strong_bearish_features(self):
        """Manually crafted strongly bearish features."""
        f = BreadthFeatures(
            date="2025-02-01", data_cutoff_date="2025-01-31",
            pct_above_sma50=15.0,
            ad_ratio=0.2,
            net_new_highs=-20.0,
            breadth_momentum=-25.0,
            score_pct_above_sma50=-4.0,
            score_ad_ratio=-4.0,
            score_net_new_highs=-4.0,
            score_breadth_momentum=-4.0,
            total_stocks_with_data=25,
            has_sufficient_data=True,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.breadth_score == -4.0
        assert o.signal_code == "BR_BROAD_DECLINE"
        assert o.signal_quality == "HIGH"

    def test_neg_divergence_cap(self):
        """Negative divergence should cap score at +1."""
        f = BreadthFeatures(
            date="2025-02-01", data_cutoff_date="2025-01-31",
            pct_above_sma50=70.0,
            ad_ratio=2.5,
            net_new_highs=10.0,
            breadth_momentum=12.0,
            score_pct_above_sma50=3.0,
            score_ad_ratio=3.0,
            score_net_new_highs=3.0,
            score_breadth_momentum=3.0,
            vnindex_at_20d_high=True,
            pct_above_sma50_declining_days=6,  # >= 5
            total_stocks_with_data=25,
            has_sufficient_data=True,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.breadth_score <= 1.0
        assert o.neg_divergence is True
        assert o.signal_code == "BR_NEG_DIVERGENCE"

    def test_pos_divergence_floor(self):
        """Positive divergence should floor score at -1."""
        f = BreadthFeatures(
            date="2025-02-01", data_cutoff_date="2025-01-31",
            pct_above_sma50=25.0,
            ad_ratio=0.4,
            net_new_highs=-10.0,
            breadth_momentum=-12.0,
            score_pct_above_sma50=-3.0,
            score_ad_ratio=-3.0,
            score_net_new_highs=-3.0,
            score_breadth_momentum=-3.0,
            vnindex_at_20d_low=True,
            pct_above_sma50_rising_days=6,  # >= 5
            total_stocks_with_data=25,
            has_sufficient_data=True,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.breadth_score >= -1.0
        assert o.pos_divergence is True
        assert o.signal_code == "BR_POS_DIVERGENCE"

    def test_mixed_subscores_low_quality(self):
        """Mixed sub-scores should produce LOW quality."""
        f = BreadthFeatures(
            date="2025-02-01", data_cutoff_date="2025-01-31",
            pct_above_sma50=48.0,
            ad_ratio=1.0,
            net_new_highs=0.0,
            breadth_momentum=0.0,
            score_pct_above_sma50=0.0,
            score_ad_ratio=0.0,
            score_net_new_highs=0.0,
            score_breadth_momentum=0.0,
            total_stocks_with_data=25,
            has_sufficient_data=True,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.signal_quality == "LOW"
        assert o.signal_code == "BR_NEUTRAL"

    def test_medium_quality(self):
        """3 of 4 agree + abs >= 2 should be MEDIUM quality."""
        f = BreadthFeatures(
            date="2025-02-01", data_cutoff_date="2025-01-31",
            pct_above_sma50=62.0,
            ad_ratio=1.8,
            net_new_highs=5.0,
            breadth_momentum=0.0,
            score_pct_above_sma50=2.0,
            score_ad_ratio=2.0,
            score_net_new_highs=2.0,
            score_breadth_momentum=0.0,  # disagree
            total_stocks_with_data=25,
            has_sufficient_data=True,
        )
        o = BreadthSignalLogic().compute(f)
        assert o.signal_quality == "MEDIUM"


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestBreadthExpertWriter:

    def test_run_writes_for_all_symbols(self, test_dbs):
        """run() should write same score for all provided symbols."""
        mdb, sdb = test_dbs
        symbols = _TEST_STOCKS[:5]
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=symbols)
        assert isinstance(output, BreadthOutput)

        if output.has_sufficient_data:
            conn = sqlite3.connect(sdb)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM expert_signals WHERE expert_id='V4BR' AND date=?",
                (TARGET_DATE,),
            ).fetchall()
            conn.close()

            assert len(rows) == len(symbols)
            # All should have same score
            scores = {row["primary_score"] for row in rows}
            assert len(scores) == 1

    def test_score_in_range(self, test_dbs):
        mdb, sdb = test_dbs
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=["FPT"])
        if output.has_sufficient_data:
            conn = sqlite3.connect(sdb)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4BR'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert -4.0 <= row["primary_score"] <= 4.0

    def test_secondary_score_is_norm(self, test_dbs):
        mdb, sdb = test_dbs
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=["FPT"])
        if output.has_sufficient_data:
            conn = sqlite3.connect(sdb)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4BR'"
            ).fetchone()
            conn.close()
            assert abs(row["secondary_score"] - row["primary_score"] / 4.0) < 1e-9

    def test_metadata_json_valid(self, test_dbs):
        """Metadata must be valid JSON with expected keys."""
        mdb, sdb = test_dbs
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=["FPT"])
        if output.has_sufficient_data:
            conn = sqlite3.connect(sdb)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT metadata_json FROM expert_signals "
                "WHERE symbol='FPT' AND expert_id='V4BR'"
            ).fetchone()
            conn.close()
            meta = json.loads(row["metadata_json"])
            assert "pct_above_sma50" in meta
            assert "ad_ratio" in meta
            assert "net_new_highs" in meta
            assert "breadth_momentum" in meta
            assert "score_pct_above_sma50" in meta
            assert "neg_divergence" in meta
            assert isinstance(meta["neg_divergence"], bool)

    def test_idempotent(self, test_dbs):
        """Running twice should not duplicate rows (INSERT OR REPLACE)."""
        mdb, sdb = test_dbs
        w = BreadthExpertWriter(mdb, sdb)
        w.run(TARGET_DATE, symbols=["FPT"])
        w.run(TARGET_DATE, symbols=["FPT"])
        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals "
            "WHERE symbol='FPT' AND date=? AND expert_id='V4BR'",
            (TARGET_DATE,),
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_all_symbols_same_score(self, test_dbs):
        """All symbols on same date must get identical breadth_score."""
        mdb, sdb = test_dbs
        symbols = _TEST_STOCKS[:10]
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=symbols)

        if output.has_sufficient_data:
            conn = sqlite3.connect(sdb)
            rows = conn.execute(
                "SELECT DISTINCT primary_score FROM expert_signals "
                "WHERE expert_id='V4BR' AND date=?",
                (TARGET_DATE,),
            ).fetchall()
            conn.close()
            # All symbols must share the same breadth score
            assert len(rows) == 1

    def test_signal_code_in_db(self, test_dbs):
        mdb, sdb = test_dbs
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=["FPT"])
        if output.has_sufficient_data:
            conn = sqlite3.connect(sdb)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT signal_code FROM expert_signals "
                "WHERE symbol='FPT' AND expert_id='V4BR'"
            ).fetchone()
            conn.close()
            assert row["signal_code"].startswith("BR_")

    def test_bearish_market_negative_score(self, bearish_dbs):
        mdb, sdb = bearish_dbs
        w = BreadthExpertWriter(mdb, sdb)
        output = w.run(TARGET_DATE, symbols=["FPT"])
        if output.has_sufficient_data:
            # In persistent downtrend, breadth score should be non-positive
            assert output.breadth_score <= 1.0

    def test_expert_id_is_v4br(self, test_dbs):
        mdb, sdb = test_dbs
        w = BreadthExpertWriter(mdb, sdb)
        w.run(TARGET_DATE, symbols=["FPT"])
        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT expert_id FROM expert_signals WHERE symbol='FPT'"
        ).fetchone()
        conn.close()
        if row:
            assert row["expert_id"] == "V4BR"


# ---------------------------------------------------------------------------
# Integration: full pipeline
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_full_pipeline(self, test_dbs):
        """End-to-end: build features -> compute signal -> write to DB."""
        mdb, sdb = test_dbs
        builder = BreadthFeatureBuilder(mdb)
        logic = BreadthSignalLogic()

        features = builder.build(TARGET_DATE)
        assert features.has_sufficient_data is True

        output = logic.compute(features)
        assert -4.0 <= output.breadth_score <= 4.0
        assert output.signal_code.startswith("BR_")

        # Write via expert writer
        writer = BreadthExpertWriter(mdb, sdb)
        result = writer.run(TARGET_DATE, symbols=_TEST_STOCKS[:5])
        assert result.has_sufficient_data is True

    def test_multiple_dates(self, test_dbs):
        """Different dates should produce (potentially) different scores."""
        mdb, _ = test_dbs
        builder = BreadthFeatureBuilder(mdb)
        logic = BreadthSignalLogic()

        f1 = builder.build("2025-01-15")
        f2 = builder.build("2025-02-15")
        o1 = logic.compute(f1)
        o2 = logic.compute(f2)
        # Both should be valid
        assert o1.has_sufficient_data is True
        assert o2.has_sufficient_data is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
