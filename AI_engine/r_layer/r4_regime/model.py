"""
R4 Regime — LightGBM multiclass for market regime prediction.
Predicts VNINDEX T+20 return bucket as regime class (-4 to +4).
Market-wide model: same prediction for all symbols on a given date.
"""

from datetime import datetime
import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from sklearn.metrics import accuracy_score

from ..base_model import RBaseModel


REGIME_BINS = [-0.08, -0.05, -0.03, -0.01, 0.01, 0.03, 0.05, 0.08]
REGIME_CLASSES = [-4, -3, -2, -1, 0, 1, 2, 3, 4]


def _return_to_regime(ret: float) -> int:
    """Map return to regime class."""
    for i, edge in enumerate(REGIME_BINS):
        if ret < edge:
            return REGIME_CLASSES[i]
    return REGIME_CLASSES[-1]


class R4Model(RBaseModel):
    MODEL_ID = "R4"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        if not HAS_LIGHTGBM:
            raise ImportError("lightgbm required for R4")

    def train(self, train_start, train_end, horizon=20, **kwargs):
        # Load VNINDEX labels for regime target
        labels = self.load_labels(train_start, train_end, horizon, symbols=["VNINDEX"])
        if labels.empty:
            return {"error": "no VNINDEX labels"}

        # Create regime target
        labels["regime_class"] = labels["target_return"].apply(_return_to_regime)
        regime_by_date = dict(zip(labels["feature_date"], labels["regime_class"]))

        # Load features for all symbols
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no feature data"}

        # Get dates from the merged data — need to reload with dates
        features = self.load_feature_matrix(train_start, train_end)
        feat_labels = self.load_labels(train_start, train_end, horizon)
        if features.empty or feat_labels.empty:
            return {"error": "no data"}

        merged = features.merge(
            feat_labels, left_on=["symbol", "date"],
            right_on=["symbol", "feature_date"], how="inner",
        )
        merged["regime_target"] = merged["date"].map(regime_by_date)
        merged = merged.dropna(subset=["regime_target"])

        if len(merged) < 100:
            return {"error": "insufficient data"}

        non_feat = {"symbol", "date", "feature_date", "close_t",
                    "target_return", "target_label", "regime_target", "snapshot_time"}
        feat_cols = [c for c in merged.columns if c not in non_feat]
        X_train = merged[feat_cols].astype(float).fillna(0.0)
        y_regime = merged["regime_target"].astype(int)

        # Shift classes to 0-8 for LightGBM
        y_shifted = y_regime + 4  # -4..+4 → 0..8

        self.model = lgb.LGBMClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            num_leaves=31, verbose=-1, random_state=42,
            num_class=9, objective="multiclass",
        )
        self.model.fit(X_train, y_shifted)
        self.model_version = f"R4_v1_{datetime.now():%Y%m%d}"

        preds = self.model.predict(X_train)
        metrics = {
            "accuracy": round(accuracy_score(y_shifted, preds), 4),
            "samples": len(X_train),
            "classes": 9,
        }

        self.write_training_history(
            train_date=datetime.now().strftime("%Y-%m-%d"),
            data_start=train_start, data_end=train_end,
            sample_count=len(X_train), metrics=metrics,
        )
        self._feature_names = feat_cols
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
        trained_classes = list(self.model.classes_)  # actual classes present

        results = []
        for i in range(len(sym_dates)):
            p = probs[i]
            # Expected regime score using actual trained classes (shifted back to -4..+4)
            expected = sum((int(trained_classes[j]) - 4) * float(p[j]) for j in range(len(trained_classes)))
            score = max(-4.0, min(4.0, expected))
            confidence = float(max(p))

            # Derive vol/liq from features
            vol_score = float(X_feat.iloc[i].get("volatility_group_score", 0.0)) * 4
            vol_score = max(0.0, min(4.0, abs(vol_score)))
            liq_score = float(X_feat.iloc[i].get("context_group_score", 0.0)) * 2
            liq_score = max(-2.0, min(2.0, liq_score))

            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)
            results.append({
                "symbol": sym_dates.iloc[i]["symbol"],
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "direction": direction,
                "vol_regime": round(vol_score, 4),
                "liq_regime": round(liq_score, 4),
            })
        return results
