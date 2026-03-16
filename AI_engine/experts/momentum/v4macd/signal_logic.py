"""
V4MACD Signal Logic
Scoring:
    Cross score      : -2 to +2 (MACD vs signal line cross)
    Zero line score  : -1 to +1 (MACD position relative to zero)
    Histogram score  : -0.5 to +0.5 (histogram expansion/contraction)
    Divergence score : -1 to +1 (price vs MACD divergence)
    Total clamp      : -4 to +4
    macd_norm        : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import MACDFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class MACDOutput:
    """Scoring output for V4MACD."""
    symbol: str
    date: str
    data_cutoff_date: str

    macd_score: float = 0.0
    macd_norm: float = 0.0

    cross_score: float = 0.0
    zero_line_score: float = 0.0
    histogram_score: float = 0.0
    divergence_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class MACDSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: MACDFeatures) -> MACDOutput:
        output = MACDOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # --- 1. Signal line cross score (-2 to +2) ---
        output.cross_score = self._compute_cross_score(features)

        # --- 2. Zero line score (-1 to +1) ---
        output.zero_line_score = self._compute_zero_line_score(features)

        # --- 3. Histogram momentum score (-0.5 to +0.5) ---
        output.histogram_score = self._compute_histogram_score(features)

        # --- 4. Divergence score (-1 to +1) ---
        output.divergence_score = self._compute_divergence_score(features)

        # --- Total ---
        raw = (output.cross_score + output.zero_line_score +
               output.histogram_score + output.divergence_score)
        output.macd_score = max(-4.0, min(4.0, raw))
        output.macd_norm = output.macd_score / 4.0

        # --- Quality ---
        output.signal_quality = self._compute_quality(features, output)

        # --- Signal code ---
        output.signal_code = self._signal_code(features, output)

        return output

    def _compute_cross_score(self, f: MACDFeatures) -> float:
        """Signal line cross score: -2 to +2."""
        scoring = self.cfg["scoring"]["cross"]

        if f.bull_cross:
            # MACD crossed above signal
            if f.macd_value > 0 and f.signal_value > 0:
                return float(scoring["bull_cross_above_zero"])   # +2
            else:
                return float(scoring["bull_cross_below_zero"])   # +1

        if f.bear_cross:
            # MACD crossed below signal
            if f.macd_value < 0 and f.signal_value < 0:
                return float(scoring["bear_cross_below_zero"])   # -2
            else:
                return float(scoring["bear_cross_above_zero"])   # -1

        # No fresh cross
        if f.macd_above_signal == 1:
            return float(scoring["above_signal_no_cross"])       # +0.5
        elif f.macd_above_signal == -1:
            return float(scoring["below_signal_no_cross"])       # -0.5

        return float(scoring["neutral"])                         # 0

    def _compute_zero_line_score(self, f: MACDFeatures) -> float:
        """Zero line score: -1 to +1."""
        scoring = self.cfg["scoring"]["zero_line"]

        # Threshold = 0.5% of close price
        threshold = 0.005 * f.close if f.close > 0 else 0.001

        if abs(f.macd_value) < threshold:
            return float(scoring["near_zero"])  # 0

        macd_rising = f.macd_slope > 0

        if f.macd_value > 0:
            if macd_rising:
                return float(scoring["above_rising"])    # +1
            else:
                return float(scoring["above_falling"])   # +0.5
        else:
            if macd_rising:
                return float(scoring["below_rising"])    # -0.5
            else:
                return float(scoring["below_falling"])   # -1

    def _compute_histogram_score(self, f: MACDFeatures) -> float:
        """Histogram momentum score: -0.5 to +0.5."""
        scoring = self.cfg["scoring"]["histogram"]

        # Expanding positive: histogram > 0 and slope > 0
        if f.histogram_value > 0 and f.histogram_slope > 0:
            return float(scoring["positive_expanding"])   # +0.5

        # Expanding negative: histogram < 0 and slope < 0
        if f.histogram_value < 0 and f.histogram_slope < 0:
            return float(scoring["negative_expanding"])   # -0.5

        return float(scoring["contracting"])              # 0

    def _compute_divergence_score(self, f: MACDFeatures) -> float:
        """Divergence score: -1 to +1."""
        scoring = self.cfg["scoring"]["divergence"]

        if f.divergence_flag == 1:
            return float(scoring["bullish"])    # +1
        elif f.divergence_flag == -1:
            return float(scoring["bearish"])    # -1

        return float(scoring["none"])           # 0

    def _compute_quality(self, f: MACDFeatures, o: MACDOutput) -> int:
        """
        Signal quality 0-4.
        4: cross + zero line confirm + divergence
        3: cross + zero line confirm OR divergence alone
        2: cross only, clear direction
        1: trending but no cross
        0: flat near zero
        """
        has_cross = f.bull_cross or f.bear_cross

        # Zero line confirms direction of cross
        if has_cross and f.bull_cross:
            zero_confirms = o.zero_line_score > 0
        elif has_cross and f.bear_cross:
            zero_confirms = o.zero_line_score < 0
        else:
            zero_confirms = False

        has_divergence = f.divergence_flag != 0

        if has_cross and zero_confirms and has_divergence:
            return 4
        if (has_cross and zero_confirms) or has_divergence:
            return 3
        if has_cross:
            return 2

        # Trending but no cross
        threshold = 0.005 * f.close if f.close > 0 else 0.001
        if abs(f.macd_value) >= threshold:
            return 1

        return 0

    def _signal_code(self, f: MACDFeatures, o: MACDOutput) -> str:
        """Determine the primary signal code."""
        # Priority: divergence > cross > histogram > flat
        if f.divergence_flag == 1:
            return "V4MACD_BULL_DIV"
        if f.divergence_flag == -1:
            return "V4MACD_BEAR_DIV"

        if f.bull_cross:
            # Check if also crossing zero
            if f.prev_macd <= 0 < f.macd_value:
                return "V4MACD_BULL_CROSS_ZERO"
            return "V4MACD_BULL_CROSS"
        if f.bear_cross:
            if f.prev_macd >= 0 > f.macd_value:
                return "V4MACD_BEAR_CROSS_ZERO"
            return "V4MACD_BEAR_CROSS"

        if o.histogram_score > 0:
            return "V4MACD_BULL_HIST_EXPAND"
        if o.histogram_score < 0:
            return "V4MACD_BEAR_HIST_EXPAND"

        return "V4MACD_NEUT_FLAT"
