"""
V4RSI Feature Builder
Computes RSI(14) with Wilder smoothing and all derived features.

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


def _wilder_rsi(closes: np.ndarray, period: int) -> np.ndarray:
    """
    Compute RSI with Wilder smoothing.

    First avg_gain/avg_loss = simple average of first `period` changes.
    Subsequent: smoothed = (prev * (period-1) + current) / period.

    Returns array same length as closes, NaN-padded at start.
    """
    n = len(closes)
    rsi = np.full(n, np.nan, dtype=float)

    if n < period + 1:
        return rsi

    # Price changes
    deltas = np.diff(closes)  # length n-1

    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # First average: simple mean of first `period` changes
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # RSI at index `period` (0-based: we have period changes from period+1 prices)
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    # Subsequent values using Wilder smoothing
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Compute SMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result


@dataclass
class RSIFeatures:
    """All RSI features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- RSI values at T-1 ---
    rsi_value: float = 50.0       # RSI(14) raw value, 0-100
    rsi_norm: float = 0.0         # (rsi - 50) / 50, range -1..+1
    rsi_slope: float = 0.0        # (RSI[t] - RSI[t-3]) / 100
    rsi_ma10: float = 50.0        # SMA(RSI, 10)
    rsi_above_50: int = 0         # 1 if RSI > 50, -1 otherwise
    rsi_zone: int = 0             # -2 extreme OS, -1 OS, 0 neutral, +1 OB, +2 extreme OB

    # --- Divergence ---
    divergence_flag: int = 0      # +1 bullish, -1 bearish, 0 none

    # --- Failure swing ---
    failure_swing_flag: int = 0   # +1 bullish, -1 bearish, 0 none

    # --- Centerline cross ---
    centerline_cross: int = 0     # +1 crossed above 50, -1 crossed below 50, 0 none

    # --- Arrays for signal_logic lookback (not stored in DB) ---
    rsi_history: list = field(default_factory=list)
    close_history: list = field(default_factory=list)

    has_sufficient_data: bool = False


