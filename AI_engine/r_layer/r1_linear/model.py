"""
R1 Linear — ElasticNet Regression
Captures linear factor relationships. Interpretable baseline.
"""

from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_squared_error, r2_score

from ..base_model import RBaseModel


class R1Model(RBaseModel):
    MODEL_ID = "R1"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        self.scale_factor = 200

    def train(self, train_start, train_end, horizon=5, **kwargs):
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no data"}
        if len(X) < 50:
            return {"error": "insufficient data"}

        self.model = ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=1000)
        self.model.fit(X, y_return)
        self.model_version = f"R1_v1_{datetime.now():%Y%m%d}"

        preds = self.model.predict(X)
        metrics = {
            "mse": round(float(mean_squared_error(y_return, preds)), 6),
            "r2": round(float(r2_score(y_return, preds)), 4),
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

        raw_preds = self.model.predict(X_feat)
        results = []
        for i in range(len(sym_dates)):
            raw = float(raw_preds[i])
            score = max(-4.0, min(4.0, raw * self.scale_factor))
            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)
            confidence = min(1.0, abs(score) / 4.0)
            results.append({
                "symbol": sym_dates.iloc[i]["symbol"],
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "direction": direction,
            })
        return results
