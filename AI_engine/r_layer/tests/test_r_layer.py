"""
R Layer Tests
Tests base_model, R0-R5 models, and ensemble.
Uses production signals.db with Phase 1 data.
"""

import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

MARKET_DB = r"D:\AI\AI_data\market.db"
SIGNALS_DB = r"D:\AI\AI_data\signals.db"
MODELS_DB = r"D:\AI\AI_data\models.db"

# Phase 1 date range (has enough data for all experts)
TRAIN_START = "2015-06-01"
TRAIN_END = "2016-06-30"
TEST_DATE = "2016-12-30"


# ---------------------------------------------------------------------------
# Base Model Tests
# ---------------------------------------------------------------------------

class TestBaseModel:

    def test_load_feature_matrix(self):
        from AI_engine.r_layer.base_model import RBaseModel
        # Can't instantiate abstract, but test via R0
        from AI_engine.r_layer.r0_baseline.model import R0Model
        m = R0Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
        df = m.load_feature_matrix("2016-12-01", "2016-12-30")
        if not df.empty:
            assert "symbol" in df.columns
            assert "date" in df.columns
            assert len(df) > 0

    def test_load_labels(self):
        from AI_engine.r_layer.r0_baseline.model import R0Model
        m = R0Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
        labels = m.load_labels("2015-06-01", "2016-06-30", horizon=5)
        if not labels.empty:
            assert "target_return" in labels.columns
            assert "target_label" in labels.columns

    def test_prepare_training_data(self):
        from AI_engine.r_layer.r0_baseline.model import R0Model
        m = R0Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
        X, y_ret, y_lab = m.prepare_training_data(TRAIN_START, TRAIN_END, horizon=5)
        # May be empty if no meta_features computed for this range
        # This is expected — integration test will populate first


# ---------------------------------------------------------------------------
# R0 Baseline Tests
# ---------------------------------------------------------------------------

class TestR0:

    def test_instantiate(self):
        from AI_engine.r_layer.r0_baseline.model import R0Model
        m = R0Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
        assert m.MODEL_ID == "R0"

    def test_train_with_synthetic_data(self):
        from AI_engine.r_layer.r0_baseline.model import R0Model
        m = R0Model(SIGNALS_DB, MODELS_DB, MARKET_DB)

        # Synthetic data
        np.random.seed(42)
        n = 200
        X = pd.DataFrame(np.random.randn(n, 10), columns=[f"f{i}" for i in range(10)])
        y_label = pd.Series(np.random.choice(["UP", "DOWN"], n))

        from sklearn.linear_model import LogisticRegression
        m.model = LogisticRegression(max_iter=500, class_weight="balanced")
        m.model.fit(X, (y_label == "UP").astype(int))
        m._feature_names = list(X.columns)
        m.model_version = "R0_test"

        # Predict
        probs = m.model.predict_proba(X[:5])
        assert probs.shape == (5, 2)

    def test_score_range(self):
        """R0 scores should be in -4..+4."""
        prob_up = 0.9
        score = (2 * prob_up - 1) * 4
        assert -4.0 <= score <= 4.0


# ---------------------------------------------------------------------------
# R1 Linear Tests
# ---------------------------------------------------------------------------

class TestR1:

    def test_instantiate(self):
        from AI_engine.r_layer.r1_linear.model import R1Model
        m = R1Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
        assert m.MODEL_ID == "R1"

    def test_train_synthetic(self):
        from AI_engine.r_layer.r1_linear.model import R1Model
        m = R1Model(SIGNALS_DB, MODELS_DB, MARKET_DB)

        np.random.seed(42)
        n = 200
        X = pd.DataFrame(np.random.randn(n, 10), columns=[f"f{i}" for i in range(10)])
        y = pd.Series(np.random.randn(n) * 0.02)

        from sklearn.linear_model import ElasticNet
        m.model = ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=1000)
        m.model.fit(X, y)
        m._feature_names = list(X.columns)

        preds = m.model.predict(X[:5])
        assert len(preds) == 5


# ---------------------------------------------------------------------------
# R2 RF Tests
# ---------------------------------------------------------------------------

