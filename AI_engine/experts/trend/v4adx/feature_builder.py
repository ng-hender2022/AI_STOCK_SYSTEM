"""
V4ADX Feature Builder
Computes ADX, +DI, -DI using Wilder smoothing, and all derived features.

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
class ADXFeatures:
    """All ADX features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    # --- ADX / DI values at cutoff ---
    adx_value: float = 0.0
    plus_di: float = 0.0
    minus_di: float = 0.0
    di_diff: float = 0.0        # +DI - -DI

    # --- ADX slope ---
    adx_slope: float = 0.0     # ADX[t] - ADX[t-slope_window]
    adx_rising: bool = False   # ADX[t] > ADX[t-slope_window]

    # --- DI crossover events (just happened at cutoff) ---
    di_cross_bull: bool = False   # +DI just crossed above -DI
    di_cross_bear: bool = False   # -DI just crossed above +DI

    # --- Scores (computed in feature_builder for metadata convenience) ---
    adx_score: int = 0          # 0..4
    di_score: float = 0.0       # +DI - -DI (same as di_diff)

    has_sufficient_data: bool = False


class ADXFeatureBuilder:
    """
    Build ADX features from market.db.

    Usage:
        builder = ADXFeatureBuilder(db_path)
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

    def build(self, symbol: str, target_date: str) -> ADXFeatures:
        """Build ADX features. Uses only data with date < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? "
                "ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return ADXFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 20)

            feat = ADXFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[ADXFeatures]:
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
                    results.append(ADXFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 20)
                feat = ADXFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: ADXFeatures, hist: list[dict]) -> None:
        """Compute ADX, +DI, -DI and all derived features."""
        period = self.cfg["adx_period"]
        slope_window = self.cfg["slope_window"]

        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)

        # --- Directional Movement and True Range ---
        # Arrays start from index 1 (need previous bar)
        plus_dm = np.zeros(n, dtype=float)
        minus_dm = np.zeros(n, dtype=float)
        tr = np.zeros(n, dtype=float)

        for i in range(1, n):
            up_move = highs[i] - highs[i - 1]
            down_move = lows[i - 1] - lows[i]

            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move

            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

        # --- Wilder smoothing of +DM, -DM, TR ---
        # We smooth starting from index 1, so shift arrays
        smooth_plus_dm = _wilder_smooth(plus_dm[1:], period)
        smooth_minus_dm = _wilder_smooth(minus_dm[1:], period)
        smooth_tr = _wilder_smooth(tr[1:], period)

        # --- +DI and -DI ---
        m = len(smooth_tr)
        plus_di_arr = np.full(m, np.nan, dtype=float)
        minus_di_arr = np.full(m, np.nan, dtype=float)

        for i in range(m):
            if not np.isnan(smooth_tr[i]) and smooth_tr[i] > 0:
                plus_di_arr[i] = 100.0 * smooth_plus_dm[i] / smooth_tr[i]
                minus_di_arr[i] = 100.0 * smooth_minus_dm[i] / smooth_tr[i]

        # --- DX ---
        dx_arr = np.full(m, np.nan, dtype=float)
        for i in range(m):
            if not np.isnan(plus_di_arr[i]) and not np.isnan(minus_di_arr[i]):
                di_sum = plus_di_arr[i] + minus_di_arr[i]
                if di_sum > 0:
                    dx_arr[i] = 100.0 * abs(plus_di_arr[i] - minus_di_arr[i]) / di_sum

        # --- ADX = Wilder smooth of DX ---
        # Find first valid DX to start smoothing
        valid_dx = dx_arr[~np.isnan(dx_arr)]
        if len(valid_dx) < period:
            return

        # Build a contiguous DX array starting from first valid value
        first_valid = 0
        for i in range(m):
            if not np.isnan(dx_arr[i]):
                first_valid = i
                break

        dx_contiguous = dx_arr[first_valid:]
        adx_from_dx = _wilder_smooth(dx_contiguous, period)

        # Map back to full array indices
        adx_arr = np.full(m, np.nan, dtype=float)
        for i in range(len(adx_from_dx)):
            if not np.isnan(adx_from_dx[i]):
                adx_arr[first_valid + i] = adx_from_dx[i]

        last = m - 1
        if np.isnan(adx_arr[last]) or np.isnan(plus_di_arr[last]) or np.isnan(minus_di_arr[last]):
            return

        # --- Populate features ---
        feat.adx_value = float(adx_arr[last])
        feat.plus_di = float(plus_di_arr[last])
        feat.minus_di = float(minus_di_arr[last])
        feat.di_diff = feat.plus_di - feat.minus_di
        feat.di_score = feat.di_diff

        # --- ADX score ---
        thresholds = self.cfg["scoring"]["thresholds"]
        adx = feat.adx_value
        if adx >= thresholds["very_strong"]:
            feat.adx_score = 4
        elif adx >= thresholds["moderate"]:      # >= 25
            feat.adx_score = 3
        elif adx >= thresholds["weak"]:           # >= 20
            feat.adx_score = 2
        elif adx >= thresholds["no_trend"]:       # >= 15
            feat.adx_score = 1
        else:
            feat.adx_score = 0

        # --- ADX slope ---
        if last >= slope_window and not np.isnan(adx_arr[last - slope_window]):
            feat.adx_slope = float(adx_arr[last] - adx_arr[last - slope_window])
            feat.adx_rising = bool(adx_arr[last] > adx_arr[last - slope_window])

        # --- DI crossover detection ---
        if last >= 1 and not np.isnan(plus_di_arr[last - 1]) and not np.isnan(minus_di_arr[last - 1]):
            prev_diff = plus_di_arr[last - 1] - minus_di_arr[last - 1]
            curr_diff = plus_di_arr[last] - minus_di_arr[last]
            if prev_diff <= 0 < curr_diff:
                feat.di_cross_bull = True
            elif prev_diff >= 0 > curr_diff:
                feat.di_cross_bear = True
