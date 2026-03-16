"""
V4MACD Feature Builder
Computes MACD line, Signal line, Histogram, and all derived features.

MACD = EMA(close, 12) - EMA(close, 26)
Signal = EMA(MACD, 9)
Histogram = MACD - Signal

DATA LEAKAGE RULE: Only uses data with date < target_date.
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


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Compute EMA. Returns array same length as data (NaN-padded).
    alpha = 2 / (period + 1). Seed with SMA of first `period` values."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    alpha = 2.0 / (period + 1)
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def _ema_from_series(data: np.ndarray, period: int) -> np.ndarray:
    """Compute EMA on a series that may contain NaNs at the start.
    Finds the first valid window of `period` non-NaN values and seeds from there."""
    result = np.full_like(data, np.nan, dtype=float)
    # Find first index where we have `period` consecutive valid values
    valid = ~np.isnan(data)
    first_valid = -1
    count = 0
    for i in range(len(data)):
        if valid[i]:
            count += 1
            if count >= period:
                first_valid = i
                break
        else:
            count = 0

    if first_valid < 0:
        return result

    start = first_valid - period + 1
    alpha = 2.0 / (period + 1)
    result[first_valid] = np.mean(data[start:first_valid + 1])
    for i in range(first_valid + 1, len(data)):
        if np.isnan(data[i]):
            continue
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


@dataclass
class MACDFeatures:
    """All MACD features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- MACD components at cutoff ---
    macd_value: float = 0.0        # MACD line
    signal_value: float = 0.0      # Signal line
    histogram_value: float = 0.0   # Histogram = MACD - Signal

    # --- Slopes (change over slope_window bars, normalized by close) ---
    macd_slope: float = 0.0        # (MACD[t] - MACD[t-3]) / close
    histogram_slope: float = 0.0   # (hist[t] - hist[t-3]) / close

    # --- Directional flags ---
    macd_above_signal: int = 0     # 1 if MACD > Signal, -1 if <
    macd_above_zero: int = 0       # 1 if MACD > 0, -1 if <

    # --- Divergence ---
    divergence_flag: int = 0       # +1 bullish, -1 bearish, 0 none

    # --- Cross events (just happened at cutoff bar) ---
    bull_cross: bool = False       # MACD crossed above Signal
    bear_cross: bool = False       # MACD crossed below Signal

    # --- Previous bar values for cross detection context ---
    prev_macd: float = 0.0
    prev_signal: float = 0.0

    # --- Full arrays for divergence detection (not stored in metadata) ---
    _macd_array: object = None
    _close_array: object = None

    has_sufficient_data: bool = False


