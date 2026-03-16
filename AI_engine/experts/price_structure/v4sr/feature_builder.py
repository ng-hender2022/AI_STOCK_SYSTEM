"""
V4SR Feature Builder
Detects swing highs/lows, builds SR zones with ATR-based widths,
computes zone strength (touch_count * age_factor * volume_factor).

DATA LEAKAGE RULE: Day T only uses data with date < target_date.
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


# ---------------------------------------------------------------------------
# ATR (Wilder smoothing)
# ---------------------------------------------------------------------------

def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
         period: int) -> np.ndarray:
    """Compute ATR using Wilder's smoothing method.
    Returns array same length as input, NaN-padded at start."""
    n = len(highs)
    tr = np.full(n, np.nan, dtype=float)
    atr_arr = np.full(n, np.nan, dtype=float)

    # True Range for first bar has no previous close
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    if n < period:
        return atr_arr

    # Initial ATR = simple average of first `period` TRs
    atr_arr[period - 1] = np.mean(tr[:period])

    # Wilder smoothing
    for i in range(period, n):
        atr_arr[i] = (atr_arr[i - 1] * (period - 1) + tr[i]) / period

    return atr_arr


# ---------------------------------------------------------------------------
# Swing detection
# ---------------------------------------------------------------------------

def _detect_swing_highs(highs: np.ndarray, window: int) -> list[int]:
    """Detect swing high indices. Bar i is swing high if its high >
    high of `window` bars before AND `window` bars after."""
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
    """Detect swing low indices. Bar i is swing low if its low <
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


# ---------------------------------------------------------------------------
# SR Zone dataclass
# ---------------------------------------------------------------------------

@dataclass
class SRZone:
    """A single support/resistance zone."""
    price: float            # center price of the zone
    zone_upper: float
    zone_lower: float
    touch_count: int = 1
    formation_idx: int = 0  # index in history array when zone was formed
    total_volume: float = 0.0   # sum of volume at touches
    touch_indices: list = field(default_factory=list)  # indices of touches


# ---------------------------------------------------------------------------
# SR Features dataclass
# ---------------------------------------------------------------------------

