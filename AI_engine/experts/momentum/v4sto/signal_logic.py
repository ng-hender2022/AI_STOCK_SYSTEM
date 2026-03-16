"""
V4STO Signal Logic
Scoring:
    primary_score   : Slow %K value (0 to 100)
    secondary_score : sto_norm = (slow_k - 50) / 50 -> -1..+1
    signal_quality  : 0..4
    signal_code     : V4STO_*
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import STOFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class STOOutput:
    """Scoring output for V4STO."""
    symbol: str
    date: str
    data_cutoff_date: str

    primary_score: float = 50.0    # Slow %K value 0-100
    secondary_score: float = 0.0   # sto_norm -1..+1

    signal_code: str = ""
    signal_quality: int = 0
    has_sufficient_data: bool = False

    # Feature passthrough for metadata
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    stoch_k_slope: float = 0.0
    k_above_d: int = 0
    stoch_zone: int = 0
    stoch_divergence: int = 0
    stoch_cross_in_zone: int = 0
    sto_norm: float = 0.0


class STOSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: STOFeatures) -> STOOutput:
        output = STOOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        levels = self.cfg["levels"]

        k = features.stoch_k

        # --- Scores ---
        output.primary_score = k
        output.secondary_score = features.sto_norm

        # --- Copy features ---
        output.stoch_k = features.stoch_k
        output.stoch_d = features.stoch_d
        output.stoch_k_slope = features.stoch_k_slope
        output.k_above_d = features.k_above_d
        output.stoch_zone = features.stoch_zone
        output.stoch_divergence = features.stoch_divergence
        output.stoch_cross_in_zone = features.stoch_cross_in_zone
        output.sto_norm = features.sto_norm

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(features, levels)

        # --- Signal code ---
        output.signal_code = self._signal_code(features, levels)

        return output

    def _compute_quality(self, f: STOFeatures, levels: dict) -> int:
        """
        Quality 0-4 per rulebook:
            4: Divergence + %K/%D cross in OB/OS zone
            3: %K/%D cross in OB/OS zone (< 20 or > 80)
            2: %K/%D cross near OB/OS (20-30 or 70-80)
            1: OB/OS zone reached but no cross
            0: %K in neutral zone, no cross
        """
        k = f.stoch_k
        has_div = f.stoch_divergence != 0
        has_cross = f.k_crossed_above_d or f.k_crossed_below_d
        is_obos = k <= levels["oversold"] or k >= levels["overbought"]
        is_near_obos = (20 < k <= 30) or (70 <= k < 80)

        if has_div and has_cross and is_obos:
            return 4
        if has_cross and is_obos:
            return 3
        if has_cross and is_near_obos:
            return 2
        if is_obos:
            return 1
        return 0

    def _signal_code(self, f: STOFeatures, levels: dict) -> str:
        """
        Determine the most relevant signal code.
        Priority: divergence > cross in zone > extreme OB/OS > neutral.

        Lane rule: crosses in the middle zone are unreliable.
        """
        k = f.stoch_k

        # Divergence (highest priority)
        if f.stoch_divergence == 1:
            return "V4STO_BULL_DIV"
        if f.stoch_divergence == -1:
            return "V4STO_BEAR_DIV"

        # %K/%D cross in OB/OS zone
        if f.k_crossed_above_d and k <= levels["oversold"]:
            return "V4STO_BULL_CROSS"
        if f.k_crossed_below_d and k >= levels["overbought"]:
            return "V4STO_BEAR_CROSS"

        # Extreme OB/OS
        if k <= levels["extreme_oversold"]:
            return "V4STO_BULL_EXTREME_OS"
        if k >= levels["extreme_overbought"]:
            return "V4STO_BEAR_EXTREME_OB"

        # %K/%D cross near OB/OS (still somewhat meaningful)
        if f.k_crossed_above_d and k <= 30:
            return "V4STO_BULL_CROSS"
        if f.k_crossed_below_d and k >= 70:
            return "V4STO_BEAR_CROSS"

        # Regular OB/OS zone (no cross)
        if k <= levels["oversold"]:
            return "V4STO_BULL_EXTREME_OS"
        if k >= levels["overbought"]:
            return "V4STO_BEAR_EXTREME_OB"

        # Neutral / mid zone
        return "V4STO_NEUT_MID"
