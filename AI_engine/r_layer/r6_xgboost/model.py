"""
R6 XGBoost — Classification model
Alternative gradient boosting to R3 (LightGBM). Different regularization approach.
"""

from datetime import datetime
import numpy as np
import pandas as pd

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from sklearn.metrics import accuracy_score, f1_score
from ..base_model import RBaseModel
from ..regime_filter import RegimeFilter


class R6Model(RBaseModel):
    MODEL_ID = "R6"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        self.feature_importances_ = None
        if not HAS_XGBOOST:
            raise ImportError("xgboost required for R6. pip install xgboost")

    def train(self, train_start, train_end, horizon=5, **kwargs):
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no data"}
        if len(X) < 100:
            return {"error": "insufficient data"}

        label_map = {"DOWN": 0, "NEUTRAL": 1, "UP": 2}
        y_encoded = y_label.map(label_map).fillna(1).astype(int)

        self.model = xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=20,
            eval_metric="mlogloss", use_label_encoder=False,
            device="cuda", verbosity=0, random_state=42,
        )
        self.model.fit(X, y_encoded)
        self.model_version = f"R6_v1_{datetime.now():%Y%m%d}"
        self._label_map = label_map
        self._label_inv = {v: k for k, v in label_map.items()}
        self.feature_importances_ = dict(zip(X.columns, self.model.feature_importances_))

        preds = self.model.predict(X)
        pred_labels = pd.Series(preds).map(self._label_inv)
        metrics = {
            "accuracy": round(accuracy_score(y_label, pred_labels), 4),
            "f1_weighted": round(f1_score(y_label, pred_labels, average="weighted"), 4),
            "samples": len(X),
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

        # Regime filter
        rf = RegimeFilter(self.market_db)
        regime_ctx = rf.get_regime_context(date)

        probs = self.model.predict_proba(X_feat)

        results = []
        for i in range(len(sym_dates)):
            p_down = float(probs[i][0])
            p_neut = float(probs[i][1]) if probs.shape[1] > 2 else 0.0
            p_up = float(probs[i][-1])

            score = max(-4.0, min(4.0, (p_up - p_down) * 4))
            score = rf.apply_filter(score, p_up, regime_ctx, base_threshold=0.57)
            confidence = max(p_up, p_down, p_neut)
            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)

            results.append({
                "symbol": sym_dates.iloc[i]["symbol"],
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "direction": direction,
            })
        return results
