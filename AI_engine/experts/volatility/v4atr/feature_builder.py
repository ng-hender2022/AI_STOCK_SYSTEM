"""
V4ATR Feature Builder
Computes ATR(14) using Wilder smoothing, ATR_pct, percentile scoring,
and all derived volatility features.

DATA LEAKAGE RULE: Day T only uses data with date < target_date.
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _wilder_smooth(data: np.ndarray, period: int) -> np.ndarray:
    """
    Wilder smoothing: first value = simple average of first `period` values,
    subsequent = (prev * (N-1) + current) / N.
    Returns array same length as data (NaN-padded).
    """
    result = np.full(len(data), np.nan, dtype=float)
    if len(data) < period:
        return result
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (result[i - 1] * (period - 1) + data[i]) / period
    return result


@dataclass
class ATRFeatures:
    """All ATR features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    # --- ATR values at cutoff ---
    atr_value: float = 0.0
    atr_pct: float = 0.0           # ATR / Close * 100
    atr_percentile: float = 0.0    # percentile within 120-day lookback

    # --- Derived features ---
    atr_change_5d: float = 0.0     # (ATR[t] - ATR[t-5]) / ATR[t-5]
    atr_ratio: float = 0.0         # ATR / SMA(ATR, 50)
    atr_expanding: bool = False    # atr_change_5d > +0.10
    atr_contracting: bool = False  # atr_change_5d < -0.10

    # --- Score ---
    atr_score: int = 0             # 0..4
    atr_norm: float = 0.0         # atr_score / 4

    # --- Volatility regime ---
    vol_regime: str = "NORMAL"     # SQUEEZE / NORMAL / EXPANSION / CLIMAX

    # --- Price return (for direction in signal codes) ---
    price_return: float = 0.0

    # --- Close price at cutoff ---
    close: float = 0.0

    has_sufficient_data: bool = False


class ATRFeatureBuilder:
    """
    Build ATR features from market.db.

    Usage:
        builder = ATRFeatureBuilder(db_path)
        features = builder.build("FPT", "2026-03-16")
        batch = builder.build_batch(["FPT", "VNM"], "2026-03-16")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_history(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, lookback: int
    ) -> list[dict]:
        """Fetch OHLC history up to and including cutoff_date, ordered chronologically."""
        rows = conn.execute(
            "SELECT date, high, low, close FROM prices_daily "
            "WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> ATRFeatures:
        """Build ATR features. Uses only data with date < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? "
                "ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return ATRFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 50)

            feat = ATRFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[ATRFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? "
                    "ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(ATRFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 50)
                feat = ATRFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: ATRFeatures, hist: list[dict]) -> None:
        """Compute ATR(14), ATR_pct, percentile, and all derived features."""
        period = self.cfg["atr_period"]
        lookback = self.cfg["atr_pct_lookback"]
        sma_period = self.cfg["atr_sma_period"]
        change_window = self.cfg["atr_change_window"]

        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)

        # --- True Range ---
        tr = np.zeros(n, dtype=float)
        tr[0] = highs[0] - lows[0]  # first bar: just H-L
        for i in range(1, n):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

        # --- ATR via Wilder smoothing ---
        atr_arr = _wilder_smooth(tr[1:], period)
        # atr_arr is indexed from tr[1:], so atr_arr[i] corresponds to hist[i+1]

        last_atr_idx = len(atr_arr) - 1
        if np.isnan(atr_arr[last_atr_idx]):
            return

        feat.atr_value = float(atr_arr[last_atr_idx])
        feat.close = float(closes[-1])

        # --- ATR_pct ---
        if feat.close > 0:
            feat.atr_pct = feat.atr_value / feat.close * 100.0

        # --- ATR_pct array for percentile calculation ---
        # Build atr_pct series for valid ATR values
        atr_pct_series = []
        for i in range(len(atr_arr)):
            if not np.isnan(atr_arr[i]) and closes[i + 1] > 0:
                atr_pct_series.append(atr_arr[i] / closes[i + 1] * 100.0)

        if len(atr_pct_series) < 2:
            return

        # Use last `lookback` values for percentile
        window = atr_pct_series[-lookback:] if len(atr_pct_series) >= lookback else atr_pct_series
        current_atr_pct = atr_pct_series[-1]
        feat.atr_percentile = float(
            np.sum(np.array(window) <= current_atr_pct) / len(window) * 100.0
        )

        # --- ATR score from percentile ---
        bins = self.cfg["scoring"]["percentile_bins"]
        pct = feat.atr_percentile
        if pct < bins["very_low"]:
            feat.atr_score = 0
        elif pct < bins["low"]:
            feat.atr_score = 1
        elif pct < bins["normal"]:
            feat.atr_score = 2
        elif pct < bins["high"]:
            feat.atr_score = 3
        else:
            feat.atr_score = 4

        feat.atr_norm = feat.atr_score / 4.0

        # --- ATR change 5d ---
        valid_atr = [(i, atr_arr[i]) for i in range(len(atr_arr)) if not np.isnan(atr_arr[i])]
        if len(valid_atr) > change_window:
            prev_atr = valid_atr[-1 - change_window][1]
            if prev_atr > 0:
                feat.atr_change_5d = float((feat.atr_value - prev_atr) / prev_atr)

        # --- Expanding / Contracting ---
        expanding_th = self.cfg["expanding_threshold"]
        contracting_th = self.cfg["contracting_threshold"]
        feat.atr_expanding = bool(feat.atr_change_5d > expanding_th)
        feat.atr_contracting = bool(feat.atr_change_5d < contracting_th)

        # --- ATR Ratio = ATR / SMA(ATR, 50) ---
        valid_atr_values = np.array([v for _, v in valid_atr])
        if len(valid_atr_values) >= sma_period:
            sma_atr = float(np.mean(valid_atr_values[-sma_period:]))
            if sma_atr > 0:
                feat.atr_ratio = float(feat.atr_value / sma_atr)

        # --- Volatility Regime ---
        regime_cfg = self.cfg["regime"]
        if pct > regime_cfg["climax_percentile"]:
            feat.vol_regime = "CLIMAX"
        elif pct > regime_cfg["expansion_percentile"] and feat.atr_expanding:
            feat.vol_regime = "EXPANSION"
        elif pct < regime_cfg["squeeze_percentile"] and feat.atr_contracting:
            feat.vol_regime = "SQUEEZE"
        else:
            feat.vol_regime = "NORMAL"

        # --- Price return (for direction determination) ---
        if len(closes) >= 2 and closes[-2] > 0:
            feat.price_return = float((closes[-1] - closes[-2]) / closes[-2])
