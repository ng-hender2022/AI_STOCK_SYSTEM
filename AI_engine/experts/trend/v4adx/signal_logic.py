"""
V4ADX Signal Logic
Scoring:
    primary_score  : adx_score (0..4), trend strength only
    secondary_score: di_score = +DI - -DI, raw directional difference
    signal_quality : 0..4 based on ADX level + DI separation + ADX slope
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import ADXFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class ADXOutput:
    """Scoring output for V4ADX."""
    symbol: str
    date: str
    data_cutoff_date: str

    primary_score: int = 0      # adx_score 0..4
    secondary_score: float = 0.0  # di_score = +DI - -DI

    signal_code: str = ""
    signal_quality: int = 0
    has_sufficient_data: bool = False


class ADXSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: ADXFeatures) -> ADXOutput:
        output = ADXOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        output.primary_score = features.adx_score
        output.secondary_score = features.di_score

        # --- Signal code ---
        output.signal_code = self._signal_code(features)

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(features)

        return output

    def _signal_code(self, f: ADXFeatures) -> str:
        """Determine signal code based on ADX, DI, and crossover state."""
        cfg = self.cfg
        neutral_band = cfg["direction"]["neutral_band"]
        exhaustion_threshold = cfg["exhaustion"]["adx_threshold"]

        # DI crossover events take priority
        if f.di_cross_bull:
            return "V4ADX_BULL_DI_CROSS"
        if f.di_cross_bear:
            return "V4ADX_BEAR_DI_CROSS"

        # Exhaustion: ADX > 40 and falling
        if f.adx_value > exhaustion_threshold and not f.adx_rising:
            return "V4ADX_NEUT_EXHAUSTION"

        # Trend start: ADX rising from below 20
        if f.adx_rising and f.adx_value < 25:
            if f.di_diff > neutral_band:
                return "V4ADX_BULL_TREND_START"
            elif f.di_diff < -neutral_band:
                return "V4ADX_BEAR_TREND_START"

        # Strong trend: ADX >= 25
        if f.adx_value >= 25:
            if f.di_diff > neutral_band:
                return "V4ADX_BULL_TREND_STRONG"
            elif f.di_diff < -neutral_band:
                return "V4ADX_BEAR_TREND_STRONG"

        # Weak trend
        if f.adx_value < 20:
            return "V4ADX_NEUT_TREND_WEAK"

        # Moderate ADX (20-25), direction based
        if f.di_diff > neutral_band:
            return "V4ADX_BULL_TREND_START"
        elif f.di_diff < -neutral_band:
            return "V4ADX_BEAR_TREND_START"

        return "V4ADX_NEUT_TREND_WEAK"

    def _compute_quality(self, f: ADXFeatures) -> int:
        """
        Signal quality 0-4 based on ADX level + DI separation + ADX slope.
        Quality 4: ADX > 30, DI cross confirmed, ADX rising
        Quality 3: ADX > 25, clear DI separation
        Quality 2: ADX 20-25 or DI cross with moderate ADX
        Quality 1: ADX 15-20, weak signal
        Quality 0: ADX < 15, no trend
        """
        q_cfg = self.cfg["quality"]
        di_sep = abs(f.di_diff)
        clear_sep = q_cfg["di_separation_clear"]

        if f.adx_value >= q_cfg["adx_q4_min"] and di_sep >= clear_sep and f.adx_rising:
            return 4
        if f.adx_value >= q_cfg["adx_q3_min"] and di_sep >= clear_sep:
            return 3
        if f.adx_value >= q_cfg["adx_q2_min"]:
            return 2
        if f.adx_value >= q_cfg["adx_q1_min"]:
            return 1
        return 0