class MACDFeatureBuilder:
    """
    Build MACD features from market.db.

    Usage:
        builder = MACDFeatureBuilder(db_path)
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
        """Fetch up to `lookback` rows with date <= cutoff_date, ordered chronologically."""
        rows = conn.execute(
            "SELECT date, close FROM prices_daily "
            "WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> MACDFeatures:
        """Build MACD features. Uses only data with date < target_date."""
        conn = self._connect()
        try:
            return self._build_single(conn, symbol, target_date)
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[MACDFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                results.append(self._build_single(conn, sym, target_date))
        finally:
            conn.close()
        return results

    def _build_single(
        self, conn: sqlite3.Connection, symbol: str, target_date: str
    ) -> MACDFeatures:
        row = conn.execute(
            "SELECT date FROM prices_daily WHERE symbol=? AND date<? "
            "ORDER BY date DESC LIMIT 1",
            (symbol, target_date),
        ).fetchone()

        if not row:
            return MACDFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

        cutoff = row["date"]
        min_hist = self.cfg["min_history_days"]
        # Fetch extra for divergence lookback
        div_max = self.cfg["divergence"]["lookback_max"]
        lookback = max(min_hist, 26 + 9 + div_max) + 50  # generous buffer
        hist = self._fetch_history(conn, symbol, cutoff, lookback=lookback)

        feat = MACDFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
        if len(hist) < min_hist:
            return feat

        self._compute(feat, hist)
        feat.has_sufficient_data = True
        return feat

    def _compute(self, feat: MACDFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1
        cfg = self.cfg
        slope_w = cfg["slope_window"]

        fast = cfg["macd_params"]["fast_period"]
        slow = cfg["macd_params"]["slow_period"]
        sig_period = cfg["macd_params"]["signal_period"]

        feat.close = float(closes[last])

        # --- Compute MACD components ---
        ema_fast = _ema(closes, fast)
        ema_slow = _ema(closes, slow)

        # MACD line = EMA_fast - EMA_slow
        macd_arr = np.full(n, np.nan, dtype=float)
        for i in range(n):
            if not np.isnan(ema_fast[i]) and not np.isnan(ema_slow[i]):
                macd_arr[i] = ema_fast[i] - ema_slow[i]

        # Signal line = EMA of MACD
        signal_arr = _ema_from_series(macd_arr, sig_period)

        # Histogram = MACD - Signal
        hist_arr = np.full(n, np.nan, dtype=float)
        for i in range(n):
            if not np.isnan(macd_arr[i]) and not np.isnan(signal_arr[i]):
                hist_arr[i] = macd_arr[i] - signal_arr[i]

        # Check we have valid values at last index
        if np.isnan(macd_arr[last]) or np.isnan(signal_arr[last]):
            return

        feat.macd_value = float(macd_arr[last])
        feat.signal_value = float(signal_arr[last])
        feat.histogram_value = float(hist_arr[last])

        # --- Slopes (normalized by close) ---
        c = feat.close
        if c == 0:
            c = 1e-9
        if last >= slope_w and not np.isnan(macd_arr[last - slope_w]):
            feat.macd_slope = float(
                (macd_arr[last] - macd_arr[last - slope_w]) / c
            )
        if last >= slope_w and not np.isnan(hist_arr[last - slope_w]):
            feat.histogram_slope = float(
                (hist_arr[last] - hist_arr[last - slope_w]) / c
            )

        # --- Directional flags ---
        feat.macd_above_signal = 1 if feat.macd_value > feat.signal_value else -1
        feat.macd_above_zero = 1 if feat.macd_value > 0 else -1

        # --- Cross detection ---
        if last >= 1 and not np.isnan(macd_arr[last - 1]) and not np.isnan(signal_arr[last - 1]):
            feat.prev_macd = float(macd_arr[last - 1])
            feat.prev_signal = float(signal_arr[last - 1])
            prev_diff = macd_arr[last - 1] - signal_arr[last - 1]
            curr_diff = macd_arr[last] - signal_arr[last]
            if prev_diff <= 0 < curr_diff:
                feat.bull_cross = True
            elif prev_diff >= 0 > curr_diff:
                feat.bear_cross = True

        # --- Divergence detection ---
        feat.divergence_flag = self._detect_divergence(closes, macd_arr, last)

        # Store arrays for potential external use
        feat._macd_array = macd_arr
        feat._close_array = closes

    def _detect_divergence(
        self, closes: np.ndarray, macd_arr: np.ndarray, last: int
    ) -> int:
        """
        Detect bullish/bearish divergence.
        Bullish: price makes lower low but MACD makes higher low.
        Bearish: price makes higher high but MACD makes lower high.
        Lookback: 10-30 bars, min 5 bars between pivots.
        """
        cfg_div = self.cfg["divergence"]
        lb_min = cfg_div["lookback_min"]
        lb_max = cfg_div["lookback_max"]
        min_gap = cfg_div["min_pivot_gap"]

        if last < lb_min:
            return 0

        start = max(0, last - lb_max)
        end = last  # inclusive

        # We need valid MACD values in the range
        valid_range = []
        for i in range(start, end + 1):
            if not np.isnan(macd_arr[i]):
                valid_range.append(i)

        if len(valid_range) < lb_min:
            return 0

        # Find local lows and highs in the lookback window
        # Simple approach: find two troughs and two peaks
        price_slice = closes[start:end + 1]
        macd_slice = macd_arr[start:end + 1]
        window_len = len(price_slice)

        if window_len < lb_min:
            return 0

        # Find local minima for bullish divergence
        lows = []
        for i in range(1, window_len - 1):
            if np.isnan(macd_slice[i]):
                continue
            if (price_slice[i] <= price_slice[i - 1] and
                    price_slice[i] <= price_slice[i + 1]):
                lows.append(i)

        # Check bullish divergence: recent price low < earlier price low,
        # but recent MACD low > earlier MACD low
        if len(lows) >= 2:
            for j in range(len(lows) - 1, 0, -1):
                recent = lows[j]
                for k in range(j - 1, -1, -1):
                    earlier = lows[k]
                    if recent - earlier < min_gap:
                        continue
                    if (price_slice[recent] < price_slice[earlier] and
                            macd_slice[recent] > macd_slice[earlier]):
                        return 1  # bullish divergence
                    break  # only check first valid pair
                break

        # Find local maxima for bearish divergence
        highs = []
        for i in range(1, window_len - 1):
            if np.isnan(macd_slice[i]):
                continue
            if (price_slice[i] >= price_slice[i - 1] and
                    price_slice[i] >= price_slice[i + 1]):
                highs.append(i)

        if len(highs) >= 2:
            for j in range(len(highs) - 1, 0, -1):
                recent = highs[j]
                for k in range(j - 1, -1, -1):
                    earlier = highs[k]
                    if recent - earlier < min_gap:
                        continue
                    if (price_slice[recent] > price_slice[earlier] and
                            macd_slice[recent] < macd_slice[earlier]):
                        return -1  # bearish divergence
                    break
                break

        return 0