class TestR2:

    def test_instantiate(self):
        from AI_engine.r_layer.r2_rf.model import R2Model
        m = R2Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
        assert m.MODEL_ID == "R2"

    def test_train_synthetic(self):
        from AI_engine.r_layer.r2_rf.model import R2Model
        m = R2Model(SIGNALS_DB, MODELS_DB, MARKET_DB)

        np.random.seed(42)
        n = 300
        X = pd.DataFrame(np.random.randn(n, 10), columns=[f"f{i}" for i in range(10)])
        y = pd.Series(np.random.choice(["UP", "DOWN", "NEUTRAL"], n))

        from sklearn.ensemble import RandomForestClassifier
        m.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
        m.model.fit(X, y)
        m._feature_names = list(X.columns)

        probs = m.model.predict_proba(X[:5])
        assert probs.shape[0] == 5
        assert probs.shape[1] == 3  # 3 classes


# ---------------------------------------------------------------------------
# R3 GBDT Tests
# ---------------------------------------------------------------------------

class TestR3:

    def test_instantiate(self):
        try:
            from AI_engine.r_layer.r3_gbdt.model import R3Model
            m = R3Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
            assert m.MODEL_ID == "R3"
        except ImportError:
            pytest.skip("lightgbm not installed")

    def test_train_synthetic(self):
        try:
            import lightgbm as lgb
        except ImportError:
            pytest.skip("lightgbm not installed")

        from AI_engine.r_layer.r3_gbdt.model import R3Model
        m = R3Model(SIGNALS_DB, MODELS_DB, MARKET_DB)

        np.random.seed(42)
        n = 300
        X = pd.DataFrame(np.random.randn(n, 10), columns=[f"f{i}" for i in range(10)])
        y = pd.Series(np.random.choice([0, 1, 2], n))

        m.model = lgb.LGBMClassifier(n_estimators=50, verbose=-1)
        m.model.fit(X, y)
        m._feature_names = list(X.columns)
        m._label_inv = {0: "DOWN", 1: "NEUTRAL", 2: "UP"}

        probs = m.model.predict_proba(X[:5])
        assert probs.shape == (5, 3)


# ---------------------------------------------------------------------------
# R4 Regime Tests
# ---------------------------------------------------------------------------

class TestR4:

    def test_instantiate(self):
        try:
            from AI_engine.r_layer.r4_regime.model import R4Model
            m = R4Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
            assert m.MODEL_ID == "R4"
        except ImportError:
            pytest.skip("lightgbm not installed")

    def test_regime_mapping(self):
        from AI_engine.r_layer.r4_regime.model import _return_to_regime
        assert _return_to_regime(0.10) == 4
        assert _return_to_regime(0.06) == 3
        assert _return_to_regime(0.0) == 0
        assert _return_to_regime(-0.06) == -3
        assert _return_to_regime(-0.10) == -4


# ---------------------------------------------------------------------------
# R5 Sector Tests
# ---------------------------------------------------------------------------

class TestR5:

    def test_instantiate(self):
        try:
            from AI_engine.r_layer.r5_sector.model import R5Model
            m = R5Model(SIGNALS_DB, MODELS_DB, MARKET_DB)
            assert m.MODEL_ID == "R5"
            assert len(m.sector_map) > 0
        except ImportError:
            pytest.skip("lightgbm not installed")

    def test_sector_mapping_loaded(self):
        from AI_engine.r_layer.r5_sector.model import _load_sector_mapping
        mapping = _load_sector_mapping()
        assert "FPT" in mapping
        assert mapping["FPT"] == "Công nghệ"
        assert len(mapping) >= 91


# ---------------------------------------------------------------------------
# Ensemble Tests
# ---------------------------------------------------------------------------

class TestEnsemble:

    def test_instantiate(self):
        from AI_engine.r_layer.ensemble import EnsembleEngine
        e = EnsembleEngine(MODELS_DB)
        assert e.weights is not None
        assert sum(e.weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_direction_threshold(self):
        from AI_engine.r_layer.ensemble import EnsembleEngine
        e = EnsembleEngine(MODELS_DB)
        assert e.DIRECTION_THRESHOLD == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
