"""
R7 CatBoost — Regime-Aware Classification model
Monotonic constraints + sample weighting per market regime.
"""

from datetime import datetime
import sqlite3
import numpy as np
import pandas as pd

try:
    from catboost import CatBoostClassifier, Pool
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False

from sklearn.metrics import accuracy_score, f1_score
from ..base_model import RBaseModel

# Monotonic constraints per AI_STOCK_MONOTONIC_CONSTRAINT_MAP
# Maps feature column name -> constraint (1=positive, -1=negative, 0=neutral)
MONOTONIC_CONSTRAINTS = {
    # Positive: higher value → more bullish
    "v4p_trend_persistence": 1,
    "v4ma_alignment_score": 1,
    "trend_strength_max": 1,
    "v4rs_rank": 1,
    "sector_momentum": 1,
    "momentum_group_score": 1,
    "v4v_volume_ratio_20": 1,
    "volume_pressure": 1,
    "v4liq_liquidity_shock": 1,
    "liquidity_shock_avg": 1,
    "trend_group_score": 1,
    "trend_alignment_score": 1,
    "expert_alignment_score": 1,
    # Negative: higher value → less bullish
    "v4atr_pct": -1,
    "v4atr_percentile": -1,
    "v4bb_width": -1,
    "volatility_group_score": -1,
    # Neutral: no constraint (oscillators, patterns, flags)
    "v4rsi_norm": 0,
    "v4sto_norm": 0,
    "v4macd_hist_slope": 0,
    "v4candle_volume_confirm": 0,
    "v4p_breakout20_flag": 0,
    "v4p_breakout60_flag": 0,
}


class R7Model(RBaseModel):
    MODEL_ID = "R7"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        self.feature_importances_ = None
        if not HAS_CATBOOST:
            raise ImportError("catboost required for R7. pip install catboost")

    def _compute_sample_weights(self, X: pd.DataFrame) -> np.ndarray:
        """
        Compute sample weights based on market regime.
        Strong Bear (regime_score <= -3): 5.0x
        Bear (regime_score <= -2): 3.0x
        Sideways (-1..+1): 1.5x
        Bull (regime_score >= +2): 1.0x
        """
        weights = np.ones(len(X), dtype=float)

        if "regime_score" in X.columns:
            regime = X["regime_score"].values
            # regime_score is already normalized by /4 in feature_normalizer
            # so -1..+1 maps to raw -4..+4. Multiply back for thresholds.
            raw_regime = regime * 4.0
        else:
            return weights

        for i in range(len(raw_regime)):
            r = raw_regime[i]
            if r <= -3.0:
                weights[i] = 5.0
            elif r <= -2.0:
                weights[i] = 3.0
            elif -1.0 <= r <= 1.0:
                weights[i] = 1.5
            else:
                weights[i] = 1.0

        return weights

    def _build_constraints(self, feature_names: list[str]) -> list[int]:
        """Build monotonic constraints vector aligned with feature order."""
        return [MONOTONIC_CONSTRAINTS.get(f, 0) for f in feature_names]

    def train(self, train_start, train_end, horizon=5, **kwargs):
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no data"}
        if len(X) < 100:
            return {"error": "insufficient data"}

        # Binary classification: UP=1 vs NOT_UP=0 (enables monotonic constraints)
        y_binary = (y_label == "UP").astype(int)

        # Compute regime-aware sample weights
        sample_weights = self._compute_sample_weights(X)

        # Build monotonic constraints
        constraints = self._build_constraints(list(X.columns))
        n_constrained = sum(1 for c in constraints if c != 0)

        # CatBoost: CPU required for monotonic constraints
        self.model = CatBoostClassifier(
            iterations=2000, depth=6, learning_rate=0.02,
            l2_leaf_reg=8, random_seed=42, verbose=0,
            task_type="CPU", thread_count=-1,
            auto_class_weights="Balanced",
            monotone_constraints=constraints,
        )
        self.model.fit(X, y_binary, sample_weight=sample_weights)
        self.model_version = f"R7_v2_{datetime.now():%Y%m%d}"
        self._binary_mode = True
        self.feature_importances_ = dict(zip(X.columns, self.model.feature_importances_))

        preds = self.model.predict(X).flatten()
        metrics = {
            "accuracy": round(accuracy_score(y_binary, preds), 4),
            "f1_weighted": round(f1_score(y_binary, preds, average="weighted"), 4),
            "samples": len(X),
            "positive_rate": round(float(y_binary.mean()), 4),
            "monotonic_constrained": n_constrained,
            "bear_weight_samples": int(np.sum(sample_weights >= 3.0)),
        }

        self.write_training_history(
            train_date=datetime.now().strftime("%Y-%m-%d"),
            data_start=train_start, data_end=train_end,
            sample_count=len(X), metrics=metrics,
        )
        self._feature_names = list(X.columns)
        return metrics

    def predict(self, date, symbols=None):
        if self.model is None:
            return []

        X = self.load_feature_matrix(date, date, symbols)
        if X.empty:
            return []

        sym_dates = X[["symbol", "date"]].copy()
        X_feat = X.drop(columns=["symbol", "date"], errors="ignore")
        for col in self._feature_names:
            if col not in X_feat.columns:
                X_feat[col] = 0.0
        X_feat = X_feat[self._feature_names].fillna(0.0)

        probs = self.model.predict_proba(X_feat)

        results = []
        for i in range(len(sym_dates)):
            # Binary mode: probs = [p_not_up, p_up]
            p_up = float(probs[i][1]) if probs.shape[1] > 1 else float(probs[i][0])
            p_not_up = 1.0 - p_up

            # Score: positive = bullish, scaled to -4..+4
            score = max(-4.0, min(4.0, (p_up - 0.5) * 8))
            confidence = max(p_up, p_not_up)

            # Hard threshold: only emit BUY when prob_up >= 0.78
            # Target: ~1000 signals / 3000 days
            if p_up < 0.78:
                score = 0.0

            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)

            results.append({
                "symbol": sym_dates.iloc[i]["symbol"],
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "direction": direction,
            })
        return results
