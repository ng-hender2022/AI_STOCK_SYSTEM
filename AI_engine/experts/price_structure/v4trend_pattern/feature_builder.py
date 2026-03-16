"""
V4TREND_PATTERN Feature Builder
Detects classical chart patterns: flags, pennants, double tops/bottoms,
and triangles from OHLCV data.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

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
class PatternResult:
    """Result of pattern detection for a single symbol/date."""
    pattern_type: str = "none"              # flag/pennant/double_top/double_bottom/triangle_asc/triangle_desc/none
    pattern_direction: str = "neutral"      # bullish/bearish/neutral
    confirmed: bool = False
    target_pct: float = 0.0                 # projected target as % from breakout price
    breakout_volume_ratio: float = 0.0      # volume at breakout / avg20
    pattern_duration: int = 0               # bars the pattern spans
    pattern_failure: bool = False           # price re-entered pattern after breakout


@dataclass
class TPFeatures:
    """All Trend Pattern features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0
    high: float = 0.0
    low: float = 0.0

    pattern: Optional[PatternResult] = None

    has_sufficient_data: bool = False


class TPFeatureBuilder:
    """
    Build Trend Pattern features from market.db.

    Usage:
        builder = TPFeatureBuilder(db_path)
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

    def build(self, symbol: str, target_date: str) -> TPFeatures:
        """Build TP features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return TPFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 30)

            feat = TPFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[TPFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(TPFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 30)
                feat = TPFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: TPFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        highs = np.array([d["high"] for d in hist], dtype=float)
        lows = np.array([d["low"] for d in hist], dtype=float)
        volumes = np.array([d.get("volume", 0) or 0 for d in hist], dtype=float)
        n = len(closes)
        last = n - 1

        feat.close = float(closes[last])
        feat.high = float(highs[last])
        feat.low = float(lows[last])

        # Compute avg volume (20-day)
        vol_avg20 = float(np.mean(volumes[max(0, n - 20) :])) if n >= 20 else float(np.mean(volumes))

        # Detect swing points
        sw = self.cfg["swing_window"]
        swing_highs = _detect_swing_highs(highs, sw)
        swing_lows = _detect_swing_lows(lows, sw)

        # Try pattern detection in priority order (most specific first)
        # If multiple patterns detected, use highest quality (first confirmed, then forming)
        candidates = []

        # 1. Flag / Pennant
        flag = self._detect_flag_pennant(closes, highs, lows, volumes, vol_avg20, n)
        if flag is not None:
            candidates.append(flag)

        # 2. Double top / bottom
        dbl = self._detect_double(closes, highs, lows, volumes, vol_avg20, swing_highs, swing_lows, n)
        if dbl is not None:
            candidates.append(dbl)

        # 3. Triangle
        tri = self._detect_triangle(closes, highs, lows, volumes, vol_avg20, swing_highs, swing_lows, n)
        if tri is not None:
            candidates.append(tri)

        # Pick best candidate: confirmed > forming, then by duration (longer = more significant)
        if candidates:
            # Sort: confirmed first, then by duration descending
            candidates.sort(key=lambda p: (p.confirmed, p.pattern_duration), reverse=True)
            feat.pattern = candidates[0]
        else:
            feat.pattern = PatternResult()  # no pattern

    def _detect_flag_pennant(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        vol_avg20: float,
        n: int,
    ) -> Optional[PatternResult]:
        """Detect bull/bear flag or pennant pattern."""
        cfg = self.cfg
        impulse_min = cfg["flag_impulse_min_pct"]
        impulse_max_bars = cfg["flag_impulse_max_bars"]
        consol_min = cfg["flag_consol_min_bars"]
        consol_max = cfg["flag_consol_max_bars"]
        consol_range_ratio = cfg["flag_consol_range_max_ratio"]
        vol_ratio_thresh = cfg["volume_breakout_ratio"]

        # Look back from the end for a consolidation followed by an impulse
        # Search window: last 20 bars
        search_end = n - 1
        search_start = max(0, n - 25)

        best = None

        for consol_end in range(search_end, search_start + consol_min + impulse_max_bars, -1):
            for consol_len in range(consol_min, min(consol_max + 1, consol_end - impulse_max_bars + 1)):
                consol_start = consol_end - consol_len + 1
                if consol_start < impulse_max_bars:
                    continue

                # Check impulse before consolidation
                for imp_len in range(2, impulse_max_bars + 1):
                    imp_start = consol_start - imp_len
                    if imp_start < 0:
                        continue

                    imp_return = (closes[consol_start - 1] - closes[imp_start]) / (closes[imp_start] + 1e-9)

                    if abs(imp_return) < impulse_min:
                        continue

                    # Consolidation range
                    consol_high = float(np.max(highs[consol_start : consol_end + 1]))
                    consol_low = float(np.min(lows[consol_start : consol_end + 1]))
                    consol_range = consol_high - consol_low
                    impulse_range = abs(closes[consol_start - 1] - closes[imp_start])

                    if impulse_range < 1e-9:
                        continue
                    if consol_range / impulse_range > consol_range_ratio:
                        continue

                    is_bull = imp_return > 0
                    pattern_type = "flag"

                    # Check if pennant (converging highs/lows)
                    if consol_len >= 5:
                        c_highs = highs[consol_start : consol_end + 1]
                        c_lows = lows[consol_start : consol_end + 1]
                        mid = consol_len // 2
                        first_half_range = float(np.max(c_highs[:mid]) - np.min(c_lows[:mid]))
                        second_half_range = float(np.max(c_highs[mid:]) - np.min(c_lows[mid:]))
                        if second_half_range < first_half_range * 0.8:
                            pattern_type = "pennant"

                    # Check breakout confirmation
                    confirmed = False
                    failure = False
                    breakout_vol_ratio = 0.0

                    if consol_end < n - 1:
                        # There are bars after consolidation
                        if is_bull and closes[consol_end + 1] > consol_high:
                            breakout_vol_ratio = float(volumes[consol_end + 1] / (vol_avg20 + 1e-9))
                            if breakout_vol_ratio >= vol_ratio_thresh:
                                confirmed = True
                            # Check failure: price re-enters pattern within 2 bars
                            if confirmed and consol_end + 3 < n:
                                for fb in range(consol_end + 2, min(consol_end + 4, n)):
                                    if closes[fb] < consol_high:
                                        failure = True
                                        break
                        elif not is_bull and closes[consol_end + 1] < consol_low:
                            breakout_vol_ratio = float(volumes[consol_end + 1] / (vol_avg20 + 1e-9))
                            if breakout_vol_ratio >= vol_ratio_thresh:
                                confirmed = True
                            if confirmed and consol_end + 3 < n:
                                for fb in range(consol_end + 2, min(consol_end + 4, n)):
                                    if closes[fb] > consol_low:
                                        failure = True
                                        break
                    elif consol_end == n - 1:
                        # Last bar is end of consolidation — check if last bar breaks out
                        if is_bull and closes[-1] > consol_high * 0.999:
                            breakout_vol_ratio = float(volumes[-1] / (vol_avg20 + 1e-9))
                            if breakout_vol_ratio >= vol_ratio_thresh:
                                confirmed = True
                        elif not is_bull and closes[-1] < consol_low * 1.001:
                            breakout_vol_ratio = float(volumes[-1] / (vol_avg20 + 1e-9))
                            if breakout_vol_ratio >= vol_ratio_thresh:
                                confirmed = True

                    # Target: flagpole projection
                    if is_bull:
                        target_price = consol_high + impulse_range
                        breakout_ref = consol_high if consol_high > 0 else closes[-1]
                    else:
                        target_price = consol_low - impulse_range
                        breakout_ref = consol_low if consol_low > 0 else closes[-1]

                    target_pct = (target_price - breakout_ref) / (breakout_ref + 1e-9)

                    direction = "bullish" if is_bull else "bearish"
                    duration = imp_len + consol_len

                    result = PatternResult(
                        pattern_type=pattern_type,
                        pattern_direction=direction,
                        confirmed=bool(confirmed),
                        target_pct=round(float(target_pct), 6),
                        breakout_volume_ratio=round(float(breakout_vol_ratio), 4),
                        pattern_duration=int(duration),
                        pattern_failure=bool(failure),
                    )

                    if best is None or (result.confirmed and not best.confirmed) or \
                       (result.confirmed == best.confirmed and result.pattern_duration > best.pattern_duration):
                        best = result

                    # Early exit once we find a confirmed pattern
                    if best and best.confirmed:
                        return best

        return best

    def _detect_double(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        vol_avg20: float,
        swing_highs: list[int],
        swing_lows: list[int],
        n: int,
    ) -> Optional[PatternResult]:
        """Detect double top or double bottom."""
        cfg = self.cfg
        tol = cfg["double_peak_tolerance_pct"]
        min_apart = cfg["double_min_bars_apart"]
        vol_ratio_thresh = cfg["volume_breakout_ratio"]

        best = None

        # Double Top: two swing highs within tolerance
        for i in range(len(swing_highs)):
            for j in range(i + 1, len(swing_highs)):
                idx1, idx2 = swing_highs[i], swing_highs[j]
                if idx2 - idx1 < min_apart:
                    continue
                h1, h2 = float(highs[idx1]), float(highs[idx2])
                if h1 < 1e-9:
                    continue
                diff_pct = abs(h1 - h2) / h1
                if diff_pct > tol:
                    continue

                # Valley between peaks
                valley_low = float(np.min(lows[idx1:idx2 + 1]))

                # Check confirmation: close below valley support after second peak
                confirmed = False
                failure = False
                breakout_vol_ratio = 0.0

                # Look for breakdown after idx2
                for k in range(idx2 + 1, n):
                    if closes[k] < valley_low:
                        breakout_vol_ratio = float(volumes[k] / (vol_avg20 + 1e-9))
                        if breakout_vol_ratio >= vol_ratio_thresh:
                            confirmed = True
                        # Check failure
                        if confirmed and k + 2 < n:
                            if closes[min(k + 2, n - 1)] > valley_low:
                                failure = True
                        break

                peak_avg = (h1 + h2) / 2.0
                target_pct = -((peak_avg - valley_low) / (valley_low + 1e-9))
                duration = idx2 - idx1

                result = PatternResult(
                    pattern_type="double_top",
                    pattern_direction="bearish",
                    confirmed=bool(confirmed),
                    target_pct=round(float(target_pct), 6),
                    breakout_volume_ratio=round(float(breakout_vol_ratio), 4),
                    pattern_duration=int(duration),
                    pattern_failure=bool(failure),
                )

                if best is None or (result.confirmed and not best.confirmed) or \
                   (result.confirmed == best.confirmed and result.pattern_duration > best.pattern_duration):
                    best = result

        # Double Bottom: two swing lows within tolerance
        for i in range(len(swing_lows)):
            for j in range(i + 1, len(swing_lows)):
                idx1, idx2 = swing_lows[i], swing_lows[j]
                if idx2 - idx1 < min_apart:
                    continue
                l1, l2 = float(lows[idx1]), float(lows[idx2])
                if l1 < 1e-9:
                    continue
                diff_pct = abs(l1 - l2) / l1
                if diff_pct > tol:
                    continue

                # Resistance between troughs
                resistance = float(np.max(highs[idx1:idx2 + 1]))

                confirmed = False
                failure = False
                breakout_vol_ratio = 0.0

                for k in range(idx2 + 1, n):
                    if closes[k] > resistance:
                        breakout_vol_ratio = float(volumes[k] / (vol_avg20 + 1e-9))
                        if breakout_vol_ratio >= vol_ratio_thresh:
                            confirmed = True
                        if confirmed and k + 2 < n:
                            if closes[min(k + 2, n - 1)] < resistance:
                                failure = True
                        break

                trough_avg = (l1 + l2) / 2.0
                target_pct = (resistance - trough_avg) / (resistance + 1e-9)
                duration = idx2 - idx1

                result = PatternResult(
                    pattern_type="double_bottom",
                    pattern_direction="bullish",
                    confirmed=bool(confirmed),
                    target_pct=round(float(target_pct), 6),
                    breakout_volume_ratio=round(float(breakout_vol_ratio), 4),
                    pattern_duration=int(duration),
                    pattern_failure=bool(failure),
                )

                if best is None or (result.confirmed and not best.confirmed) or \
                   (result.confirmed == best.confirmed and result.pattern_duration > best.pattern_duration):
                    best = result

        return best

    def _detect_triangle(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        vol_avg20: float,
        swing_highs: list[int],
        swing_lows: list[int],
        n: int,
    ) -> Optional[PatternResult]:
        """Detect ascending, descending, or symmetrical triangle."""
        cfg = self.cfg
        min_bars = cfg["triangle_min_bars"]
        max_bars = cfg["triangle_max_bars"]
        min_touches = cfg["triangle_min_touches"]
        flat_tol = cfg["triangle_flat_tolerance_pct"]
        vol_ratio_thresh = cfg["volume_breakout_ratio"]

        if len(swing_highs) < min_touches or len(swing_lows) < min_touches:
            return None

        best = None

        # Use the most recent swing points within the valid range
        # Filter to last max_bars
        recent_sh = [i for i in swing_highs if i >= n - max_bars - 5]
        recent_sl = [i for i in swing_lows if i >= n - max_bars - 5]

        if len(recent_sh) < min_touches or len(recent_sl) < min_touches:
            return None

        # Get high values at swing highs and low values at swing lows
        sh_vals = np.array([float(highs[i]) for i in recent_sh])
        sl_vals = np.array([float(lows[i]) for i in recent_sl])

        if len(sh_vals) < 2 or len(sl_vals) < 2:
            return None

        # Check for flat upper boundary (ascending triangle)
        upper_range = (np.max(sh_vals) - np.min(sh_vals)) / (np.mean(sh_vals) + 1e-9)
        # Check for flat lower boundary (descending triangle)
        lower_range = (np.max(sl_vals) - np.min(sl_vals)) / (np.mean(sl_vals) + 1e-9)

        # Check for rising lows
        rising_lows = all(sl_vals[i] >= sl_vals[i - 1] - 1e-9 for i in range(1, len(sl_vals)))
        # Check for falling highs
        falling_highs = all(sh_vals[i] <= sh_vals[i + 1 if i + 1 < len(sh_vals) else i] + 1e-9
                            for i in range(len(sh_vals) - 1))
        # Correct: falling highs means each subsequent high is lower
        falling_highs = all(sh_vals[i] >= sh_vals[i + 1] - 1e-9 for i in range(len(sh_vals) - 1))

        # Converging
        first_span = recent_sh[0] if recent_sh else 0
        last_span = max(recent_sh[-1] if recent_sh else 0, recent_sl[-1] if recent_sl else 0)
        duration = last_span - min(recent_sh[0] if recent_sh else n, recent_sl[0] if recent_sl else n)

        if duration < min_bars or duration > max_bars + 10:
            return None

        resistance_level = float(np.mean(sh_vals))
        support_level = float(np.mean(sl_vals))

        pattern_type = None
        direction = "neutral"

        if upper_range < flat_tol * 3 and rising_lows:
            # Ascending triangle: flat resistance, rising support
            pattern_type = "triangle_asc"
            direction = "bullish"
        elif lower_range < flat_tol * 3 and falling_highs:
            # Descending triangle: flat support, falling resistance
            pattern_type = "triangle_desc"
            direction = "bearish"
        elif falling_highs and rising_lows:
            # Symmetrical triangle: converging
            # Direction from prior trend — use simple check
            if n > 20:
                prior_trend = (closes[recent_sh[0]] - closes[max(0, recent_sh[0] - 20)]) / (closes[max(0, recent_sh[0] - 20)] + 1e-9)
                if prior_trend > 0.02:
                    direction = "bullish"
                    pattern_type = "triangle_asc"  # treat as ascending bias
                elif prior_trend < -0.02:
                    direction = "bearish"
                    pattern_type = "triangle_desc"  # treat as descending bias
                else:
                    return None  # symmetrical with no prior trend — skip in v1
            else:
                return None

        if pattern_type is None:
            return None

        # Check breakout
        confirmed = False
        failure = False
        breakout_vol_ratio = 0.0
        last_close = float(closes[-1])

        if direction == "bullish" and last_close > resistance_level:
            breakout_vol_ratio = float(volumes[-1] / (vol_avg20 + 1e-9))
            if breakout_vol_ratio >= vol_ratio_thresh:
                confirmed = True
            # Check failure with second-to-last bar
            if confirmed and n >= 3 and closes[-2] < resistance_level:
                # Price just broke out on last bar — not yet failed, but single close
                pass
        elif direction == "bearish" and last_close < support_level:
            breakout_vol_ratio = float(volumes[-1] / (vol_avg20 + 1e-9))
            if breakout_vol_ratio >= vol_ratio_thresh:
                confirmed = True

        # Target: base width projection
        base_width = resistance_level - support_level
        if direction == "bullish":
            target_pct = base_width / (resistance_level + 1e-9)
        else:
            target_pct = -base_width / (support_level + 1e-9)

        result = PatternResult(
            pattern_type=pattern_type,
            pattern_direction=direction,
            confirmed=bool(confirmed),
            target_pct=round(float(target_pct), 6),
            breakout_volume_ratio=round(float(breakout_vol_ratio), 4),
            pattern_duration=int(duration),
            pattern_failure=bool(failure),
        )

        return result
