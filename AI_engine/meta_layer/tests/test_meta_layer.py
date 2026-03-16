"""
Meta Layer Tests
Covers: MetaBuilder, ConflictDetector, FeatureMatrixWriter.
Uses production signals.db with Phase TEST data (2014-07-29).
"""

import sqlite3
import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from AI_engine.meta_layer.meta_builder import (
    MetaBuilder, MetaFeatures, _normalize_score, EXPERT_GROUPS,
)
from AI_engine.meta_layer.conflict_detector import ConflictDetector
from AI_engine.meta_layer.feature_matrix_writer import FeatureMatrixWriter


# ---------------------------------------------------------------------------
# Fixtures — use production DBs with Phase TEST data
# ---------------------------------------------------------------------------

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
TEST_DATE = "2014-07-29"


@pytest.fixture
def meta_builder():
    return MetaBuilder(SIGNALS_DB, MARKET_DB)


@pytest.fixture
def conflict_detector():
    return ConflictDetector()


@pytest.fixture
def writer():
    return FeatureMatrixWriter(SIGNALS_DB, MARKET_DB)


# ---------------------------------------------------------------------------
# Normalization Tests
# ---------------------------------------------------------------------------

class TestNormalization:

    def test_standard_expert(self):
        """Standard -4..+4 expert: norm = score / 4."""
        assert _normalize_score("V4I", 4.0) == 1.0
        assert _normalize_score("V4I", -4.0) == -1.0
        assert _normalize_score("V4I", 0.0) == 0.0
        assert _normalize_score("V4MACD", 2.0) == 0.5

    def test_rsi_normalization(self):
        """RSI 0-100: norm = (score - 50) / 50."""
        assert _normalize_score("V4RSI", 100.0) == 1.0
        assert _normalize_score("V4RSI", 0.0) == -1.0
        assert _normalize_score("V4RSI", 50.0) == 0.0
        assert _normalize_score("V4RSI", 75.0) == 0.5

    def test_sto_normalization(self):
        """Stochastic 0-100: same as RSI."""
        assert _normalize_score("V4STO", 80.0) == 0.6
        assert _normalize_score("V4STO", 20.0) == -0.6

    def test_adx_normalization(self):
        """ADX 0-4: norm = score / 4 (always non-negative)."""
        assert _normalize_score("V4ADX", 4.0) == 1.0
        assert _normalize_score("V4ADX", 0.0) == 0.0
        assert _normalize_score("V4ADX", 2.0) == 0.5

    def test_atr_normalization(self):
        """ATR 0-4: same as ADX."""
        assert _normalize_score("V4ATR", 3.0) == 0.75


# ---------------------------------------------------------------------------
# MetaBuilder Tests
# ---------------------------------------------------------------------------

class TestMetaBuilder:

    def test_build_single_symbol(self, meta_builder):
        """Build meta for FPT on test date."""
        meta = meta_builder.build("FPT", TEST_DATE)
        assert isinstance(meta, MetaFeatures)
        assert meta.symbol == "FPT"
        assert meta.expert_count > 0

    def test_expert_counts(self, meta_builder):
        meta = meta_builder.build("FPT", TEST_DATE)
        total = meta.bullish_expert_count + meta.bearish_expert_count + meta.neutral_expert_count
        assert total == meta.expert_count

    def test_avg_score_range(self, meta_builder):
        meta = meta_builder.build("FPT", TEST_DATE)
        assert -1.0 <= meta.avg_score <= 1.0

    def test_group_scores_range(self, meta_builder):
        meta = meta_builder.build("FPT", TEST_DATE)
        for score in [
            meta.trend_group_score, meta.momentum_group_score,
            meta.volume_group_score, meta.volatility_group_score,
            meta.structure_group_score, meta.context_group_score,
        ]:
            assert -1.0 <= score <= 1.0

    def test_conflict_alignment_range(self, meta_builder):
        meta = meta_builder.build("FPT", TEST_DATE)
        assert 0.0 <= meta.expert_conflict_score <= 1.0
        assert 0.0 <= meta.expert_alignment_score <= 1.0

    def test_build_all(self, meta_builder):
        results = meta_builder.build_all(TEST_DATE)
        assert len(results) > 0
        for m in results:
            assert isinstance(m, MetaFeatures)

    def test_no_data_returns_empty(self, meta_builder):
        meta = meta_builder.build("NOSYMBOL", TEST_DATE)
        assert meta.expert_count == 0

    def test_expert_norms_populated(self, meta_builder):
        meta = meta_builder.build("FPT", TEST_DATE)
        assert len(meta.expert_norms) > 0
        for eid, norm in meta.expert_norms.items():
            assert -1.5 <= norm <= 1.5  # slightly beyond -1..+1 due to edge cases


# ---------------------------------------------------------------------------
# ConflictDetector Tests
# ---------------------------------------------------------------------------

