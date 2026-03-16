"""
V4RS Relative Strength Expert Tests
"""

import sqlite3
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from AI_engine.experts.market_context.v4rs.feature_builder import RSFeatureBuilder, RSFeatures
from AI_engine.experts.market_context.v4rs.signal_logic import RSSignalLogic, RSOutput
from AI_engine.experts.market_context.v4rs.expert_writer import RSExpertWriter


# ---------------------------------------------------------------------------
# Test DB helpers
# ---------------------------------------------------------------------------

SYMBOLS = [
    "VNINDEX", "FPT", "VNM", "HPG", "MWG", "VCB", "BID", "CTG",
    "TCB", "VHM", "VIC", "MSN", "SSI",
]


def _create_test_db(db_path: str, num_days=400):
    """Create market.db with VNINDEX + 12 stocks, diverse return profiles."""
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
    for s in SYMBOLS:
        t = 0 if s == "VNINDEX" else 1
        conn.execute("INSERT OR IGNORE INTO symbols_master VALUES (?,?,?,?,?,?,?,?)",
                      (s, s, "HOSE", "BANK" if s in ("VCB","BID","CTG","TCB") else "OTHER",
                       None, t, "2024-01-01", None))

    base = date(2024, 1, 1)
    np.random.seed(42)

    # Different drift profiles so stocks rank differently
    drifts = {
        "VNINDEX": 0.0003,   # moderate market
        "FPT": 0.0008,       # strong outperformer
        "VNM": 0.0001,       # slight underperformer
        "HPG": 0.0006,       # outperformer
        "MWG": -0.0002,      # underperformer
        "VCB": 0.0004,       # slight outperformer
        "BID": 0.0002,       # near market
        "CTG": 0.0005,       # outperformer
        "TCB": -0.0001,      # underperformer
        "VHM": 0.0007,       # strong outperformer
        "VIC": -0.0003,      # strong underperformer
        "MSN": 0.0003,       # market average
        "SSI": 0.0001,       # slight underperformer
    }

    for s in SYMBOLS:
        price = 1200.0 if s == "VNINDEX" else 100.0
        drift = drifts.get(s, 0.0003)
        for i in range(num_days):
            d = base + timedelta(days=i)
            if d.weekday() >= 5:
                continue
            price *= 1 + drift + np.random.normal(0, 0.012)
            price = max(price, 1.0)  # floor at 1
            h = price * 1.005
            l = price * 0.995
            conn.execute(
                "INSERT OR IGNORE INTO prices_daily VALUES (?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP)",
                (s, d.isoformat(), round(price * 1.001, 2), round(h, 2),
                 round(l, 2), round(price, 2), int(np.random.uniform(1e6, 5e6))),
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


TARGET_DATE = "2025-02-01"


# ---------------------------------------------------------------------------
# Feature Builder Tests
# ---------------------------------------------------------------------------

class TestRSFeatureBuilder:

    def test_build_batch(self, test_dbs):
        mdb, _ = test_dbs
        syms = [s for s in SYMBOLS if s != "VNINDEX"]
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        assert len(results) == len(SYMBOLS)
        sufficient = [r for r in results if r.has_sufficient_data]
        assert len(sufficient) >= 10  # most symbols should have enough data

    def test_data_leakage(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        for r in results:
            if r.has_sufficient_data:
                assert r.data_cutoff_date < TARGET_DATE, (
                    f"{r.symbol} cutoff {r.data_cutoff_date} not < {TARGET_DATE}"
                )

    def test_rs_ratios_computed(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        fpt = [r for r in results if r.symbol == "FPT"][0]
        assert fpt.has_sufficient_data
        assert not math.isnan(fpt.rs_5d)
        assert not math.isnan(fpt.rs_20d)
        assert not math.isnan(fpt.rs_60d)

    def test_ranks_distributed(self, test_dbs):
        """Ranks should span from low to high across diverse symbols."""
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        ranks = [r.rs_rank_20d for r in results if r.has_sufficient_data and r.symbol != "VNINDEX"]
        assert len(ranks) >= 8
        assert min(ranks) < 20  # someone near bottom
        assert max(ranks) > 80  # someone near top

    def test_deciles_valid(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        for r in results:
            if r.has_sufficient_data:
                assert 1 <= r.rs_decile <= 10, f"{r.symbol} decile={r.rs_decile}"

    def test_trend_values(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        valid_trends = {"RISING", "FLAT", "FALLING"}
        for r in results:
            if r.has_sufficient_data:
                assert r.rs_trend in valid_trends, f"{r.symbol} trend={r.rs_trend}"

    def test_build_single_symbol(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        feat = builder.build("FPT", TARGET_DATE, universe=SYMBOLS)
        assert feat.symbol == "FPT"
        assert feat.has_sufficient_data

    def test_vnindex_self_reference(self, test_dbs):
        """VNINDEX compared to itself should be neutral."""
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        vni = [r for r in results if r.symbol == "VNINDEX"][0]
        assert vni.has_sufficient_data
        assert vni.rs_5d == 1.0
        assert vni.rs_decile == 5

    def test_insufficient_data(self, test_dbs):
        """Very early date should produce insufficient data."""
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        results = builder.build_batch(SYMBOLS, "2024-02-01")
        for r in results:
            assert not r.has_sufficient_data


# ---------------------------------------------------------------------------
# Signal Logic Tests
# ---------------------------------------------------------------------------

class TestRSSignalLogic:

    def test_score_range(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        logic = RSSignalLogic()
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        for feat in results:
            o = logic.compute(feat)
            assert -4.0 <= o.rs_score <= 4.0, f"{o.symbol} score={o.rs_score}"

    def test_norm(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        logic = RSSignalLogic()
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        for feat in results:
            o = logic.compute(feat)
            if o.has_sufficient_data:
                assert abs(o.rs_norm - o.rs_score / 4.0) < 1e-9

    def test_signal_code_valid(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        logic = RSSignalLogic()
        valid_codes = {
            "RS_TOP_LEADER", "RS_EMERGING_LEADER", "RS_OUTPERFORMER",
            "RS_MILD_OUTPERFORM", "RS_NEUTRAL", "RS_MILD_UNDERPERFORM",
            "RS_UNDERPERFORMER", "RS_DETERIORATING", "RS_BOTTOM_LAGGARD",
        }
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        for feat in results:
            o = logic.compute(feat)
            if o.has_sufficient_data:
                assert o.signal_code in valid_codes, f"{o.symbol} code={o.signal_code}"

    def test_quality_range(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        logic = RSSignalLogic()
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        for feat in results:
            o = logic.compute(feat)
            assert 0 <= o.signal_quality <= 4

    def test_strong_outperformer_positive(self):
        """Decile 1 + RISING -> high positive score."""
        logic = RSSignalLogic()
        f = RSFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            rs_5d=1.5, rs_20d=1.3, rs_60d=1.2,
            rs_rank_20d=95.0, rs_decile=1, rs_trend="RISING",
            rs_rank_change_10d=5.0, rs_slope=0.01, rs_acceleration=0.005,
            all_periods_agree=True, all_periods_direction=1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.rs_score == 4.0  # 4(matrix) + 1(all_agree) + 1(accel) -> clamped to 4
        assert o.signal_code == "RS_TOP_LEADER"

    def test_strong_underperformer_negative(self):
        """Decile 10 + FALLING -> strong negative score."""
        logic = RSSignalLogic()
        f = RSFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            rs_5d=0.5, rs_20d=0.6, rs_60d=0.7,
            rs_rank_20d=5.0, rs_decile=10, rs_trend="FALLING",
            rs_rank_change_10d=-5.0, rs_slope=-0.01, rs_acceleration=-0.005,
            all_periods_agree=True, all_periods_direction=-1,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.rs_score == -4.0
        assert o.signal_code == "RS_BOTTOM_LAGGARD"

    def test_neutral_middle(self):
        """Decile 5 + FLAT -> 0 score."""
        logic = RSSignalLogic()
        f = RSFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            rs_5d=1.0, rs_20d=1.0, rs_60d=1.0,
            rs_rank_20d=50.0, rs_decile=5, rs_trend="FLAT",
            rs_rank_change_10d=0.0, rs_slope=0.0, rs_acceleration=0.0,
            all_periods_agree=False, all_periods_direction=0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        assert o.rs_score == 0.0
        assert o.signal_code == "RS_NEUTRAL"

    def test_rapid_rank_change_modifier(self):
        """Rapid rank improvement (+25) adds +1."""
        logic = RSSignalLogic()
        f = RSFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="2025-01-31",
            rs_5d=1.2, rs_20d=1.1, rs_60d=1.05,
            rs_rank_20d=65.0, rs_decile=4, rs_trend="FLAT",
            rs_rank_change_10d=25.0,
            has_sufficient_data=True,
        )
        o = logic.compute(f)
        # Primary: decile4+FLAT=1, modifier_rank_change=+1 -> 2
        assert o.modifier_rank_change == 1.0
        assert o.rs_score == 2.0

    def test_deterministic(self, test_dbs):
        mdb, _ = test_dbs
        builder = RSFeatureBuilder(mdb)
        logic = RSSignalLogic()
        results = builder.build_batch(SYMBOLS, TARGET_DATE)
        fpt = [r for r in results if r.symbol == "FPT"][0]
        o1 = logic.compute(fpt)
        o2 = logic.compute(fpt)
        assert o1.rs_score == o2.rs_score

    def test_insufficient_data_returns_zero(self):
        logic = RSSignalLogic()
        f = RSFeatures(
            symbol="TEST", date="2025-02-01", data_cutoff_date="",
            has_sufficient_data=False,
        )
        o = logic.compute(f)
        assert o.rs_score == 0.0
        assert not o.has_sufficient_data


# ---------------------------------------------------------------------------
# Expert Writer Tests
# ---------------------------------------------------------------------------

class TestRSExpertWriter:

    def test_run_all(self, test_dbs):
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        results = w.run_all(TARGET_DATE, symbols=SYMBOLS)
        assert len(results) == len(SYMBOLS)
        sufficient = [r for r in results if r.has_sufficient_data]
        assert len(sufficient) >= 10

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM expert_signals WHERE expert_id='V4RS'"
        ).fetchall()
        conn.close()
        assert len(rows) >= 10

    def test_run_symbol(self, test_dbs):
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        o = w.run_symbol("FPT", TARGET_DATE, universe=SYMBOLS)
        assert isinstance(o, RSOutput)
        assert o.has_sufficient_data

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM expert_signals WHERE symbol='FPT' AND expert_id='V4RS'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert -4 <= row["primary_score"] <= 4

    def test_metadata_fields(self, test_dbs):
        """Metadata must include all required RS features."""
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        w.run_all(TARGET_DATE, symbols=SYMBOLS)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE symbol='FPT' AND expert_id='V4RS'"
        ).fetchone()
        conn.close()

        meta = json.loads(row["metadata_json"])
        required_keys = [
            "rs_5d", "rs_20d", "rs_60d", "rs_rank_20d",
            "rs_decile", "rs_trend", "rs_rank_change_10d", "rs_norm",
        ]
        for key in required_keys:
            assert key in meta, f"Missing metadata key: {key}"

    def test_metadata_json_serializable(self, test_dbs):
        """All metadata values must be JSON-serializable (no numpy types)."""
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        w.run_all(TARGET_DATE, symbols=SYMBOLS)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT metadata_json FROM expert_signals WHERE expert_id='V4RS'"
        ).fetchall()
        conn.close()

        for row in rows:
            meta = json.loads(row["metadata_json"])
            # Re-serialize to ensure no numpy types leaked
            json.dumps(meta)
            # Check specific types
            for k, v in meta.items():
                assert not isinstance(v, (np.bool_, np.integer, np.floating)), (
                    f"Numpy type leaked in metadata key '{k}': {type(v)}"
                )

    def test_idempotent(self, test_dbs):
        """INSERT OR REPLACE should not create duplicates."""
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        w.run_all(TARGET_DATE, symbols=SYMBOLS)
        w.run_all(TARGET_DATE, symbols=SYMBOLS)

        conn = sqlite3.connect(sdb)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM expert_signals WHERE symbol='FPT' AND date=? AND expert_id='V4RS'",
            (TARGET_DATE,),
        ).fetchone()[0]
        conn.close()
        assert cnt == 1

    def test_score_diversity(self, test_dbs):
        """With diverse return profiles, scores should not all be the same."""
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        results = w.run_all(TARGET_DATE, symbols=SYMBOLS)
        scores = [r.rs_score for r in results if r.has_sufficient_data]
        assert len(set(scores)) > 1, "All scores are identical — likely a bug"

    def test_outperformer_higher_than_underperformer(self, test_dbs):
        """FPT (strong drift) should score higher than VIC (negative drift)."""
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        results = w.run_all(TARGET_DATE, symbols=SYMBOLS)
        result_map = {r.symbol: r for r in results}
        fpt = result_map.get("FPT")
        vic = result_map.get("VIC")
        if fpt and vic and fpt.has_sufficient_data and vic.has_sufficient_data:
            assert fpt.rs_score > vic.rs_score, (
                f"FPT score={fpt.rs_score} should be > VIC score={vic.rs_score}"
            )

    def test_secondary_score_is_norm(self, test_dbs):
        """secondary_score in DB should equal rs_norm."""
        mdb, sdb = test_dbs
        w = RSExpertWriter(mdb, sdb)
        w.run_all(TARGET_DATE, symbols=SYMBOLS)

        conn = sqlite3.connect(sdb)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT primary_score, secondary_score FROM expert_signals WHERE expert_id='V4RS'"
        ).fetchall()
        conn.close()

        for row in rows:
            expected_norm = row["primary_score"] / 4.0
            assert abs(row["secondary_score"] - expected_norm) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
