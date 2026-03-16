"""
V4P Feature Builder
Computes swing highs/lows, trend structure, SMA20, High20/Low20,
range position, and breakout/breakdown flags.

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


def _detect_swing_highs(highs: np.ndarray, window: int) -> list[int]:
    """Detect swing high indices. A bar is a swing high if its high >
    high of `window` bars before AND `window` bars after (5-bar window with window=2)."""
    indices = []
    n = len(highs)
    for i in range(window, n - window):
        is_swing = True
        for j in range(1, window + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing = False
                break
        if is_swing:
            indices.append(i)
    return indices


def _detect_swing_lows(lows: np.ndarray, window: int) -> list[int]:
    """Detect swing low indices. A bar is a swing low if its low <
    low of `window` bars before AND `window` bars after."""
    indices = []
    n = len(lows)
    for i in range(window, n - window):
        is_swing = True
        for j in range(1, window + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing = False
                break
        if is_swing:
            indices.append(i)
    return indices


def _count_hh_hl_lh_ll(
    highs: np.ndarray,
    lows: np.ndarray,
    swing_high_idx: list[int],
    swing_low_idx: list[int],
) -> tuple[int, int, int, int]:
    """Count consecutive HH, HL, LH, LL from swing points.

    HH = swing high > previous swing high
    HL = swing low > previous swing low
    LH = swing high < previous swing high
    LL = swing low < previous swing low
    """
    hh_count = 0
    lh_count = 0
    for i in range(1, len(swing_high_idx)):
        if highs[swing_high_idx[i]] > highs[swing_high_idx[i - 1]]:
            hh_count += 1
        elif highs[swing_high_idx[i]] < highs[swing_high_idx[i - 1]]:
            lh_count += 1

    hl_count = 0
    ll_count = 0
    for i in range(1, len(swing_low_idx)):
        if lows[swing_low_idx[i]] > lows[swing_low_idx[i - 1]]:
            hl_count += 1
        elif lows[swing_low_idx[i]] < lows[swing_low_idx[i - 1]]:
            ll_count += 1

    return hh_count, hl_count, lh_count, ll_count


@dataclass
class PAFeatures:
    """All Price Action features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0
    high: float = 0.0
    low: float = 0.0

    # --- Swing counts (in last swing_lookback bars) ---
    hh_count: int = 0
    hl_count: int = 0
    lh_count: int = 0
    ll_count: int = 0

    # --- Trend structure ---
    trend_structure: str = "CONSOLIDATION"  # UPTREND / DOWNTREND / CONSOLIDATION

    # --- SMA20 ---
    sma20: float = 0.0
    sma20_slope: float = 0.0  # (sma20_now - sma20_5ago) / sma20_5ago

    # --- Support / Resistance (20-day) ---
    high20: float = 0.0
    low20: float = 0.0

    # --- Range position ---
    range_position: float = 0.5  # (close - low20) / (high20 - low20), 0-1

    # --- Breakout / Breakdown flags ---
    breakout_flag: bool = False   # close > high20
    breakdown_flag: bool = False  # close < low20

    # New expansion features
    trend_persistence: float = 0.5  # up_days_last_10 / 10
    ret_1d: float = 0.0
    ret_5d: float = 0.0
    ret_10d: float = 0.0
    ret_20d: float = 0.0
    gap_ret: float = 0.0
    breakout60_flag: bool = False

    has_sufficient_data: bool = False


