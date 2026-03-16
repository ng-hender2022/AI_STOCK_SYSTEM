"""
R0 Baseline — Logistic Regression
Simplest model for benchmarking. Binary UP vs DOWN.
"""

from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

from ..base_model import RBaseModel


class R0Model(RBaseModel):
    MODEL_ID = "R0"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        self.model = None

    def train(self, train_start, train_end, horizon=5, **kwargs):
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no data"}

        # Binary: keep only UP and DOWN
        mask = y_label.isin(["UP", "DOWN"])
        X_bin = X[mask].reset_index(drop=True)
        y_bin = (y_label[mask] == "UP").astype(int).reset_index(drop=True)

        if len(X_bin) < 50:
            return {"error": "insufficient data"}

        # Train
        self.model = LogisticRegression(
            C=1.0, max_iter=500, class_weight="balanced", solver="lbfgs"
        )
        self.model.fit(X_bin, y_bin)
        self.model_version = f"R0_v1_{datetime.now():%Y%m%d}"

        # Metrics
        preds = self.model.predict(X_bin)
        metrics = {
            "accuracy": round(accuracy_score(y_bin, preds), 4),
            "f1": round(f1_score(y_bin, preds), 4),
            "samples": len(X_bin),
        }

        self.write_training_history(
            train_date=datetime.now().strftime("%Y-%m-%d"),
            data_start=train_start, data_end=train_end,
            sample_count=len(X_bin), metrics=metrics,
        )
        self._feature_names = list(X_bin.columns)
        return metrics

    def predict(self, date, symbols=None):
        if self.model is None:
            return []

        X = self.load_feature_matrix(date, date, symbols)
        if X.empty:
            return []

        sym_dates = X[["symbol", "date"]].copy()
        X_feat = X.drop(columns=["symbol", "date"], errors="ignore")

        # Align columns
        for col in self._feature_names:
            if col not in X_feat.columns:
                X_feat[col] = 0.0
        X_feat = X_feat[self._feature_names].fillna(0.0)

        probs = self.model.predict_proba(X_feat)
        prob_up = probs[:, 1] if probs.shape[1] == 2 else probs[:, 0]

        results = []
        for i in range(len(sym_dates)):
            p = float(prob_up[i])
            score = max(-4.0, min(4.0, (2 * p - 1) * 4))
            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)
            results.append({
                "symbol": sym_dates.iloc[i]["symbol"],
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(max(p, 1 - p), 4),
                "direction": direction,
            })
        return results
