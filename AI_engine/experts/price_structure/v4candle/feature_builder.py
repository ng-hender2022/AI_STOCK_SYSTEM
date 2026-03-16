"""
V4CANDLE Feature Builder
Computes candlestick pattern features from OHLCV data.

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


def _detect_swing_highs(highs: np.ndarray, window: int) -> list[int]:
    """Detect swing high indices."""
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
    """Detect swing low indices."""
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


@dataclass
class CandleFeatures:
    """All candlestick features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    # Last 3 bars OHLCV (index 0=oldest, 2=most recent)
    opens: list = field(default_factory=list)
    highs: list = field(default_factory=list)
    lows: list = field(default_factory=list)
    closes: list = field(default_factory=list)
    volumes: list = field(default_factory=list)

    # Current bar body/shadow metrics
    body: float = 0.0              # close - open (signed)
    body_pct: float = 0.0          # abs(body) / range
    upper_shadow: float = 0.0     # high - max(open,close)
    lower_shadow: float = 0.0     # min(open,close) - low
    upper_shadow_pct: float = 0.0  # upper_shadow / range
    lower_shadow_pct: float = 0.0  # lower_shadow / range
    candle_range: float = 0.0     # high - low

    # Volume
    volume_current: int = 0
    volume_avg: float = 0.0
    volume_ratio: float = 0.0     # current / avg

    # Swing context
    recent_swing_high: float = 0.0
    recent_swing_low: float = 0.0
    at_swing_high: bool = False
    at_swing_low: bool = False

    has_sufficient_data: bool = False


class CandleFeatureBuilder:
    """
    Build Candlestick features from market.db.

    Usage:
        builder = CandleFeatureBuilder(db_path)
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
            "SELECT date, open, high, low, close, volume FROM prices_daily "
            "WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> CandleFeatures:
        """Build candle features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return CandleFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 10)

            feat = CandleFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[CandleFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(CandleFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 10)
                feat = CandleFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: CandleFeatures, hist: list[dict]) -> None:
        n = len(hist)
        last = n - 1

        # Extract last 3 bars
        bar_count = min(3, n)
        start = n - bar_count
        feat.opens = [hist[i]["open"] for i in range(start, n)]
        feat.highs = [hist[i]["high"] for i in range(start, n)]
        feat.lows = [hist[i]["low"] for i in range(start, n)]
        feat.closes = [hist[i]["close"] for i in range(start, n)]
        feat.volumes = [hist[i]["volume"] for i in range(start, n)]

        # Current bar metrics
        o = hist[last]["open"]
        h = hist[last]["high"]
        lo = hist[last]["low"]
        c = hist[last]["close"]
        rng = h - lo + 1e-9

        feat.body = c - o
        feat.candle_range = h - lo
        feat.body_pct = abs(feat.body) / rng
        feat.upper_shadow = h - max(o, c)
        feat.lower_shadow = min(o, c) - lo
        feat.upper_shadow_pct = feat.upper_shadow / rng
        feat.lower_shadow_pct = feat.lower_shadow / rng

        # Volume
        feat.volume_current = int(hist[last]["volume"])
        vol_period = self.cfg["vol_avg_period"]
        vol_start = max(0, n - vol_period)
        volumes = np.array([hist[i]["volume"] for i in range(vol_start, n)], dtype=float)
        feat.volume_avg = float(np.mean(volumes)) if len(volumes) > 0 else 0.0
        feat.volume_ratio = feat.volume_current / (feat.volume_avg + 1e-9)

        # Swing detection for context
        swing_window = self.cfg["swing_window"]
        swing_lookback = self.cfg["swing_lookback"]
        s_start = max(0, n - swing_lookback)
        highs_arr = np.array([hist[i]["high"] for i in range(s_start, n)], dtype=float)
        lows_arr = np.array([hist[i]["low"] for i in range(s_start, n)], dtype=float)

        sh_idx = _detect_swing_highs(highs_arr, swing_window)
        sl_idx = _detect_swing_lows(lows_arr, swing_window)

        if sh_idx:
            feat.recent_swing_high = float(highs_arr[sh_idx[-1]])
        else:
            feat.recent_swing_high = float(np.max(highs_arr))

        if sl_idx:
            feat.recent_swing_low = float(lows_arr[sl_idx[-1]])
        else:
            feat.recent_swing_low = float(np.min(lows_arr))

        # Check proximity to swing levels
        sr_prox = self.cfg["sr_proximity"]
        current_close = c
        if feat.recent_swing_high > 0:
            feat.at_swing_high = bool(
                abs(current_close - feat.recent_swing_high) / (feat.recent_swing_high + 1e-9) < sr_prox
            )
        if feat.recent_swing_low > 0:
            feat.at_swing_low = bool(
                abs(current_close - feat.recent_swing_low) / (feat.recent_swing_low + 1e-9) < sr_prox
            )
