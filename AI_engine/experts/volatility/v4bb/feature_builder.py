"""
V4BB Feature Builder
Computes Bollinger Bands features: %B, bandwidth, squeeze, band walk, reversal patterns.

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


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Compute SMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result


def _rolling_std(data: np.ndarray, period: int) -> np.ndarray:
    """Compute rolling standard deviation. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.std(data[i - period + 1 : i + 1], ddof=0)
    return result


@dataclass
class BBFeatures:
    """All Bollinger Band features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- BB values at cutoff ---
    bb_middle: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_pct_b: float = 0.5
    bb_bandwidth: float = 0.0

    # --- Derived ---
    bb_squeeze_active: bool = False
    bb_bandwidth_pctile: float = 50.0
    bb_band_walk: int = 0          # +1 upper walk, -1 lower walk, 0 none
    bb_position_score: float = 0.0
    bb_squeeze_score: float = 0.0
    bb_band_walk_score: float = 0.0
    bb_reversal_score: float = 0.0

    # --- History for reversal detection ---
    recent_pct_b: list = field(default_factory=list)
    recent_closes: list = field(default_factory=list)

    has_sufficient_data: bool = False


class BBFeatureBuilder:
    """
    Build Bollinger Band features from market.db.

    Usage:
        builder = BBFeatureBuilder(db_path)
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

    def build(self, symbol: str, target_date: str) -> BBFeatures:
        """Build BB features. Uses only data with date < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return BBFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 20)

            feat = BBFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[BBFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(BBFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 20)
                feat = BBFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: BBFeatures, hist: list[dict]) -> None:
        closes = np.array([d["close"] for d in hist], dtype=float)
        n = len(closes)
        last = n - 1
        period = self.cfg["bb_period"]
        mult = self.cfg["bb_std_mult"]

        feat.close = float(closes[last])

        # Compute SMA and StdDev
        sma_arr = _sma(closes, period)
        std_arr = _rolling_std(closes, period)

        # BB values at last bar
        middle = float(sma_arr[last])
        std_val = float(std_arr[last])
        upper = middle + mult * std_val
        lower = middle - mult * std_val

        feat.bb_middle = middle
        feat.bb_upper = upper
        feat.bb_lower = lower

        # %B
        band_width_val = upper - lower
        if band_width_val > 1e-9:
            feat.bb_pct_b = (feat.close - lower) / band_width_val
        else:
            feat.bb_pct_b = 0.5

        # Bandwidth
        if middle > 1e-9:
            feat.bb_bandwidth = band_width_val / middle
        else:
            feat.bb_bandwidth = 0.0

        # Bandwidth percentile over last N bandwidths
        pctile_lookback = self.cfg["bandwidth_pctile_lookback"]
        bandwidths = []
        for i in range(max(period - 1, last - pctile_lookback), last + 1):
            if i >= period - 1 and not np.isnan(sma_arr[i]) and not np.isnan(std_arr[i]):
                m = float(sma_arr[i])
                s = float(std_arr[i])
                u = m + mult * s
                l = m - mult * s
                bw = (u - l) / m if m > 1e-9 else 0.0
                bandwidths.append(bw)

        if len(bandwidths) >= 2:
            current_bw = bandwidths[-1]
            rank = sum(1 for bw in bandwidths if bw < current_bw)
            feat.bb_bandwidth_pctile = (rank / len(bandwidths)) * 100.0
        else:
            feat.bb_bandwidth_pctile = 50.0

        # Squeeze detection
        squeeze_threshold = self.cfg["squeeze_pctile_threshold"]
        feat.bb_squeeze_active = bool(feat.bb_bandwidth_pctile < squeeze_threshold)

        # Squeeze score
        if feat.bb_squeeze_active:
            if feat.close > upper:
                feat.bb_squeeze_score = float(self.cfg["scoring"]["squeeze"]["break_above"])
            elif feat.close < lower:
                feat.bb_squeeze_score = float(self.cfg["scoring"]["squeeze"]["break_below"])
            else:
                feat.bb_squeeze_score = float(self.cfg["scoring"]["squeeze"]["no_break"])
        else:
            feat.bb_squeeze_score = 0.0

        # Band walk detection
        walk_bars = self.cfg["band_walk_bars"]
        proximity = self.cfg["band_walk_proximity"]
        feat.bb_band_walk = self._detect_band_walk(
            closes, sma_arr, std_arr, mult, last, walk_bars, proximity
        )
        if feat.bb_band_walk == 1:
            feat.bb_band_walk_score = float(self.cfg["scoring"]["band_walk"]["upper_walk"])
        elif feat.bb_band_walk == -1:
            feat.bb_band_walk_score = float(self.cfg["scoring"]["band_walk"]["lower_walk"])
        else:
            feat.bb_band_walk_score = 0.0

        # Position score
        feat.bb_position_score = self._position_score(feat.bb_pct_b)

        # Reversal detection (W-bottom / M-top)
        reversal_lookback = self.cfg["reversal_lookback"]
        # Store recent %B values for reversal detection
        recent_pct_b = []
        for i in range(max(0, last - reversal_lookback), last + 1):
            if i >= period - 1 and not np.isnan(sma_arr[i]) and not np.isnan(std_arr[i]):
                m = float(sma_arr[i])
                s = float(std_arr[i])
                u = m + mult * s
                l = m - mult * s
                bw = u - l
                if bw > 1e-9:
                    pb = (closes[i] - l) / bw
                else:
                    pb = 0.5
                recent_pct_b.append(float(pb))
        feat.recent_pct_b = recent_pct_b

        recent_closes_list = []
        for i in range(max(0, last - reversal_lookback), last + 1):
            recent_closes_list.append(float(closes[i]))
        feat.recent_closes = recent_closes_list

        feat.bb_reversal_score = self._detect_reversal(recent_pct_b, recent_closes_list)

    def _position_score(self, pct_b: float) -> float:
        """Compute position score based on %B."""
        scoring = self.cfg["scoring"]["position"]
        if pct_b > 1.0:
            return float(scoring["above_upper"])     # +2
        elif pct_b > 0.6:
            return float(scoring["upper_half"])      # +1
        elif pct_b >= 0.4:
            return float(scoring["middle"])          # 0
        elif pct_b >= 0.0:
            return float(scoring["lower_half"])      # -1
        else:
            return float(scoring["below_lower"])     # -2

    def _detect_band_walk(
        self,
        closes: np.ndarray,
        sma_arr: np.ndarray,
        std_arr: np.ndarray,
        mult: float,
        last: int,
        walk_bars: int,
        proximity: float,
    ) -> int:
        """
        Detect band walk.
        Upper walk: close > (upper - proximity * (upper-lower)) for walk_bars consecutive bars.
        Lower walk: close < (lower + proximity * (upper-lower)) for walk_bars consecutive bars.
        Returns: +1 (upper walk), -1 (lower walk), 0 (none).
        """
        if last < walk_bars:
            return 0

        # Check upper walk
        upper_count = 0
        for i in range(last, max(last - walk_bars - 1, -1), -1):
            if np.isnan(sma_arr[i]) or np.isnan(std_arr[i]):
                break
            m = float(sma_arr[i])
            s = float(std_arr[i])
            u = m + mult * s
            l = m - mult * s
            bw = u - l
            threshold = u - proximity * bw
            if closes[i] > threshold:
                upper_count += 1
            else:
                break
        if upper_count >= walk_bars:
            return 1

        # Check lower walk
        lower_count = 0
        for i in range(last, max(last - walk_bars - 1, -1), -1):
            if np.isnan(sma_arr[i]) or np.isnan(std_arr[i]):
                break
            m = float(sma_arr[i])
            s = float(std_arr[i])
            u = m + mult * s
            l = m - mult * s
            bw = u - l
            threshold = l + proximity * bw
            if closes[i] < threshold:
                lower_count += 1
            else:
                break
        if lower_count >= walk_bars:
            return -1

        return 0

    def _detect_reversal(self, recent_pct_b: list, recent_closes: list) -> float:
        """
        Detect W-bottom or M-top from recent %B and close data.
        W-bottom: find two lows in closes, second low has higher %B -> +0.5
        M-top: find two highs in closes, second high has lower %B -> -0.5
        """
        if len(recent_pct_b) < 5 or len(recent_closes) < 5:
            return 0.0

        scoring = self.cfg["scoring"]["reversal"]
        n = len(recent_closes)

        # Find local lows (simple: compare with neighbors)
        lows = []
        for i in range(1, n - 1):
            if recent_closes[i] < recent_closes[i - 1] and recent_closes[i] < recent_closes[i + 1]:
                lows.append(i)

        # W-bottom: two lows where second has higher %B
        if len(lows) >= 2:
            # Take last two lows
            i1, i2 = lows[-2], lows[-1]
            if i1 < len(recent_pct_b) and i2 < len(recent_pct_b):
                if recent_pct_b[i2] > recent_pct_b[i1] and recent_pct_b[i1] < 0.3:
                    return float(scoring["w_bottom"])  # +0.5

        # Find local highs
        highs = []
        for i in range(1, n - 1):
            if recent_closes[i] > recent_closes[i - 1] and recent_closes[i] > recent_closes[i + 1]:
                highs.append(i)

        # M-top: two highs where second has lower %B
        if len(highs) >= 2:
            i1, i2 = highs[-2], highs[-1]
            if i1 < len(recent_pct_b) and i2 < len(recent_pct_b):
                if recent_pct_b[i2] < recent_pct_b[i1] and recent_pct_b[i1] > 0.7:
                    return float(scoring["m_top"])  # -0.5

        return 0.0
