"""
V4BR Signal Logic
Computes composite breadth score from sub-scores, applies divergence overrides,
determines signal code and quality.

Output:
    breadth_score : -4 to +4 (primary_score)
    breadth_norm  : breadth_score / 4 (secondary_score)
    signal_code   : BR_* code
    signal_quality: HIGH / MEDIUM / LOW
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import BreadthFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class BreadthOutput:
    """Scoring output for V4BR."""
    date: str
    data_cutoff_date: str

    # Scores
    breadth_score: float = 0.0       # -4..+4 (primary_score)
    breadth_norm: float = 0.0        # breadth_score / 4 (secondary_score)

    # Sub-scores (for transparency)
    score_pct_above_sma50: float = 0.0
    score_ad_ratio: float = 0.0
    score_net_new_highs: float = 0.0
    score_breadth_momentum: float = 0.0

    # Indicators
    pct_above_sma50: float = 0.0
    ad_ratio: float = 1.0
    net_new_highs: float = 0.0
    breadth_momentum: float = 0.0

    # Signal
    signal_code: str = "BR_NEUTRAL"
    signal_quality: str = "LOW"

    # Divergence
    neg_divergence: bool = False
    pos_divergence: bool = False

    # Data
    has_sufficient_data: bool = False
    total_stocks: int = 0


class BreadthSignalLogic:
    """
    Rulebook scoring engine for V4BR.

    Usage:
        logic = BreadthSignalLogic()
        output = logic.compute(features)
    """

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: BreadthFeatures) -> BreadthOutput:
        """Compute breadth score from features."""
        output = BreadthOutput(
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        output.total_stocks = features.total_stocks_with_data

        # Copy sub-scores from features
        output.score_pct_above_sma50 = features.score_pct_above_sma50
        output.score_ad_ratio = features.score_ad_ratio
        output.score_net_new_highs = features.score_net_new_highs
        output.score_breadth_momentum = features.score_breadth_momentum

        # Copy indicators
        output.pct_above_sma50 = features.pct_above_sma50
        output.ad_ratio = features.ad_ratio
        output.net_new_highs = features.net_new_highs
        output.breadth_momentum = features.breadth_momentum

        # --- Composite score: average of 4 sub-scores ---
        sub_scores = [
            features.score_pct_above_sma50,
            features.score_ad_ratio,
            features.score_net_new_highs,
            features.score_breadth_momentum,
        ]
        raw = sum(sub_scores) / len(sub_scores)
        raw = round(raw)
        raw = max(-4.0, min(4.0, float(raw)))

        # --- Divergence overrides ---
        div_cfg = self.cfg["divergence"]

        # Negative divergence: VNINDEX at 20d high but pct_above_sma50 declining 5+ days
        if (
            features.vnindex_at_20d_high
            and features.pct_above_sma50_declining_days >= div_cfg["breadth_decline_days"]
        ):
            output.neg_divergence = True
            raw = min(raw, float(div_cfg["neg_div_cap"]))

        # Positive divergence: VNINDEX at 20d low but pct_above_sma50 rising 5+ days
        if (
            features.vnindex_at_20d_low
            and features.pct_above_sma50_rising_days >= div_cfg["breadth_decline_days"]
        ):
            output.pos_divergence = True
            raw = max(raw, float(div_cfg["pos_div_floor"]))

        # Clamp final
        raw = max(-4.0, min(4.0, raw))
        output.breadth_score = raw
        output.breadth_norm = raw / 4.0

        # --- Signal code ---
        output.signal_code = self._determine_signal_code(output, sub_scores)

        # --- Signal quality ---
        output.signal_quality = self._determine_signal_quality(sub_scores, raw)

        return output

    def _determine_signal_code(
        self, output: BreadthOutput, sub_scores: list[float]
    ) -> str:
        """Determine the appropriate BR_* signal code."""
        score = output.breadth_score

        # Divergence signals take priority
        if output.neg_divergence:
            return "BR_NEG_DIVERGENCE"
        if output.pos_divergence:
            return "BR_POS_DIVERGENCE"

        # Score-based signals
        if score >= 3:
            return "BR_BROAD_ADVANCE"
        elif score <= -3:
            return "BR_BROAD_DECLINE"
        elif score >= 2:
            return "BR_HEALTHY_BULL"
        elif score <= -2:
            return "BR_HEALTHY_BEAR"
        elif score >= 1:
            # Check if it's a narrow advance (index up but breadth limited)
            if output.pct_above_sma50 < 50:
                return "BR_NARROW_ADVANCE"
            return "BR_HEALTHY_BULL"
        elif score <= -1:
            if output.pct_above_sma50 > 50:
                return "BR_NARROW_DECLINE"
            return "BR_HEALTHY_BEAR"
        else:
            return "BR_NEUTRAL"

    def _determine_signal_quality(
        self, sub_scores: list[float], composite: float
    ) -> str:
        """
        Determine signal quality based on sub-score agreement.
        HIGH: all 4 agree in direction, abs(composite) >= 3
        MEDIUM: 3/4 agree, abs(composite) >= 2
        LOW: mixed
        """
        positive = sum(1 for s in sub_scores if s > 0)
        negative = sum(1 for s in sub_scores if s < 0)
        abs_composite = abs(composite)

        q_cfg = self.cfg["quality"]

        if (positive >= q_cfg["high_min_agree"] or negative >= q_cfg["high_min_agree"]) \
                and abs_composite >= q_cfg["high_min_abs"]:
            return "HIGH"
        elif (positive >= q_cfg["medium_min_agree"] or negative >= q_cfg["medium_min_agree"]) \
                and abs_composite >= q_cfg["medium_min_abs"]:
            return "MEDIUM"
        else:
            return "LOW"
