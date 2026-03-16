"""
V4STO Feature Builder
Computes Stochastic Oscillator (14, 3, 3) and all derived features.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Compute SMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result


def _fast_k(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
            period: int) -> np.ndarray:
    """
    Compute Fast %K.

    %K(period) = 100 * (Close - Lowest_Low_period) / (Highest_High_period - Lowest_Low_period)

    Returns array same length as closes, NaN-padded at start.
    """
    n = len(closes)
    result = np.full(n, np.nan, dtype=float)

    if n < period:
        return result

    for i in range(period - 1, n):
        highest = np.max(highs[i - period + 1 : i + 1])
        lowest = np.min(lows[i - period + 1 : i + 1])
        rng = highest - lowest
        if rng == 0:
            result[i] = 50.0  # no range -> midpoint
        else:
            result[i] = 100.0 * (closes[i] - lowest) / rng

    return result


def _slow_stochastic(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                     fast_k_period: int, fast_d_period: int,
                     slow_d_period: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute Slow Stochastic.

    Slow %K = Fast %D = SMA(Fast %K, fast_d_period)
    Slow %D = SMA(Slow %K, slow_d_period)

    Returns (slow_k, slow_d) arrays same length as closes, NaN-padded.
    """
    fk = _fast_k(closes, highs, lows, fast_k_period)
    slow_k = _sma(fk, fast_d_period)   # Slow %K = Fast %D
    slow_d = _sma(slow_k, slow_d_period)
    return slow_k, slow_d