@dataclass
class SRFeatures:
    """All SR features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0
    atr_value: float = 0.0

    # Nearest zones
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    nearest_support_strength: float = 0.0
    nearest_resistance_strength: float = 0.0
    dist_to_support: float = 0.0       # (close - support) / close
    dist_to_resistance: float = 0.0    # (resistance - close) / close

    # Zone details
    num_sr_zones: int = 0
    support_zone_upper: float = 0.0
    support_zone_lower: float = 0.0
    resistance_zone_upper: float = 0.0
    resistance_zone_lower: float = 0.0

    # Context
    price_bouncing: bool = False   # price moving up from support
    price_rejecting: bool = False  # price moving down from resistance
    volume_rising: bool = False    # recent volume > average

    # Breakout/Breakdown
    breakout_above_resistance: bool = False
    breakdown_below_support: bool = False

    avg_volume: float = 0.0
    has_sufficient_data: bool = False


class SRFeatureBuilder:
    """
    Build Support/Resistance features from market.db.

    Usage:
        builder = SRFeatureBuilder(db_path)
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

    def build(self, symbol: str, target_date: str) -> SRFeatures:
        """Build SR features. Uses only data with date < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? "
                "ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return SRFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            # Extra buffer for ATR warmup and swing detection
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 30)

            feat = SRFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[SRFeatures]:
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
                    results.append(SRFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 30)
                feat = SRFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: SRFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)
        volumes = np.array([d["volume"] if d["volume"] else 0 for d in hist], dtype=float)
        n = len(closes)
        last = n - 1

        feat.close = float(closes[last])

        # --- ATR(14) ---
        atr_period = self.cfg["atr_period"]
        atr_arr = _atr(highs, lows, closes, atr_period)
        current_atr = float(atr_arr[last]) if not np.isnan(atr_arr[last]) else 0.0
        feat.atr_value = current_atr

        if current_atr <= 0:
            return

        # --- Average volume ---
        vol_window = min(20, n)
        feat.avg_volume = float(np.mean(volumes[last - vol_window + 1: last + 1]))

        # --- Swing detection over lookback window ---
        lookback = self.cfg["lookback_days"]
        swing_window = self.cfg["swing_window"]
        start_idx = max(0, n - lookback)
        h_slice = highs[start_idx:]
        l_slice = lows[start_idx:]
        v_slice = volumes[start_idx:]
        c_slice = closes[start_idx:]
        slice_len = len(h_slice)

        swing_high_idx = _detect_swing_highs(h_slice, swing_window)
        swing_low_idx = _detect_swing_lows(l_slice, swing_window)

        # --- Build initial SR zones ---
        zone_mult = self.cfg["zone_multiplier"]
        zone_width = current_atr * zone_mult
        merge_thresh = current_atr * self.cfg["merge_threshold_atr"]

        zones: list[SRZone] = []

        # Add zones from swing highs
        for idx in swing_high_idx:
            price = float(h_slice[idx])
            vol_at_touch = float(v_slice[idx]) if idx < len(v_slice) else 0.0
            z = SRZone(
                price=price,
                zone_upper=price + zone_width / 2,
                zone_lower=price - zone_width / 2,
                touch_count=1,
                formation_idx=start_idx + idx,
                total_volume=vol_at_touch,
                touch_indices=[start_idx + idx],
            )
            zones.append(z)

        # Add zones from swing lows
        for idx in swing_low_idx:
            price = float(l_slice[idx])
            vol_at_touch = float(v_slice[idx]) if idx < len(v_slice) else 0.0
            z = SRZone(
                price=price,
                zone_upper=price + zone_width / 2,
                zone_lower=price - zone_width / 2,
                touch_count=1,
                formation_idx=start_idx + idx,
                total_volume=vol_at_touch,
                touch_indices=[start_idx + idx],
            )
            zones.append(z)

        # --- Count additional touches for each zone ---
        for z in zones:
            for i in range(start_idx, n):
                if i in z.touch_indices:
                    continue
                # A touch = price entered zone (high >= zone_lower AND low <= zone_upper)
                if highs[i] >= z.zone_lower and lows[i] <= z.zone_upper:
                    z.touch_count += 1
                    z.total_volume += float(volumes[i])
                    z.touch_indices.append(i)

        # --- Merge zones within merge_threshold ---
        zones.sort(key=lambda z: z.price)
        merged: list[SRZone] = []
        for z in zones:
            if merged and abs(z.price - merged[-1].price) <= merge_thresh:
                # Merge: weighted average price
                prev = merged[-1]
                total_touches = prev.touch_count + z.touch_count
                merged_price = (
                    prev.price * prev.touch_count + z.price * z.touch_count
                ) / total_touches
                prev.price = merged_price
                prev.zone_upper = max(prev.zone_upper, z.zone_upper)
                prev.zone_lower = min(prev.zone_lower, z.zone_lower)
                prev.touch_count = total_touches
                prev.total_volume += z.total_volume
                prev.formation_idx = min(prev.formation_idx, z.formation_idx)
                prev.touch_indices.extend(z.touch_indices)
            else:
                merged.append(z)
        zones = merged

        feat.num_sr_zones = len(zones)
        if not zones:
            return

        # --- Compute zone strength ---
        decay_period = self.cfg["decay_period"]
        min_age_factor = self.cfg["min_age_factor"]
        max_vol_factor = self.cfg["max_volume_factor"]
        avg_vol = feat.avg_volume if feat.avg_volume > 0 else 1.0

        zone_strengths = []
        for z in zones:
            days_since = last - z.formation_idx
            age_factor = max(min_age_factor, 1.0 - days_since / decay_period)
            avg_vol_at_touches = (z.total_volume / z.touch_count) if z.touch_count > 0 else 0.0
            volume_factor = min(max_vol_factor, avg_vol_at_touches / avg_vol) if avg_vol > 0 else 1.0
            strength = z.touch_count * age_factor * volume_factor
            zone_strengths.append(strength)

        # --- Find nearest support and resistance ---
        current_close = feat.close
        best_support_idx = -1
        best_support_dist = float("inf")
        best_resistance_idx = -1
        best_resistance_dist = float("inf")

        for i, z in enumerate(zones):
            if z.price <= current_close:
                # Potential support zone
                dist = current_close - z.price
                if dist < best_support_dist:
                    best_support_dist = dist
                    best_support_idx = i
            if z.price >= current_close:
                # Potential resistance zone
                dist = z.price - current_close
                if dist < best_resistance_dist:
                    best_resistance_dist = dist
                    best_resistance_idx = i

        # Populate support fields
        if best_support_idx >= 0:
            sz = zones[best_support_idx]
            feat.nearest_support = sz.price
            feat.nearest_support_strength = zone_strengths[best_support_idx]
            feat.dist_to_support = (current_close - sz.price) / current_close if current_close > 0 else 0.0
            feat.support_zone_upper = sz.zone_upper
            feat.support_zone_lower = sz.zone_lower

        # Populate resistance fields
        if best_resistance_idx >= 0:
            rz = zones[best_resistance_idx]
            feat.nearest_resistance = rz.price
            feat.nearest_resistance_strength = zone_strengths[best_resistance_idx]
            feat.dist_to_resistance = (rz.price - current_close) / current_close if current_close > 0 else 0.0
            feat.resistance_zone_upper = rz.zone_upper
            feat.resistance_zone_lower = rz.zone_lower

        # --- Breakout / Breakdown detection ---
        if best_resistance_idx >= 0:
            rz = zones[best_resistance_idx]
            if current_close > rz.zone_upper:
                feat.breakout_above_resistance = True

        if best_support_idx >= 0:
            sz = zones[best_support_idx]
            if current_close < sz.zone_lower:
                feat.breakdown_below_support = True

        # --- Context: bouncing / rejecting + volume ---
        # Check last 3 bars for direction
        if n >= 4:
            recent_closes = closes[last - 2: last + 1]
            price_rising = bool(recent_closes[-1] > recent_closes[0])
            price_falling = bool(recent_closes[-1] < recent_closes[0])

            recent_vol = float(np.mean(volumes[last - 2: last + 1]))
            avg_vol_20 = feat.avg_volume if feat.avg_volume > 0 else 1.0
            feat.volume_rising = bool(recent_vol > avg_vol_20)

            # Bouncing from support: price near support and rising
            if best_support_idx >= 0:
                sz = zones[best_support_idx]
                near_support = (current_close - sz.zone_lower) <= current_atr
                if near_support and price_rising:
                    feat.price_bouncing = True

            # Rejected from resistance: price near resistance and falling
            if best_resistance_idx >= 0:
                rz = zones[best_resistance_idx]
                near_resistance = (rz.zone_upper - current_close) <= current_atr
                if near_resistance and price_falling:
                    feat.price_rejecting = True
