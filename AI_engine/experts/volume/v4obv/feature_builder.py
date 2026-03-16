"""
V4OBV Feature Builder
Computes On Balance Volume and all derived features.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
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


def _compute_obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """Compute OBV series. OBV[0] = 0, then cumulative."""
    n = len(closes)
    obv = np.zeros(n, dtype=float)
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    return obv


@dataclass
class OBVFeatures:
    """All OBV features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- OBV values ---
    obv_current: float = 0.0

    # --- OBV slope (linear regression over 20 days, normalized) ---
    obv_slope_norm: float = 0.0

    # --- Divergence ---
    obv_divergence: int = 0       # +1 bullish, -1 bearish, 0 none

    # --- Breakout ---
    obv_new_high: int = 0         # 1 if OBV at 52-day high
    obv_new_low: int = 0          # 1 if OBV at 52-day low
    price_new_high: int = 0       # 1 if price at 52-day high
    price_new_low: int = 0        # 1 if price at 52-day low

    # --- Confirmation ---
    obv_confirms_price: int = 0   # +1 confirms, -1 diverges, 0 neutral

    has_sufficient_data: bool = False


class OBVFeatureBuilder:
    """
    Build OBV features from market.db.

    Usage:
        builder = OBVFeatureBuilder(db_path)
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
            "SELECT date, close, volume FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build(self, symbol: str, target_date: str) -> OBVFeatures:
        """Build OBV features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return OBVFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            # Fetch extra for slope/breakout calculations
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 20)

            feat = OBVFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[OBVFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(OBVFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 20)
                feat = OBVFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: OBVFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        volumes = np.array([d["volume"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1

        feat.close = float(closes[last])

        # Compute OBV series
        obv = _compute_obv(closes, volumes)
        feat.obv_current = float(obv[last])

        # --- OBV Slope (linear regression over slope_window days) ---
        slope_w = self.cfg["obv_slope_window"]
        if n >= slope_w:
            obv_window = obv[last - slope_w + 1 : last + 1]
            x = np.arange(slope_w, dtype=float)
            slope = np.polyfit(x, obv_window, 1)[0]
            # Normalize by mean absolute daily volume
            avg_vol = np.mean(np.abs(volumes[last - slope_w + 1 : last + 1]))
            if avg_vol > 0:
                feat.obv_slope_norm = float(slope / avg_vol)
            else:
                feat.obv_slope_norm = 0.0

        # --- Divergence detection ---
        div_lookback = self.cfg["divergence_lookback"]
        if n >= div_lookback + 1:
            self._detect_divergence(feat, closes, obv, div_lookback)

        # --- Breakout detection ---
        breakout_w = self.cfg["breakout_window"]
        if n >= breakout_w:
            obv_lookback = obv[last - breakout_w + 1 : last + 1]
            price_lookback = closes[last - breakout_w + 1 : last + 1]

            feat.obv_new_high = int(bool(obv[last] >= np.max(obv_lookback)))
            feat.obv_new_low = int(bool(obv[last] <= np.min(obv_lookback)))
            feat.price_new_high = int(bool(closes[last] >= np.max(price_lookback)))
            feat.price_new_low = int(bool(closes[last] <= np.min(price_lookback)))

        # --- OBV confirms price ---
        if n >= slope_w:
            price_change = closes[last] - closes[last - slope_w + 1]
            obv_change = obv[last] - obv[last - slope_w + 1]
            if price_change > 0 and obv_change > 0:
                feat.obv_confirms_price = 1
            elif price_change < 0 and obv_change < 0:
                feat.obv_confirms_price = 1
            elif (price_change > 0 and obv_change < 0) or (price_change < 0 and obv_change > 0):
                feat.obv_confirms_price = -1
            else:
                feat.obv_confirms_price = 0

    def _detect_divergence(
        self, feat: OBVFeatures, closes: np.ndarray, obv: np.ndarray, lookback: int
    ) -> None:
        """Detect bullish/bearish divergence over lookback window."""
        n = len(closes)
        last = n - 1
        start = last - lookback

        # Find local lows and highs in the lookback range
        recent_closes = closes[start : last + 1]
        recent_obv = obv[start : last + 1]

        # Current values
        curr_close = closes[last]
        curr_obv = obv[last]

        # Previous low/high (minimum/maximum in the first half of lookback)
        half = lookback // 2
        first_half_closes = closes[start : start + half]
        first_half_obv = obv[start : start + half]

        if len(first_half_closes) == 0:
            return

        prev_low_close = np.min(first_half_closes)
        prev_low_obv = obv[start + np.argmin(first_half_closes)]
        prev_high_close = np.max(first_half_closes)
        prev_high_obv = obv[start + np.argmax(first_half_closes)]

        # Bullish divergence: price lower low, OBV higher low
        if curr_close < prev_low_close and curr_obv > prev_low_obv:
            feat.obv_divergence = 1
        # Bearish divergence: price higher high, OBV lower high
        elif curr_close > prev_high_close and curr_obv < prev_high_obv:
            feat.obv_divergence = -1
        else:
            feat.obv_divergence = 0