@dataclass
class STOFeatures:
    """All Stochastic features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- Stochastic values at T-1 ---
    stoch_k: float = 50.0         # Slow %K (0-100)
    stoch_d: float = 50.0         # Slow %D (0-100)
    stoch_k_slope: float = 0.0    # (%K[t] - %K[t-3]) / 100
    k_above_d: int = 0            # 1 if %K > %D, -1 otherwise
    stoch_zone: int = 0           # -1(OS) / 0(neutral) / +1(OB)
    sto_norm: float = 0.0         # (slow_k - 50) / 50, range -1..+1

    # --- Cross detection ---
    k_crossed_above_d: bool = False   # %K just crossed above %D
    k_crossed_below_d: bool = False   # %K just crossed below %D
    stoch_cross_in_zone: int = 0      # 1 if cross occurred in OB/OS zone

    # --- Divergence ---
    stoch_divergence: int = 0     # +1 bullish, -1 bearish, 0 none

    # --- Arrays for signal_logic lookback (not stored in DB) ---
    k_history: list = field(default_factory=list)
    close_history: list = field(default_factory=list)

    has_sufficient_data: bool = False


class STOFeatureBuilder:
    """
    Build Stochastic features from market.db.

    Usage:
        builder = STOFeatureBuilder(db_path)
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
        rows = conn.execute(
            "SELECT date, open, high, low, close FROM prices_daily "
            "WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> STOFeatures:
        """Build Stochastic features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return STOFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            lookback_max = self.cfg["divergence"]["lookback_max"]
            fetch_count = min_hist + lookback_max + 50
            hist = self._fetch_history(conn, symbol, cutoff, lookback=fetch_count)

            feat = STOFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[STOFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(STOFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                lookback_max = self.cfg["divergence"]["lookback_max"]
                fetch_count = min_hist + lookback_max + 50
                hist = self._fetch_history(conn, sym, cutoff, lookback=fetch_count)
                feat = STOFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: STOFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1

        fast_k_period = self.cfg["fast_k_period"]
        fast_d_period = self.cfg["fast_d_period"]
        slow_d_period = self.cfg["slow_d_period"]
        slope_w = self.cfg["slope_window"]
        levels = self.cfg["levels"]

        feat.close = float(closes[last])

        # Compute Slow Stochastic arrays
        slow_k_arr, slow_d_arr = _slow_stochastic(
            closes, highs, lows, fast_k_period, fast_d_period, slow_d_period
        )

        if np.isnan(slow_k_arr[last]):
            return

        k_val = float(slow_k_arr[last])
        feat.stoch_k = k_val
        feat.sto_norm = (k_val - 50.0) / 50.0

        if not np.isnan(slow_d_arr[last]):
            feat.stoch_d = float(slow_d_arr[last])

        # %K slope (3-day)
        if last >= slope_w and not np.isnan(slow_k_arr[last - slope_w]):
            feat.stoch_k_slope = (slow_k_arr[last] - slow_k_arr[last - slope_w]) / 100.0

        # %K above/below %D
        if not np.isnan(slow_d_arr[last]):
            feat.k_above_d = 1 if k_val > feat.stoch_d else -1

        # Stochastic zone
        if k_val <= levels["oversold"]:
            feat.stoch_zone = -1
        elif k_val >= levels["overbought"]:
            feat.stoch_zone = 1
        else:
            feat.stoch_zone = 0

        # %K/%D crossover detection
        if last >= 1 and not np.isnan(slow_k_arr[last - 1]) and not np.isnan(slow_d_arr[last - 1]) and not np.isnan(slow_d_arr[last]):
            prev_k = slow_k_arr[last - 1]
            prev_d = slow_d_arr[last - 1]
            curr_k = slow_k_arr[last]
            curr_d = slow_d_arr[last]

            if prev_k <= prev_d and curr_k > curr_d:
                feat.k_crossed_above_d = True
            elif prev_k >= prev_d and curr_k < curr_d:
                feat.k_crossed_below_d = True

            # Cross in OB/OS zone
            if feat.k_crossed_above_d and curr_k <= levels["oversold"]:
                feat.stoch_cross_in_zone = 1
            elif feat.k_crossed_below_d and curr_k >= levels["overbought"]:
                feat.stoch_cross_in_zone = 1
            # Cross near OB/OS (20-30 or 70-80)
            elif feat.k_crossed_above_d and curr_k <= 30:
                feat.stoch_cross_in_zone = 1
            elif feat.k_crossed_below_d and curr_k >= 70:
                feat.stoch_cross_in_zone = 1

        # Store recent history for divergence detection
        lookback_max = self.cfg["divergence"]["lookback_max"]
        start_idx = max(0, last - lookback_max + 1)
        k_hist = []
        close_hist = []
        for i in range(start_idx, last + 1):
            if not np.isnan(slow_k_arr[i]):
                k_hist.append(float(slow_k_arr[i]))
                close_hist.append(float(closes[i]))
        feat.k_history = k_hist
        feat.close_history = close_hist

        # Divergence detection
        feat.stoch_divergence = self._detect_divergence(
            close_hist, k_hist,
            self.cfg["divergence"]["lookback_min"],
            levels["oversold"], levels["overbought"]
        )

    @staticmethod
    def _detect_divergence(
        closes: list[float], stoch_ks: list[float], min_lookback: int,
        oversold: float, overbought: float
    ) -> int:
        """
        Detect bullish/bearish divergence.

        Bullish: price makes lower low, %K makes higher low (in OS zone).
        Bearish: price makes higher high, %K makes lower high (in OB zone).

        Returns +1 (bullish), -1 (bearish), 0 (none).
        """
        n = len(closes)
        if n < min_lookback:
            return 0

        curr_close = closes[-1]
        curr_k = stoch_ks[-1]

        for i in range(n - min_lookback, max(-1, n - len(closes) - 1), -1):
            if i < 0:
                break
            left = max(0, i - 2)
            right = min(n - 2, i + 2)

            # Bullish: local low for price, price lower low + %K higher low, in OS zone
            if closes[i] <= min(closes[left:right + 1]):
                if curr_close < closes[i] and curr_k > stoch_ks[i]:
                    if curr_k <= oversold:
                        return 1

            # Bearish: local high for price, price higher high + %K lower high, in OB zone
            if closes[i] >= max(closes[left:right + 1]):
                if curr_close > closes[i] and curr_k < stoch_ks[i]:
                    if curr_k >= overbought:
                        return -1

        return 0
