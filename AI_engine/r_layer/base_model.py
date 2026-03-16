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

# Sub-features to extract from expert_signals metadata_json
# Maps expert_id -> list of (metadata_key, feature_column_name, default_value)
SUB_FEATURE_MAP = {
    "V4RSI": [
        ("rsi_slope", "v4rsi_slope", 0.0),
        ("divergence_flag", "v4rsi_divergence_flag", 0),
        ("centerline_cross", "v4rsi_center_cross_flag", 0),
    ],
    "V4MACD": [
        ("histogram_slope", "v4macd_hist_slope", 0.0),
        ("macd_cross_flag", "v4macd_cross_flag", 0),
        ("divergence_flag", "v4macd_divergence_flag", 0),
    ],
    "V4BB": [
        ("bb_bandwidth", "v4bb_width", 0.0),
        ("bb_pct_b", "v4bb_position", 0.5),
        ("bb_squeeze_active", "v4bb_squeeze_flag", 0),
        ("bb_band_walk", "v4bb_band_walk_flag", 0),
    ],
    "V4V": [
        ("vol_ratio", "v4v_volume_ratio_20", 1.0),
        ("vol_trend_5", "v4v_volume_trend", 0.0),
        ("vol_climax", "v4v_climax_volume_flag", 0),
        ("vol_drying", "v4v_drying_volume_flag", 0),
        ("vol_expansion", "v4v_expansion_flag", 0),
    ],
    "V4P": [
        ("ret_1d", "v4p_ret_1d", 0.0),
        ("ret_5d", "v4p_ret_5d", 0.0),
        ("ret_10d", "v4p_ret_10d", 0.0),
        ("ret_20d", "v4p_ret_20d", 0.0),
        ("breakout_flag", "v4p_breakout20_flag", 0),
        ("breakout60_flag", "v4p_breakout60_flag", 0),
        ("range_position", "v4p_range_position", 0.5),
        ("gap_ret", "v4p_gap_ret", 0.0),
        ("trend_persistence", "v4p_trend_persistence", 0.5),
    ],
    "V4I": [
        ("cloud_position_score", "v4i_cloud_position_score", 0.0),
        ("tk_signal_score", "v4i_tk_signal_score", 0.0),
        ("chikou_confirm_score", "v4i_chikou_confirm_score", 0.0),
        ("future_cloud_score", "v4i_future_cloud_score", 0.0),
        ("time_resonance", "v4i_time_resonance", 0.0),
    ],
    "V4MA": [
        ("alignment_score", "v4ma_alignment_score", 0.0),
        ("ema20_slope", "v4ma_slope_20", 0.0),
        ("ma50_slope", "v4ma_slope_50", 0.0),
        ("ma200_slope", "v4ma_slope_200", 0.0),
        ("golden_cross", "v4ma_golden_cross_flag", 0),
        ("death_cross", "v4ma_death_cross_flag", 0),
        ("dist_ema20", "v4ma_dist_ma20", 0.0),
        ("dist_ma50", "v4ma_dist_ma50", 0.0),
        ("dist_ma100", "v4ma_dist_ma100", 0.0),
        ("dist_ma200", "v4ma_dist_ma200", 0.0),
    ],
    "V4ADX": [
        ("adx_value", "v4adx_value", 0.0),
        ("plus_di", "v4adx_di_plus", 0.0),
        ("minus_di", "v4adx_di_minus", 0.0),
        ("di_diff", "v4adx_di_spread", 0.0),
    ],
    "V4STO": [
        ("stoch_k", "v4sto_k", 0.5),
        ("stoch_d", "v4sto_d", 0.5),
        ("stoch_cross_in_zone", "v4sto_cross_flag", 0),
        ("stoch_divergence", "v4sto_divergence_flag", 0),
    ],
    "V4OBV": [
        ("obv_slope_norm", "v4obv_slope", 0.0),
        ("obv_divergence", "v4obv_divergence_flag", 0),
        ("obv_new_high", "v4obv_breakout_flag", 0),
    ],
    "V4ATR": [
        ("atr_pct", "v4atr_pct", 0.0),
        ("atr_percentile", "v4atr_percentile", 50.0),
        ("volatility_compression", "v4atr_vol_compression", 1.0),
        ("atr_expanding", "v4atr_expanding_flag", 0),
    ],
    "V4CANDLE": [
        ("body_pct", "v4candle_body_pct", 0.0),
        ("upper_shadow_pct", "v4candle_upper_wick_pct", 0.0),
        ("lower_shadow_pct", "v4candle_lower_wick_pct", 0.0),
        ("volume_confirm", "v4candle_volume_confirm", 0),
    ],
    "V4BR": [
        ("pct_above_sma50", "v4br_pct_above_ma50", 0.5),
        ("ad_ratio", "v4br_ad_ratio", 0.5),
        ("net_new_highs", "v4br_new_high_low_ratio", 0.0),
        ("pos_divergence", "v4br_pos_divergence", 0),
        ("neg_divergence", "v4br_neg_divergence", 0),
    ],
    "V4RS": [
        ("rs_5d", "v4rs_5d", 0.0),
        ("rs_20d", "v4rs_20d", 0.0),
        ("rs_acceleration", "v4rs_acceleration", 0.0),
        ("rs_rank_20d", "v4rs_rank", 0.5),
    ],
    "V4S": [
        ("sector_return_20d", "v4s_sector_ret_20d", 0.0),
        ("sector_rank_20d", "v4s_sector_rank", 7.0),
        ("sector_vs_market_20d", "v4s_sector_vs_market", 0.0),
        ("sector_momentum", "v4s_sector_momentum", 0.0),
    ],
    "V4LIQ": [
        ("adtv_20d", "v4liq_avg_vol_20", 0.0),
        ("adtv_ratio", "v4liq_turnover_ratio", 1.0),
        ("liquidity_shock", "v4liq_liquidity_shock", 1.0),
    ],
    "V4PIVOT": [
        ("confluence_score", "v4pivot_confluence_score", 0.0),
        ("position_score", "v4pivot_position_score", 0.0),
        ("alignment_score", "v4pivot_alignment_score", 0.0),
    ],
    "V4SR": [
        ("dist_to_support", "v4sr_dist_support", 0.0),
        ("dist_to_resistance", "v4sr_dist_resistance", 0.0),
        ("strength_score", "v4sr_strength", 0.0),
        ("breakout_above_resistance", "v4sr_breakout_flag", 0),
    ],
    "V4TREND_PATTERN": [
        ("confirmed", "v4tp_breakout_confirmed", 0),
        ("target_pct", "v4tp_pattern_completion", 0.0),
        ("breakout_volume_ratio", "v4tp_breakout_vol_ratio", 0.0),
        ("pattern_failure", "v4tp_pattern_failure", 0),
    ],
}


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
        Returns DataFrame with columns: symbol, date, + expert norm scores + sub-features + meta features.
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
                   regime_score,
                   trend_alignment_score, trend_strength_max,
                   ma_alignment_pct, trend_persistence_avg,
                   momentum_divergence_count, overbought_count, oversold_count,
                   volume_pressure, liquidity_shock_avg, climax_volume_count,
                   compression_count, bull_bear_ratio, sector_momentum,
                   breakout_count
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
            SELECT symbol, date, expert_id, primary_score, secondary_score, metadata_json
            FROM expert_signals
            WHERE date >= ? AND date <= ? AND snapshot_time = 'EOD'
        """
        eparams = [start_date, end_date]
        if symbols:
            expert_sql += f" AND symbol IN ({placeholders})"
            eparams.extend(symbols)

        expert_rows = conn.execute(expert_sql, eparams).fetchall()
        conn.close()

        # Pivot expert scores into norm columns AND extract sub-features
        from AI_engine.meta_layer.meta_builder import _normalize_score
        norm_data = {}
        sub_data = {}  # {(symbol, date): {col: value}}
        for r in expert_rows:
            key = (r["symbol"], r["date"])
            if key not in norm_data:
                norm_data[key] = {}
            if key not in sub_data:
                sub_data[key] = {}
            eid = r["expert_id"]
            norm_data[key][f"{eid.lower()}_norm"] = _normalize_score(eid, r["primary_score"])

            # Extract sub-features from metadata_json
            if eid in SUB_FEATURE_MAP and r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    continue
                for meta_key, col_name, default in SUB_FEATURE_MAP[eid]:
                    val = meta.get(meta_key, default)
                    # Convert booleans to int
                    if isinstance(val, bool):
                        val = int(val)
                    elif isinstance(val, str):
                        continue  # skip string features
                    try:
                        sub_data[key][col_name] = float(val)
                    except (ValueError, TypeError):
                        sub_data[key][col_name] = float(default)

        # Build norm + sub-feature DataFrames efficiently via dict-of-lists
        all_extra = {}  # col -> [values]
        keys = list(zip(df["symbol"], df["date"]))

        # Collect all column names
        norm_cols = set()
        for norms in norm_data.values():
            norm_cols.update(norms.keys())
        sub_cols = set()
        for subs in sub_data.values():
            sub_cols.update(subs.keys())

        for col in sorted(norm_cols):
            all_extra[col] = [
                norm_data.get(k, {}).get(col, 0.0) for k in keys
            ]
        for col in sorted(sub_cols):
            all_extra[col] = [
                sub_data.get(k, {}).get(col, 0.0) for k in keys
            ]

        if all_extra:
            extra_df = pd.DataFrame(all_extra, index=df.index)
            df = pd.concat([df, extra_df], axis=1)

        # Normalize features per NORMALIZATION_RULEBOOK
        from AI_engine.meta_layer.feature_normalizer import FeatureNormalizer
        df = FeatureNormalizer().normalize(df, date_col="date", symbol_col="symbol")

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
        # (normalization already applied in load_feature_matrix)
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
