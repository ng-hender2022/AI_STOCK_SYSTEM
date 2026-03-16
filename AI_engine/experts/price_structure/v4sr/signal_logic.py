"""
V4SR Signal Logic
Scoring (3 components, clamped -4..+4):
    Position score  : -2 to +2
    Strength score  : -1 to +1
    Context score   : -1 to +1
    sr_norm         : sr_score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import SRFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class SROutput:
    """Scoring output for V4SR."""
    symbol: str
    date: str
    data_cutoff_date: str

    sr_score: float = 0.0
    sr_norm: float = 0.0

    position_score: float = 0.0
    strength_score: float = 0.0
    context_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class SRSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: SRFeatures) -> SROutput:
        output = SROutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        atr = features.atr_value
        close = features.close

        if atr <= 0 or close <= 0:
            return output

        # --- 1. Position score (-2..+2) ---
        position_score = 0.0

        # Check breakout/breakdown first (they take priority)
        if features.breakout_above_resistance:
            position_score = 2.0
        elif features.breakdown_below_support:
            position_score = -2.0
        else:
            # Check support proximity
            at_support = False
            near_support = False
            if features.nearest_support > 0:
                within_support_zone = (
                    close >= features.support_zone_lower
                    and close <= features.support_zone_upper
                )
                dist_support_abs = abs(close - features.nearest_support)
                if within_support_zone and features.nearest_support_strength >= 3:
                    at_support = True
                    position_score = 2.0
                elif dist_support_abs <= atr and features.nearest_support_strength >= 2:
                    near_support = True
                    position_score = 1.0

            # Check resistance proximity
            at_resistance = False
            near_resistance = False
            if features.nearest_resistance > 0:
                within_resistance_zone = (
                    close >= features.resistance_zone_lower
                    and close <= features.resistance_zone_upper
                )
                dist_resistance_abs = abs(close - features.nearest_resistance)
                if within_resistance_zone and features.nearest_resistance_strength >= 3:
                    at_resistance = True
                    position_score = -2.0
                elif dist_resistance_abs <= atr and features.nearest_resistance_strength >= 2:
                    near_resistance = True
                    position_score = -1.0

            # If both at support AND resistance, use stronger zone
            if at_support and at_resistance:
                if features.nearest_support_strength >= features.nearest_resistance_strength:
                    position_score = 2.0
                else:
                    position_score = -2.0
            elif near_support and near_resistance:
                if features.nearest_support_strength >= features.nearest_resistance_strength:
                    position_score = 1.0
                else:
                    position_score = -1.0

        output.position_score = position_score

        # --- 2. Strength score (-1..+1) ---
        strength_divisor = self.cfg["strength_divisor"]
        strength_score = 0.0

        if position_score > 0:
            # Bullish side — use support zone strength
            raw = features.nearest_support_strength / strength_divisor
            strength_score = min(1.0, raw)
        elif position_score < 0:
            # Bearish side — use resistance zone strength
            raw = features.nearest_resistance_strength / strength_divisor
            strength_score = -min(1.0, raw)

        output.strength_score = strength_score

        # --- 3. Context score (-1..+1) ---
        context_score = 0.0

        if features.price_bouncing and features.volume_rising:
            context_score = 1.0
        elif features.price_rejecting and features.volume_rising:
            context_score = -1.0

        output.context_score = context_score

        # --- Total score (clamped -4..+4) ---
        raw_score = position_score + strength_score + context_score
        output.sr_score = max(-4.0, min(4.0, raw_score))
        output.sr_norm = output.sr_score / 4.0

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(output, features)

        # --- Signal code ---
        output.signal_code = self._signal_code(output, features)

        return output

    def _compute_quality(self, o: SROutput, f: SRFeatures) -> int:
        """
        Quality 0-4:
            4 = strong zone (3+ touches) + volume + breakout/bounce
            3 = strong zone + clear reaction
            2 = moderate zone (2 touches) or near level
            1 = weak zone (1 touch) or far from levels
            0 = no identifiable SR nearby
        """
        # Determine relevant zone strength
        if o.position_score > 0:
            zone_str = f.nearest_support_strength
        elif o.position_score < 0:
            zone_str = f.nearest_resistance_strength
        else:
            zone_str = max(f.nearest_support_strength, f.nearest_resistance_strength)

        has_strong_zone = zone_str >= 3.0
        has_moderate_zone = zone_str >= 2.0
        has_volume = f.volume_rising
        has_reaction = f.price_bouncing or f.price_rejecting
        has_breakout = f.breakout_above_resistance or f.breakdown_below_support

        if has_strong_zone and has_volume and (has_breakout or has_reaction):
            return 4
        if has_strong_zone and (has_reaction or has_breakout):
            return 3
        if has_moderate_zone or abs(o.position_score) >= 1:
            return 2
        if zone_str >= 1.0:
            return 1
        return 0

    def _signal_code(self, o: SROutput, f: SRFeatures) -> str:
        """Determine signal code based on output."""
        # Breakout / Breakdown take priority
        if f.breakout_above_resistance:
            return "V4SR_BULL_BREAK_RESISTANCE"
        if f.breakdown_below_support:
            return "V4SR_BEAR_BREAK_SUPPORT"

        # Bounce / Rejection with volume
        if f.price_bouncing and f.volume_rising:
            return "V4SR_BULL_BOUNCE"
        if f.price_rejecting and f.volume_rising:
            return "V4SR_BEAR_REJECT"

        # At support / resistance
        if o.position_score >= 2:
            return "V4SR_BULL_AT_SUPPORT"
        if o.position_score <= -2:
            return "V4SR_BEAR_AT_RESISTANCE"

        # Near levels but not definitive
        if o.position_score >= 1:
            return "V4SR_BULL_AT_SUPPORT"
        if o.position_score <= -1:
            return "V4SR_BEAR_AT_RESISTANCE"

        # Between levels
        return "V4SR_NEUT_BETWEEN_LEVELS"