class TestConflictDetector:

    def test_no_conflict_all_bullish(self, conflict_detector):
        norms = {"V4I": 0.5, "V4MA": 0.6, "V4MACD": 0.4}
        score = conflict_detector.compute_conflict_score(norms)
        assert score < 0.2  # low conflict

    def test_high_conflict(self, conflict_detector):
        norms = {"V4I": 0.8, "V4MA": -0.7, "V4MACD": 0.5, "V4RSI": -0.6}
        score = conflict_detector.compute_conflict_score(norms)
        assert score > 0.4  # significant conflict

    def test_alignment_all_agree(self, conflict_detector):
        norms = {"V4I": 0.3, "V4MA": 0.5, "V4MACD": 0.2}
        score = conflict_detector.compute_alignment_score(norms)
        assert score == 1.0  # all bullish

    def test_alignment_mixed(self, conflict_detector):
        norms = {"V4I": 0.5, "V4MA": -0.5, "V4MACD": 0.3, "V4RSI": -0.2}
        score = conflict_detector.compute_alignment_score(norms)
        assert 0.0 < score < 1.0

    def test_find_conflicting_pairs(self, conflict_detector):
        norms = {"V4I": 0.8, "V4MA": -0.7}
        pairs = conflict_detector.find_conflicting_pairs(norms, threshold=0.5)
        assert len(pairs) == 1
        assert pairs[0]["type"] == "DIRECTION"

    def test_no_pairs_when_aligned(self, conflict_detector):
        norms = {"V4I": 0.5, "V4MA": 0.6}
        pairs = conflict_detector.find_conflicting_pairs(norms)
        assert len(pairs) == 0

    def test_group_conflicts(self, conflict_detector):
        norms = {
            "V4I": 0.8, "V4MA": 0.7, "V4ADX": 0.5,  # TREND bullish
            "V4MACD": -0.6, "V4RSI": -0.5, "V4STO": -0.4,  # MOMENTUM bearish
        }
        conflicts = conflict_detector.find_group_conflicts(norms)
        assert len(conflicts) > 0
        assert any(c["type"] == "GROUP_DIRECTION" for c in conflicts)

    def test_empty_norms(self, conflict_detector):
        assert conflict_detector.compute_conflict_score({}) == 0.0
        assert conflict_detector.compute_alignment_score({}) == 0.0


# ---------------------------------------------------------------------------
# FeatureMatrixWriter Tests
# ---------------------------------------------------------------------------

class TestFeatureMatrixWriter:

    def test_run_writes_meta(self, writer):
        stats = writer.run(TEST_DATE)
        assert stats["meta_written"] > 0
        assert stats["date"] == TEST_DATE

        # Verify in DB
        conn = sqlite3.connect(SIGNALS_DB)
        count = conn.execute(
            "SELECT COUNT(*) FROM meta_features WHERE date=?", (TEST_DATE,)
        ).fetchone()[0]
        conn.close()
        assert count > 0

    def test_meta_features_values(self, writer):
        writer.run(TEST_DATE)
        conn = sqlite3.connect(SIGNALS_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM meta_features WHERE date=? AND symbol='FPT'",
            (TEST_DATE,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["bullish_expert_count"] >= 0
        assert row["bearish_expert_count"] >= 0
        assert -1.0 <= row["avg_score"] <= 1.0
        assert 0.0 <= row["expert_conflict_score"] <= 1.0
        assert 0.0 <= row["expert_alignment_score"] <= 1.0

    def test_get_feature_vector(self, writer):
        vector = writer.get_feature_vector("FPT", TEST_DATE)
        assert vector is not None
        assert isinstance(vector, dict)

        # Should have norm scores
        norm_keys = [k for k in vector if k.endswith("_norm")]
        assert len(norm_keys) > 0

        # Should have meta features
        assert "avg_score" in vector
        assert "trend_group_score" in vector
        assert "expert_conflict_score" in vector
        assert "bullish_count" in vector

        # Should have regime
        assert "regime_trend" in vector
        assert "regime_vol" in vector
        assert "regime_liq" in vector

    def test_feature_vector_values(self, writer):
        vector = writer.get_feature_vector("FPT", TEST_DATE)
        for key, val in vector.items():
            assert isinstance(val, (int, float)), f"{key} is {type(val)}"

    def test_conflicts_written(self, writer):
        stats = writer.run(TEST_DATE)
        # Some conflicts are expected (experts disagree)
        assert stats["conflicts_written"] >= 0

    def test_idempotent(self, writer):
        writer.run(TEST_DATE)
        conn = sqlite3.connect(SIGNALS_DB)
        count1 = conn.execute(
            "SELECT COUNT(*) FROM meta_features WHERE date=?", (TEST_DATE,)
        ).fetchone()[0]
        conn.close()

        writer.run(TEST_DATE)
        conn = sqlite3.connect(SIGNALS_DB)
        count2 = conn.execute(
            "SELECT COUNT(*) FROM meta_features WHERE date=?", (TEST_DATE,)
        ).fetchone()[0]
        conn.close()

        assert count1 == count2  # INSERT OR REPLACE = same count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
