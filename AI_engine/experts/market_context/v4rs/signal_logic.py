"""
V4RS Signal Logic
Scoring:
    Primary score from Decile x Trend matrix: -4 to +4
    Modifiers: rapid rank change, all periods agree, acceleration
    Total clamp: -4 to +4
    rs_norm = rs_score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .feature_builder import RSFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class RSOutput:
    """Scoring output for V4RS."""
    symbol: str
    date: str
    data_cutoff_date: str

    rs_score: float = 0.0
    rs_norm: float = 0.0

    primary_score: float = 0.0
    modifier_rank_change: float = 0.0
    modifier_all_agree: float = 0.0
    modifier_acceleration: float = 0.0

    signal_quality: int = 0
    signal_code: str = "RS_NEUTRAL"
    has_sufficient_data: bool = False


# Signal code mapping by score
_SIGNAL_MAP = {
    4: "RS_TOP_LEADER",
    3: "RS_EMERGING_LEADER",
    2: "RS_OUTPERFORMER",
    1: "RS_MILD_OUTPERFORM",
    0: "RS_NEUTRAL",
    -1: "RS_MILD_UNDERPERFORM",
    -2: "RS_UNDERPERFORMER",
    -3: "RS_DETERIORATING",
    -4: "RS_BOTTOM_LAGGARD",
}


class RSSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: RSFeatures) -> RSOutput:
        output = RSOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]

        # --- Primary score from decile x trend matrix ---
        decile = features.rs_decile
        trend = features.rs_trend

        decile_key = max(1, min(10, decile))
        trend_key = trend if trend in ("RISING", "FLAT", "FALLING") else "FLAT"
        output.primary_score = float(scoring["decile_trend"][decile_key][trend_key])

        # --- Modifiers ---
        rank_threshold = self.cfg["rank_change_threshold"]

        # Rapid rank change modifier
        if features.rs_rank_change_10d > rank_threshold:
            output.modifier_rank_change = 1.0
        elif features.rs_rank_change_10d < -rank_threshold:
            output.modifier_rank_change = -1.0

        # All periods agree modifier
        if features.all_periods_agree:
            output.modifier_all_agree = float(features.all_periods_direction)

        # Acceleration modifier
        if features.rs_acceleration > 0 and features.rs_trend == "RISING":
            output.modifier_acceleration = 1.0
        elif features.rs_acceleration < 0 and features.rs_trend == "FALLING":
            output.modifier_acceleration = -1.0

        # --- Total ---
        raw = (
            output.primary_score
            + output.modifier_rank_change
            + output.modifier_all_agree
            + output.modifier_acceleration
        )
        output.rs_score = max(-4.0, min(4.0, raw))
        output.rs_norm = output.rs_score / 4.0

        # --- Quality ---
        output.signal_quality = self._compute_quality(features)

        # --- Signal code ---
        output.signal_code = self._signal_code(output)

        return output

    def _compute_quality(self, f: RSFeatures) -> int:
        """Quality based on decile extremity, trend confirmation, period agreement."""
        q_cfg = self.cfg["quality"]
        extreme = q_cfg["extreme_decile"]
        strong = q_cfg["strong_decile"]

        score = 0

        # Decile extremity
        if f.rs_decile <= extreme or f.rs_decile >= (11 - extreme):
            score += 2  # extreme decile
        elif f.rs_decile <= strong or f.rs_decile >= (11 - strong):
            score += 1  # strong decile

        # Trend confirms direction
        if f.rs_decile <= 5 and f.rs_trend == "RISING":
            score += 1
        elif f.rs_decile > 5 and f.rs_trend == "FALLING":
            score += 1

        # All periods agree
        if f.all_periods_agree:
            score += 1

        return min(4, score)

    def _signal_code(self, o: RSOutput) -> str:
        """Map rounded score to signal code."""
        rounded = int(round(o.rs_score))
        rounded = max(-4, min(4, rounded))
        return _SIGNAL_MAP.get(rounded, "RS_NEUTRAL")
