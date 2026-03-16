"""
V4TREND_PATTERN Signal Logic
Scoring (3 components, clamped -4..+4):
    Pattern score       : -2 to +2
    Confirmation score  : -1 to +1
    Target score        : -1 to +1
    pattern_norm        : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import TPFeatures, PatternResult

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class TPOutput:
    """Scoring output for V4TREND_PATTERN."""
    symbol: str
    date: str
    data_cutoff_date: str

    pattern_score: float = 0.0
    pattern_norm: float = 0.0

    base_pattern_score: float = 0.0
    confirmation_score: float = 0.0
    target_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = "V4TP_NEUT_NO_PATTERN"
    has_sufficient_data: bool = False


class TPSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: TPFeatures) -> TPOutput:
        output = TPOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]
        pattern = features.pattern

        if pattern is None or pattern.pattern_type == "none":
            output.signal_code = "V4TP_NEUT_NO_PATTERN"
            return output

        # --- 1. Base pattern score (-2..+2) ---
        pattern_scores = scoring["pattern"]

        if pattern.pattern_type == "flag":
            if pattern.pattern_direction == "bullish":
                output.base_pattern_score = float(pattern_scores["bull_flag"])
            else:
                output.base_pattern_score = float(pattern_scores["bear_flag"])
        elif pattern.pattern_type == "pennant":
            if pattern.pattern_direction == "bullish":
                output.base_pattern_score = float(pattern_scores["bull_pennant"])
            else:
                output.base_pattern_score = float(pattern_scores["bear_pennant"])
        elif pattern.pattern_type == "double_bottom":
            output.base_pattern_score = float(pattern_scores["double_bottom"])
        elif pattern.pattern_type == "double_top":
            output.base_pattern_score = float(pattern_scores["double_top"])
        elif pattern.pattern_type == "triangle_asc":
            output.base_pattern_score = float(pattern_scores["triangle_asc"])
        elif pattern.pattern_type == "triangle_desc":
            output.base_pattern_score = float(pattern_scores["triangle_desc"])
        else:
            output.base_pattern_score = float(pattern_scores["no_pattern"])

        # --- 2. Confirmation score (-1..+1) ---
        confirm = scoring["confirmation"]

        if pattern.pattern_failure:
            output.confirmation_score = float(confirm["failure"])
        elif pattern.confirmed:
            output.confirmation_score = float(confirm["confirmed"])
        else:
            output.confirmation_score = float(confirm["forming"])

        # --- 3. Target score (-1..+1) ---
        target_cfg = scoring["target"]
        threshold = float(target_cfg["target_threshold_pct"])

        if pattern.target_pct > threshold:
            output.target_score = float(target_cfg["bullish_large"])
        elif pattern.target_pct < -threshold:
            output.target_score = float(target_cfg["bearish_large"])
        else:
            output.target_score = float(target_cfg["small"])

        # --- Total score (clamped -4..+4) ---
        raw = output.base_pattern_score + output.confirmation_score + output.target_score
        output.pattern_score = max(-4.0, min(4.0, raw))
        output.pattern_norm = output.pattern_score / 4.0

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(pattern)

        # --- Signal code ---
        output.signal_code = self._signal_code(pattern)

        return output

    def _compute_quality(self, p: PatternResult) -> int:
        """
        Quality 0-4:
            4 = Major reversal (double top/bottom) + volume confirmed + breakout
            3 = Continuation pattern (flag/pennant/triangle) + volume breakout
            2 = Pattern detected + single close breakout (or no volume confirm)
            1 = Pattern forming, no breakout yet
            0 = No pattern
        """
        if p.pattern_type == "none":
            return 0

        if not p.confirmed:
            return 1

        is_reversal = p.pattern_type in ("double_top", "double_bottom")
        has_vol = p.breakout_volume_ratio >= self.cfg["volume_breakout_ratio"]

        if is_reversal and has_vol and p.confirmed:
            return 4
        if p.confirmed and has_vol:
            return 3
        if p.confirmed:
            return 2
        return 1

    def _signal_code(self, p: PatternResult) -> str:
        """Determine signal code based on pattern."""
        if p.pattern_type == "none":
            return "V4TP_NEUT_NO_PATTERN"

        # Pattern failure overrides
        if p.pattern_failure:
            if p.pattern_direction == "bullish":
                return "V4TP_BEAR_FAILURE"
            else:
                return "V4TP_BULL_FAILURE"

        # Forming (no breakout)
        if not p.confirmed:
            return "V4TP_NEUT_FORMING"

        # Confirmed patterns
        if p.pattern_type == "flag":
            if p.pattern_direction == "bullish":
                return "V4TP_BULL_FLAG"
            else:
                return "V4TP_BEAR_FLAG"
        elif p.pattern_type == "pennant":
            # Pennant maps to flag codes per spec
            if p.pattern_direction == "bullish":
                return "V4TP_BULL_FLAG"
            else:
                return "V4TP_BEAR_FLAG"
        elif p.pattern_type == "double_bottom":
            return "V4TP_BULL_DOUBLE_BOT"
        elif p.pattern_type == "double_top":
            return "V4TP_BEAR_DOUBLE_TOP"
        elif p.pattern_type == "triangle_asc":
            return "V4TP_BULL_TRI_ASC"
        elif p.pattern_type == "triangle_desc":
            return "V4TP_BEAR_TRI_DESC"

        return "V4TP_NEUT_NO_PATTERN"
