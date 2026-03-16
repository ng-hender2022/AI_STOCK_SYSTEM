"""
R5 Sector — Per-sector LightGBM regression models.
One model per sector (14 sectors). Small sectors use global fallback.
"""

from datetime import datetime
import re
import numpy as np
import pandas as pd
from pathlib import Path

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

from sklearn.metrics import mean_squared_error

from ..base_model import RBaseModel

MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")
MIN_SECTOR_STOCKS = 3


def _load_sector_mapping() -> dict[str, str]:
    """Load symbol -> sector mapping from MASTER_UNIVERSE.md."""
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    mapping = {}
    for match in re.finditer(r"\| (\w+) \| (.+?) \|", text):
        sym, sector = match.group(1), match.group(2).strip()
        if sym not in ("Symbol", "Item"):
            mapping[sym] = sector
    return mapping


class R5Model(RBaseModel):
    MODEL_ID = "R5"

    def __init__(self, signals_db, models_db, market_db):
        super().__init__(signals_db, models_db, market_db)
        if not HAS_LIGHTGBM:
            raise ImportError("lightgbm required for R5")
        self.sector_map = _load_sector_mapping()
        self.sector_models = {}  # {sector_name: model}
        self.global_model = None
        self.scale_factor = 200

    def train(self, train_start, train_end, horizon=5, **kwargs):
        X, y_return, y_label = self.prepare_training_data(
            train_start, train_end, horizon
        )
        if X.empty:
            return {"error": "no data"}

        # Get symbol info to map sectors
        features = self.load_feature_matrix(train_start, train_end)
        labels = self.load_labels(train_start, train_end, horizon)
        merged = features.merge(
            labels, left_on=["symbol", "date"],
            right_on=["symbol", "feature_date"], how="inner",
        )

        non_feat = {"symbol", "date", "feature_date", "close_t",
                    "target_return", "target_label", "snapshot_time"}
        feat_cols = [c for c in merged.columns if c not in non_feat]

        # Train global model first (fallback)
        X_all = merged[feat_cols].astype(float).fillna(0.0)
        y_all = merged["target_return"].astype(float)

        self.global_model = lgb.LGBMRegressor(
            n_estimators=150, max_depth=5, learning_rate=0.05,
            verbose=-1, random_state=42,
        )
        self.global_model.fit(X_all, y_all)

        # Train per-sector models
        merged["sector"] = merged["symbol"].map(self.sector_map).fillna("Khac")
        sector_counts = merged["sector"].value_counts()

        total_metrics = {"global_mse": round(float(mean_squared_error(y_all, self.global_model.predict(X_all))), 6)}
        self.sector_models = {}

        for sector, count in sector_counts.items():
            unique_stocks = merged[merged["sector"] == sector]["symbol"].nunique()
            if unique_stocks < MIN_SECTOR_STOCKS:
                continue  # use global fallback

            sector_mask = merged["sector"] == sector
            X_sec = merged.loc[sector_mask, feat_cols].astype(float).fillna(0.0)
            y_sec = merged.loc[sector_mask, "target_return"].astype(float)

            if len(X_sec) < 50:
                continue

            model = lgb.LGBMRegressor(
                n_estimators=150, max_depth=5, learning_rate=0.05,
                verbose=-1, random_state=42,
            )
            model.fit(X_sec, y_sec)
            self.sector_models[sector] = model

        self.model_version = f"R5_v1_{datetime.now():%Y%m%d}"
        self._feature_names = feat_cols

        total_metrics["sector_models"] = len(self.sector_models)
        total_metrics["sectors_using_global"] = len(sector_counts) - len(self.sector_models)
        total_metrics["samples"] = len(X_all)

        self.write_training_history(
            train_date=datetime.now().strftime("%Y-%m-%d"),
            data_start=train_start, data_end=train_end,
            sample_count=len(X_all), metrics=total_metrics,
        )
        self.model = True  # flag that training is done
        return total_metrics

    def predict(self, date, symbols=None):
        if self.global_model is None:
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

        results = []
        for i in range(len(sym_dates)):
            sym = sym_dates.iloc[i]["symbol"]
            sector = self.sector_map.get(sym, "Khac")

            x_row = X_feat.iloc[i:i+1]

            # Use sector model if available, else global
            if sector in self.sector_models:
                raw = float(self.sector_models[sector].predict(x_row)[0])
            else:
                raw = float(self.global_model.predict(x_row)[0])

            score = max(-4.0, min(4.0, raw * self.scale_factor))
            confidence = min(1.0, abs(score) / 4.0)
            direction = 1 if score > 0.5 else (-1 if score < -0.5 else 0)

            results.append({
                "symbol": sym,
                "date": sym_dates.iloc[i]["date"],
                "score": round(score, 4),
                "confidence": round(confidence, 4),
                "direction": direction,
            })
        return results