class PAFeatureBuilder:
    """
    Build Price Action features from market.db.

    Usage:
        builder = PAFeatureBuilder(db_path)
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

    def build(self, symbol: str, target_date: str) -> PAFeatures:
        """Build PA features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return PAFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            # Need extra buffer for swing detection and SMA
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 20)

            feat = PAFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[PAFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(PAFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 20)
                feat = PAFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: PAFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1

        feat.close = float(closes[last])
        feat.high = float(highs[last])
        feat.low = float(lows[last])

        swing_window = self.cfg["swing_window"]
        swing_lookback = self.cfg["swing_lookback"]
        sr_period = self.cfg["sr_period"]
        sma_period = self.cfg["sma_period"]
        slope_window = self.cfg["sma_slope_window"]

        # --- Swing detection (last swing_lookback bars) ---
        start_idx = max(0, n - swing_lookback)
        h_slice = highs[start_idx:]
        l_slice = lows[start_idx:]

        swing_high_idx = _detect_swing_highs(h_slice, swing_window)
        swing_low_idx = _detect_swing_lows(l_slice, swing_window)

        hh, hl, lh, ll = _count_hh_hl_lh_ll(h_slice, l_slice, swing_high_idx, swing_low_idx)
        feat.hh_count = hh
        feat.hl_count = hl
        feat.lh_count = lh
        feat.ll_count = ll

        # --- Trend structure classification ---
        bull_pts = hh + hl
        bear_pts = lh + ll
        if bull_pts >= 2 and bull_pts > bear_pts:
            feat.trend_structure = "UPTREND"
        elif bear_pts >= 2 and bear_pts > bull_pts:
            feat.trend_structure = "DOWNTREND"
        else:
            feat.trend_structure = "CONSOLIDATION"

        # --- SMA20 ---
        sma20_arr = _sma(closes, sma_period)
        feat.sma20 = float(sma20_arr[last]) if not np.isnan(sma20_arr[last]) else 0.0

        if last >= slope_window and not np.isnan(sma20_arr[last - slope_window]):
            feat.sma20_slope = float(
                (sma20_arr[last] - sma20_arr[last - slope_window])
                / (sma20_arr[last - slope_window] + 1e-9)
            )

        # --- High20 / Low20 (20-day support/resistance) ---
        sr_start = max(0, n - sr_period)
        feat.high20 = float(np.max(highs[sr_start:]))
        feat.low20 = float(np.min(lows[sr_start:]))

        # --- Range position ---
        rng = feat.high20 - feat.low20
        if rng > 1e-9:
            feat.range_position = float((feat.close - feat.low20) / rng)
            feat.range_position = max(0.0, min(1.0, feat.range_position))
        else:
            feat.range_position = 0.5

        # --- Breakout / Breakdown flags ---
        feat.breakout_flag = bool(feat.close > feat.high20 * 0.9999)
        # For breakout: close >= high20 (at the high20 level means at resistance)
        # True breakout: close is the high20 itself on the last bar, or above
        # We use close > high20 with tiny tolerance for float comparison
        feat.breakout_flag = bool(feat.close >= feat.high20 - 1e-9)
        feat.breakdown_flag = bool(feat.close <= feat.low20 + 1e-9)

        # --- Returns ---
        if n >= 2 and closes[-2] > 0:
            feat.ret_1d = float((closes[-1] - closes[-2]) / closes[-2])
        if n >= 6 and closes[-6] > 0:
            feat.ret_5d = float((closes[-1] - closes[-6]) / closes[-6])
        if n >= 11 and closes[-11] > 0:
            feat.ret_10d = float((closes[-1] - closes[-11]) / closes[-11])
        if n >= 21 and closes[-21] > 0:
            feat.ret_20d = float((closes[-1] - closes[-21]) / closes[-21])

        # --- Gap return ---
        opens = np.array([d["open"] for d in hist], dtype=float)
        if n >= 2 and closes[-2] > 0:
            feat.gap_ret = float((opens[-1] - closes[-2]) / closes[-2])

        # --- Trend persistence ---
        lookback_tp = min(10, n - 1)
        if lookback_tp > 0:
            up_days = sum(1 for i in range(n - lookback_tp, n) if closes[i] > closes[i - 1])
            feat.trend_persistence = float(up_days / lookback_tp)

        # --- Breakout 60d ---
        if n >= 60:
            high60 = float(np.max(highs[-60:]))
            feat.breakout60_flag = bool(feat.close >= high60 - 1e-9)
