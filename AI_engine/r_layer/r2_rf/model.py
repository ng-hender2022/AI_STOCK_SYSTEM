"""
R2 Random Forest — Robust nonlinear classifier
Captures rule interactions. Good baseline nonlinear learner.
"""

from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

from ..base_model import RBaseModel


class R2Model(RBaseModel):
    MODEL_ID = "R2"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        self.feature_importances_ = None

    def train(self, train_start, train_end, horizon=5, **kwargs):
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no data"}
        if len(X) < 100:
            return {"error": "insufficient data"}

        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_leaf=20,
            class_weight="balanced", n_jobs=-1, random_state=42,
        )
        self.model.fit(X, y_label)
        self.model_version = f"R2_v1_{datetime.now():%Y%m%d}"
        self.feature_importances_ = dict(zip(X.columns, self.model.feature_importances_))

        preds = self.model.predict(X)
        metrics = {
            "accuracy": round(accuracy_score(y_label, preds), 4),
            "f1_weighted": round(f1_score(y_label, preds, average="weighted"), 4),
            "samples": len(X),
            "n_classes": len(self.model.classes_),
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
        classes = list(self.model.classes_)

        results = []
        for i in range(len(sym_dates)):
            prob_dict = {c: float(probs[i][j]) for j, c in enumerate(classes)}
            p_up = prob_dict.get("UP", 0.0)
            p_down = prob_dict.get("DOWN", 0.0)

            score = max(-4.0, min(4.0, (p_up - p_down) * 4))
            confidence = max(p_up, p_down, prob_dict.get("NEUTRAL", 0.0))
            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)

            results.append({
                "symbol": sym_dates.iloc[i]["symbol"],
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "direction": direction,
            })
        return results
