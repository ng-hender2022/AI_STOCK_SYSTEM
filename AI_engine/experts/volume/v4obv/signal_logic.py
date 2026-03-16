"""
V4OBV Signal Logic
Scoring:
    Trend score      : -2 to +2 (OBV slope direction)
    Divergence score : -1 to +1 (OBV vs price divergence)
    Breakout score   : -1 to +1 (OBV new high/low)
    Total clamp      : -4 to +4
    obv_norm         : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .feature_builder import OBVFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class OBVOutput:
    """Scoring output for V4OBV."""
    symbol: str
    date: str
    data_cutoff_date: str

    obv_score: float = 0.0
    obv_norm: float = 0.0

    trend_score: float = 0.0
    divergence_score: float = 0.0
    breakout_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class OBVSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: OBVFeatures) -> OBVOutput:
        output = OBVOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]

        # --- Trend score (-2 to +2) ---
        threshold = scoring["trend"]["strong_threshold"]
        slope = features.obv_slope_norm
        if slope > threshold:
            output.trend_score = 2.0
        elif slope > 0:
            output.trend_score = 1.0
        elif slope < -threshold:
            output.trend_score = -2.0
        elif slope < 0:
            output.trend_score = -1.0
        else:
            output.trend_score = 0.0

        # --- Divergence score (-1 to +1) ---
        if features.obv_divergence == 1:
            output.divergence_score = float(scoring["divergence"]["bullish"])
        elif features.obv_divergence == -1:
            output.divergence_score = float(scoring["divergence"]["bearish"])
        else:
            output.divergence_score = 0.0

        # --- Breakout score (-1 to +1) ---
        # OBV breakout before price = leading signal
        if features.obv_new_high and not features.price_new_high:
            output.breakout_score = float(scoring["breakout"]["new_high"])
        elif features.obv_new_low and not features.price_new_low:
            output.breakout_score = float(scoring["breakout"]["new_low"])
        else:
            output.breakout_score = 0.0

        # --- Total ---
        raw = output.trend_score + output.divergence_score + output.breakout_score
        output.obv_score = max(-4.0, min(4.0, raw))
        output.obv_norm = output.obv_score / 4.0

        # --- Quality ---
        output.signal_quality = self._compute_quality(output)

        # --- Signal code ---
        output.signal_code = self._signal_code(output)

        return output

    def _compute_quality(self, o: OBVOutput) -> int:
        """Quality based on signal combination."""
        has_div = o.divergence_score != 0
        has_break = o.breakout_score != 0
        abs_trend = abs(o.trend_score)

        if has_div and has_break:
            return 4
        elif has_div or has_break:
            return 3
        elif abs_trend >= 2:
            return 2
        elif abs_trend >= 1:
            return 1
        return 0

    def _signal_code(self, o: OBVOutput) -> str:
        # Divergence signals take priority (most actionable per Granville)
        if o.divergence_score > 0:
            return "V4OBV_BULL_DIV"
        if o.divergence_score < 0:
            return "V4OBV_BEAR_DIV"
        # Then breakout
        if o.breakout_score > 0:
            return "V4OBV_BULL_BREAK"
        if o.breakout_score < 0:
            return "V4OBV_BEAR_BREAK"
        # Then trend
        if o.trend_score > 0:
            return "V4OBV_BULL_TREND"
        if o.trend_score < 0:
            return "V4OBV_BEAR_TREND"
        return "V4OBV_NEUT_FLAT"