class RSIFeatureBuilder:
    """
    Build RSI features from market.db.

    Usage:
        builder = RSIFeatureBuilder(db_path)
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
            "SELECT date, close FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> RSIFeatures:
        """Build RSI features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return RSIFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            # Fetch extra for divergence lookback and RSI MA
            lookback_max = self.cfg["divergence"]["lookback_max"]
            fetch_count = min_hist + lookback_max + 50
            hist = self._fetch_history(conn, symbol, cutoff, lookback=fetch_count)

            feat = RSIFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[RSIFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(RSIFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                lookback_max = self.cfg["divergence"]["lookback_max"]
                fetch_count = min_hist + lookback_max + 50
                hist = self._fetch_history(conn, sym, cutoff, lookback=fetch_count)
                feat = RSIFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: RSIFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1
        period = self.cfg["rsi_period"]
        slope_w = self.cfg["rsi_slope_window"]
        ma_period = self.cfg["rsi_ma_period"]
        levels = self.cfg["levels"]

        feat.close = float(closes[last])

        # Compute RSI array
        rsi_arr = _wilder_rsi(closes, period)

        if np.isnan(rsi_arr[last]):
            return

        rsi_val = float(rsi_arr[last])
        feat.rsi_value = rsi_val
        feat.rsi_norm = (rsi_val - 50.0) / 50.0

        # RSI slope (3-day)
        if last >= slope_w and not np.isnan(rsi_arr[last - slope_w]):
            feat.rsi_slope = (rsi_arr[last] - rsi_arr[last - slope_w]) / 100.0

        # RSI MA(10)
        rsi_ma_arr = _sma(rsi_arr, ma_period)
        if not np.isnan(rsi_ma_arr[last]):
            feat.rsi_ma10 = float(rsi_ma_arr[last])

        # RSI above/below 50
        feat.rsi_above_50 = 1 if rsi_val > levels["centerline"] else -1

        # RSI zone
        if rsi_val <= levels["extreme_oversold"]:
            feat.rsi_zone = -2
        elif rsi_val <= levels["oversold"]:
            feat.rsi_zone = -1
        elif rsi_val >= levels["extreme_overbought"]:
            feat.rsi_zone = 2
        elif rsi_val >= levels["overbought"]:
            feat.rsi_zone = 1
        else:
            feat.rsi_zone = 0

        # Centerline cross: check if RSI just crossed 50
        if last >= 1 and not np.isnan(rsi_arr[last - 1]):
            prev_rsi = rsi_arr[last - 1]
            curr_rsi = rsi_arr[last]
            if prev_rsi <= levels["centerline"] < curr_rsi:
                feat.centerline_cross = 1
            elif prev_rsi >= levels["centerline"] > curr_rsi:
                feat.centerline_cross = -1

        # Store recent history for divergence/failure swing detection
        # Keep last lookback_max bars of valid RSI + close pairs
        lookback_max = self.cfg["divergence"]["lookback_max"]
        start_idx = max(0, last - lookback_max + 1)
        rsi_hist = []
        close_hist = []
        for i in range(start_idx, last + 1):
            if not np.isnan(rsi_arr[i]):
                rsi_hist.append(float(rsi_arr[i]))
                close_hist.append(float(closes[i]))
        feat.rsi_history = rsi_hist
        feat.close_history = close_hist

        # Divergence detection
        feat.divergence_flag = self._detect_divergence(
            close_hist, rsi_hist, self.cfg["divergence"]["lookback_min"]
        )

        # Failure swing detection
        feat.failure_swing_flag = self._detect_failure_swing(
            rsi_hist, levels["oversold"], levels["overbought"]
        )

    @staticmethod
    def _detect_divergence(
        closes: list[float], rsis: list[float], min_lookback: int
    ) -> int:
        """
        Detect bullish/bearish divergence.

        Bullish: price makes lower low, RSI makes higher low.
        Bearish: price makes higher high, RSI makes lower high.

        Returns +1 (bullish), -1 (bearish), 0 (none).
        """
        n = len(closes)
        if n < min_lookback:
            return 0

        curr_close = closes[-1]
        curr_rsi = rsis[-1]

        # Look for local lows/highs in the lookback window (skip last bar)
        # Bullish divergence: find a prior low where price was higher and RSI was lower
        bullish = False
        bearish = False

        for i in range(n - min_lookback, max(-1, n - len(closes) - 1), -1):
            if i < 0:
                break
            # Check if index i is a local minimum for price
            left = max(0, i - 2)
            right = min(n - 2, i + 2)  # exclude the last bar
            if closes[i] <= min(closes[left:right + 1]):
                # This is a local low for price
                if curr_close < closes[i] and curr_rsi > rsis[i]:
                    bullish = True
                    break

            # Check if index i is a local maximum for price
            if closes[i] >= max(closes[left:right + 1]):
                # This is a local high for price
                if curr_close > closes[i] and curr_rsi < rsis[i]:
                    bearish = True
                    break

        if bullish:
            return 1
        if bearish:
            return -1
        return 0

    @staticmethod
    def _detect_failure_swing(
        rsis: list[float], oversold: float, overbought: float
    ) -> int:
        """
        Detect Wilder failure swing pattern.

        Bullish failure swing:
            1. RSI falls below oversold (30)
            2. RSI bounces above some level X
            3. RSI pulls back but stays above oversold
            4. RSI breaks above X
            -> bullish signal

        Bearish failure swing:
            1. RSI rises above overbought (70)
            2. RSI falls below some level Y
            3. RSI rallies but stays below overbought
            4. RSI breaks below Y
            -> bearish signal

        Returns +1 (bullish), -1 (bearish), 0 (none).
        Scans the most recent portion of the RSI history.
        """
        n = len(rsis)
        if n < 5:
            return 0

        # --- Bullish failure swing (scan backward) ---
        # Look for the pattern in the last ~20 bars
        scan_len = min(n, 20)
        scan = rsis[n - scan_len:]

        # Find sequence: below_os -> bounce_high -> pullback_above_os -> break_high
        bullish = _scan_bullish_failure_swing(scan, oversold)
        bearish = _scan_bearish_failure_swing(scan, overbought)

        if bullish:
            return 1
        if bearish:
            return -1
        return 0


def _scan_bullish_failure_swing(rsis: list[float], oversold: float) -> bool:
    """
    Scan RSI array for bullish failure swing pattern:
    1. RSI drops below oversold
    2. RSI bounces to X (local max above oversold)
    3. RSI pulls back but stays above oversold
    4. RSI breaks above X (current bar or recent)
    """
    n = len(rsis)
    if n < 5:
        return False

    # Step 1: Find a point where RSI was below oversold
    for i in range(n - 4):
        if rsis[i] >= oversold:
            continue

        # Step 2: Find bounce above oversold (local max)
        bounce_x = None
        bounce_idx = None
        for j in range(i + 1, n - 2):
            if rsis[j] > oversold:
                if bounce_x is None or rsis[j] > bounce_x:
                    bounce_x = rsis[j]
                    bounce_idx = j
                if rsis[j] < rsis[j - 1] and bounce_idx is not None:
                    # Found peak
                    break

        if bounce_x is None or bounce_idx is None:
            continue

        # Step 3: Find pullback that stays above oversold
        pullback_found = False
        for k in range(bounce_idx + 1, n - 1):
            if rsis[k] < rsis[bounce_idx]:
                if rsis[k] >= oversold:
                    pullback_found = True
                else:
                    # Dropped below oversold again, pattern invalidated
                    pullback_found = False
                    break

        if not pullback_found:
            continue

        # Step 4: RSI breaks above bounce_x
        if rsis[-1] > bounce_x:
            return True

    return False


def _scan_bearish_failure_swing(rsis: list[float], overbought: float) -> bool:
    """
    Scan RSI array for bearish failure swing pattern:
    1. RSI rises above overbought
    2. RSI falls to Y (local min below overbought)
    3. RSI rallies but stays below overbought
    4. RSI breaks below Y (current bar or recent)
    """
    n = len(rsis)
    if n < 5:
        return False

    for i in range(n - 4):
        if rsis[i] <= overbought:
            continue

        # Step 2: Find drop below overbought (local min)
        drop_y = None
        drop_idx = None
        for j in range(i + 1, n - 2):
            if rsis[j] < overbought:
                if drop_y is None or rsis[j] < drop_y:
                    drop_y = rsis[j]
                    drop_idx = j
                if rsis[j] > rsis[j - 1] and drop_idx is not None:
                    break

        if drop_y is None or drop_idx is None:
            continue

        # Step 3: Find rally that stays below overbought
        rally_found = False
        for k in range(drop_idx + 1, n - 1):
            if rsis[k] > rsis[drop_idx]:
                if rsis[k] <= overbought:
                    rally_found = True
                else:
                    rally_found = False
                    break

        if not rally_found:
            continue

        # Step 4: RSI breaks below drop_y
        if rsis[-1] < drop_y:
            return True

    return False
