"""
V4RSI Signal Logic
Scoring:
    primary_score   : RSI value (0 to 100)
    secondary_score : rsi_norm = (rsi - 50) / 50 -> -1..+1
    signal_quality  : 0..4
    signal_code     : V4RSI_*
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import RSIFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class RSIOutput:
    """Scoring output for V4RSI."""
    symbol: str
    date: str
    data_cutoff_date: str

    primary_score: float = 50.0    # RSI value 0-100
    secondary_score: float = 0.0   # rsi_norm -1..+1

    signal_code: str = ""
    signal_quality: int = 0
    has_sufficient_data: bool = False

    # Feature passthrough for metadata
    rsi_value: float = 50.0
    rsi_norm: float = 0.0
    rsi_slope: float = 0.0
    rsi_ma10: float = 50.0
    rsi_above_50: int = 0
    rsi_zone: int = 0
    divergence_flag: int = 0
    failure_swing_flag: int = 0


class RSISignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: RSIFeatures) -> RSIOutput:
        output = RSIOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        levels = self.cfg["levels"]

        rsi = features.rsi_value

        # --- Scores ---
        output.primary_score = rsi
        output.secondary_score = features.rsi_norm

        # --- Copy features ---
        output.rsi_value = features.rsi_value
        output.rsi_norm = features.rsi_norm
        output.rsi_slope = features.rsi_slope
        output.rsi_ma10 = features.rsi_ma10
        output.rsi_above_50 = features.rsi_above_50
        output.rsi_zone = features.rsi_zone
        output.divergence_flag = features.divergence_flag
        output.failure_swing_flag = features.failure_swing_flag

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(features, levels)

        # --- Signal code ---
        output.signal_code = self._signal_code(features, levels)

        return output

    def _compute_quality(self, f: RSIFeatures, levels: dict) -> int:
        """
        Quality 0-4:
            4: divergence + extreme OB/OS (or failure swing + extreme)
            3: divergence at OB/OS level
            2: extreme OB/OS (< 20 or > 80)
            1: regular OB/OS (< 30 or > 70)
            0: neutral zone, no divergence
        """
        rsi = f.rsi_value
        has_div = f.divergence_flag != 0
        has_fs = f.failure_swing_flag != 0
        is_extreme = rsi <= levels["extreme_oversold"] or rsi >= levels["extreme_overbought"]
        is_obos = rsi <= levels["oversold"] or rsi >= levels["overbought"]

        if (has_div or has_fs) and is_extreme:
            return 4
        if has_div and is_obos:
            return 3
        if is_extreme:
            return 2
        if is_obos:
            return 1
        return 0

    def _signal_code(self, f: RSIFeatures, levels: dict) -> str:
        """
        Determine the most relevant signal code.
        Priority: failure swing > divergence > extreme OB/OS > centerline > regular OB/OS > neutral.
        """
        rsi = f.rsi_value

        # Failure swings (highest priority after divergence+extreme)
        if f.failure_swing_flag == 1:
            return "V4RSI_BULL_FAILURE_SWING"
        if f.failure_swing_flag == -1:
            return "V4RSI_BEAR_FAILURE_SWING"

        # Divergence
        if f.divergence_flag == 1:
            return "V4RSI_BULL_DIV"
        if f.divergence_flag == -1:
            return "V4RSI_BEAR_DIV"

        # Extreme OB/OS
        if rsi <= levels["extreme_oversold"]:
            return "V4RSI_BULL_EXTREME_OS"
        if rsi >= levels["extreme_overbought"]:
            return "V4RSI_BEAR_EXTREME_OB"

        # Centerline cross
        if f.centerline_cross == 1:
            return "V4RSI_BULL_CENTER_CROSS"
        if f.centerline_cross == -1:
            return "V4RSI_BEAR_CENTER_CROSS"

        # Regular OB/OS (reversal signals)
        if rsi <= levels["oversold"]:
            return "V4RSI_BULL_REVERSAL"
        if rsi >= levels["overbought"]:
            return "V4RSI_BEAR_REVERSAL"

        # Neutral
        return "V4RSI_NEUT_NEUTRAL"
