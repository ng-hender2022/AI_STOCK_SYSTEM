"""
Base Model for R Layer
All R models inherit from this. Provides:
- Data loading (feature matrix + labels from signals.db)
- TimeSeriesSplit validation
- Prediction writing to models.db
- DATA LEAKAGE enforcement
"""

import sqlite3
import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod


class RBaseModel(ABC):
    """
    Abstract base for all R Layer models.

    Subclasses implement: _build_model(), _train_model(), _predict()
    """

    MODEL_ID: str = ""  # R0, R1, R2, R3, R4, R5

    def __init__(
        self,
        signals_db: str | Path,
        models_db: str | Path,
        market_db: str | Path,
    ):
        self.signals_db = str(signals_db)
        self.models_db = str(models_db)
        self.market_db = str(market_db)
        self.model = None
        self.model_version = None

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def load_feature_matrix(
        self,
        start_date: str,
        end_date: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Load feature matrix from signals.db meta_features + expert_signals.
        Returns DataFrame with columns: symbol, date, + 34 features.
        """
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.row_factory = sqlite3.Row

        # Load meta_features
        sql = """
            SELECT symbol, date,
                   avg_score, trend_group_score, momentum_group_score,
                   volume_group_score, volatility_group_score,
                   structure_group_score, context_group_score,
                   expert_conflict_score, expert_alignment_score,
                   bullish_expert_count, bearish_expert_count,
                   regime_score
            FROM meta_features
            WHERE date >= ? AND date <= ?
        """
        params = [start_date, end_date]
        if symbols:
            placeholders = ",".join(["?"] * len(symbols))
            sql += f" AND symbol IN ({placeholders})"
            params.extend(symbols)
        sql += " ORDER BY date, symbol"

        meta_rows = conn.execute(sql, params).fetchall()

        if not meta_rows:
            conn.close()
            return pd.DataFrame()

        # Build base DataFrame from meta_features
        records = []
        for r in meta_rows:
            rec = dict(r)
            records.append(rec)

        df = pd.DataFrame(records)

        # Load expert norm scores per symbol-date
        expert_sql = """
            SELECT symbol, date, expert_id, primary_score, secondary_score
            FROM expert_signals
            WHERE date >= ? AND date <= ? AND snapshot_time = 'EOD'
        """
        eparams = [start_date, end_date]
        if symbols:
            expert_sql += f" AND symbol IN ({placeholders})"
            eparams.extend(symbols)

        expert_rows = conn.execute(expert_sql, eparams).fetchall()
        conn.close()

        # Pivot expert scores into norm columns
        from AI_engine.meta_layer.meta_builder import _normalize_score
        norm_data = {}
        for r in expert_rows:
            key = (r["symbol"], r["date"])
            if key not in norm_data:
                norm_data[key] = {}
            eid = r["expert_id"]
            norm_data[key][f"{eid.lower()}_norm"] = _normalize_score(eid, r["primary_score"])

        # Merge norm columns into df
        norm_cols = set()
        for norms in norm_data.values():
            norm_cols.update(norms.keys())

        for col in sorted(norm_cols):
            df[col] = df.apply(
                lambda row: norm_data.get((row["symbol"], row["date"]), {}).get(col, 0.0),
                axis=1,
            )

        return df

    def load_labels(
        self,
        start_date: str,
        end_date: str,
        horizon: int = 5,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Load training labels from signals.db training_labels.
        Returns DataFrame with: symbol, feature_date, close_t, t{horizon}_return, t{horizon}_label
        """
        conn = sqlite3.connect(self.signals_db, timeout=30)

        sql = f"""
            SELECT symbol, feature_date, close_t,
                   t{horizon}_return as target_return,
                   t{horizon}_label as target_label
            FROM training_labels
            WHERE feature_date >= ? AND feature_date <= ?
              AND t{horizon}_label IS NOT NULL
        """
        params = [start_date, end_date]
        if symbols:
            placeholders = ",".join(["?"] * len(symbols))
            sql += f" AND symbol IN ({placeholders})"
            params.extend(symbols)

        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df

    def prepare_training_data(
        self,
        start_date: str,
        end_date: str,
        horizon: int = 5,
        symbols: list[str] | None = None,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Prepare X, y_return, y_label for training.
        Merges feature matrix with labels. Drops rows with NaN features.

        Returns:
            X: feature DataFrame (numeric columns only)
            y_return: target return Series
            y_label: target label Series (UP/DOWN/NEUTRAL)
        """
        features = self.load_feature_matrix(start_date, end_date, symbols)
        labels = self.load_labels(start_date, end_date, horizon, symbols)

        if features.empty or labels.empty:
            return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=str)

        # Merge on symbol + date
        merged = features.merge(
            labels,
            left_on=["symbol", "date"],
            right_on=["symbol", "feature_date"],
            how="inner",
        )

        if merged.empty:
            return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=str)

        # Feature columns = everything except identity + target columns
        non_feature_cols = {
            "symbol", "date", "feature_date", "close_t",
            "target_return", "target_label", "snapshot_time",
        }
        feature_cols = [c for c in merged.columns if c not in non_feature_cols]

        X = merged[feature_cols].astype(float).fillna(0.0)
        y_return = merged["target_return"].astype(float)
        y_label = merged["target_label"]

        return X, y_return, y_label

    # ------------------------------------------------------------------
    # TimeSeriesSplit
    # ------------------------------------------------------------------

    @staticmethod
    def time_series_split(
        df: pd.DataFrame,
        date_col: str = "date",
        n_splits: int = 5,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        Chronological time series split. No random shuffling.
        Returns list of (train_indices, val_indices).
        """
        dates = sorted(df[date_col].unique())
        n = len(dates)
        min_train = n // (n_splits + 1)

        splits = []
        for i in range(n_splits):
            train_end_idx = min_train + i * (n - min_train) // n_splits
            val_start_idx = train_end_idx
            val_end_idx = min(val_start_idx + (n - min_train) // n_splits, n)

            train_dates = set(dates[:train_end_idx])
            val_dates = set(dates[val_start_idx:val_end_idx])

            train_mask = df[date_col].isin(train_dates)
            val_mask = df[date_col].isin(val_dates)

            if train_mask.sum() > 0 and val_mask.sum() > 0:
                splits.append((
                    np.where(train_mask)[0],
                    np.where(val_mask)[0],
                ))

        return splits

    # ------------------------------------------------------------------
    # Prediction Writing
    # ------------------------------------------------------------------

    def write_predictions(
        self,
        predictions: list[dict],
    ) -> int:
        """
        Write predictions to models.db r_predictions table.
        Each dict: {symbol, date, score, confidence, direction}
        """
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")

        score_col = f"{self.MODEL_ID.lower()}_score"

        for pred in predictions:
            # Check if row exists
            row = conn.execute(
                "SELECT rowid FROM r_predictions WHERE symbol=? AND date=? AND snapshot_time='EOD'",
                (pred["symbol"], pred["date"]),
            ).fetchone()

            if row:
                conn.execute(
                    f"UPDATE r_predictions SET {score_col}=? WHERE symbol=? AND date=? AND snapshot_time='EOD'",
                    (pred["score"], pred["symbol"], pred["date"]),
                )
            else:
                conn.execute(
                    f"""INSERT INTO r_predictions (symbol, date, snapshot_time, {score_col}, model_version)
                        VALUES (?, ?, 'EOD', ?, ?)""",
                    (pred["symbol"], pred["date"], pred["score"], self.model_version),
                )

        conn.commit()
        written = len(predictions)
        conn.close()
        return written

    def write_training_history(
        self,
        train_date: str,
        data_start: str,
        data_end: str,
        sample_count: int,
        metrics: dict,
        hyperparams: dict | None = None,
    ) -> None:
        """Write training run to models.db training_history."""
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.execute(
            """INSERT INTO training_history
               (model_id, train_date, train_start, train_end,
                data_start_date, data_end_date, sample_count,
                hyperparams_json, metrics_json, model_version, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED')""",
            (
                self.MODEL_ID,
                train_date,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                data_start,
                data_end,
                sample_count,
                json.dumps(hyperparams) if hyperparams else None,
                json.dumps(metrics),
                self.model_version,
            ),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Model Persistence
    # ------------------------------------------------------------------

    def save_model(self, path: str | Path) -> None:
        """Save trained model + all state to disk."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "model": self.model,
            "version": self.model_version,
            "_feature_names": getattr(self, "_feature_names", None),
            "_label_map": getattr(self, "_label_map", None),
            "_label_inv": getattr(self, "_label_inv", None),
            "feature_importances_": getattr(self, "feature_importances_", None),
            "scale_factor": getattr(self, "scale_factor", None),
            "sector_models": getattr(self, "sector_models", None),
            "global_model": getattr(self, "global_model", None),
        }
        with open(path, "wb") as f:
            pickle.dump(state, f)

    def load_model(self, path: str | Path) -> None:
        """Load model + all state from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self.model_version = data.get("version")
        if data.get("_feature_names"):
            self._feature_names = data["_feature_names"]
        if data.get("_label_map"):
            self._label_map = data["_label_map"]
        if data.get("_label_inv"):
            self._label_inv = data["_label_inv"]
        if data.get("feature_importances_"):
            self.feature_importances_ = data["feature_importances_"]
        if data.get("scale_factor") is not None:
            self.scale_factor = data["scale_factor"]
        if data.get("sector_models") is not None:
            self.sector_models = data["sector_models"]
        if data.get("global_model") is not None:
            self.global_model = data["global_model"]

    # ------------------------------------------------------------------
    # Abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    def train(
        self,
        train_start: str,
        train_end: str,
        horizon: int = 5,
        **kwargs,
    ) -> dict:
        """Train the model. Returns metrics dict."""
        pass

    @abstractmethod
    def predict(
        self,
        date: str,
        symbols: list[str] | None = None,
    ) -> list[dict]:
        """Generate predictions for a date. Returns list of prediction dicts."""
        pass
