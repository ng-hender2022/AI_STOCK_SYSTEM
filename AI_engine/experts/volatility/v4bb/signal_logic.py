"""
V4BB Signal Logic
Scoring:
    Position score   : -2 to +2 (where close is relative to bands)
    Squeeze score    : -1 to +1 (squeeze breakout direction)
    Band walk score  : -0.5 to +0.5 (riding upper/lower band)
    Reversal score   : -0.5 to +0.5 (W-bottom / M-top)
    Total clamp      : -4 to +4
    bb_norm          : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import BBFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class BBOutput:
    """Scoring output for V4BB."""
    symbol: str
    date: str
    data_cutoff_date: str

    bb_score: float = 0.0
    bb_norm: float = 0.0

    position_score: float = 0.0
    squeeze_score: float = 0.0
    band_walk_score: float = 0.0
    reversal_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class BBSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: BBFeatures) -> BBOutput:
        output = BBOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # --- Component scores (already computed in feature builder) ---
        output.position_score = features.bb_position_score
        output.squeeze_score = features.bb_squeeze_score
        output.band_walk_score = features.bb_band_walk_score
        output.reversal_score = features.bb_reversal_score

        # --- Total ---
        raw = (
            output.position_score
            + output.squeeze_score
            + output.band_walk_score
            + output.reversal_score
        )
        output.bb_score = max(-4.0, min(4.0, raw))
        output.bb_norm = output.bb_score / 4.0

        # --- Quality ---
        output.signal_quality = self._compute_quality(features, output)

        # --- Signal code ---
        output.signal_code = self._signal_code(features, output)

        return output

    def _compute_quality(self, f: BBFeatures, o: BBOutput) -> int:
        """Signal quality 0-4."""
        q = self.cfg["quality"]

        # Level 4: squeeze breakout + band walk
        if f.bb_squeeze_active and o.squeeze_score != 0.0 and f.bb_band_walk != 0:
            return q["squeeze_walk"]

        # Level 3: squeeze breakout or W/M pattern
        if (f.bb_squeeze_active and o.squeeze_score != 0.0) or o.reversal_score != 0.0:
            return q["squeeze_or_pattern"]

        # Level 2: clear position beyond bands (%B > 1.0 or %B < 0.0)
        if f.bb_pct_b > 1.0 or f.bb_pct_b < 0.0:
            return q["beyond_bands"]

        # Level 1: near band but no pattern (upper or lower half)
        if f.bb_pct_b > 0.6 or f.bb_pct_b < 0.4:
            return q["near_band"]

        # Level 0: price near middle, no squeeze
        return q["neutral"]

    def _signal_code(self, f: BBFeatures, o: BBOutput) -> str:
        """Determine the signal code."""
        # Squeeze signals (highest priority when squeeze is active with breakout)
        if f.bb_squeeze_active and o.squeeze_score > 0:
            return "V4BB_BULL_SQUEEZE"
        if f.bb_squeeze_active and o.squeeze_score < 0:
            return "V4BB_BEAR_SQUEEZE"

        # Band break signals
        if f.bb_pct_b > 1.0:
            return "V4BB_BULL_BREAK"
        if f.bb_pct_b < 0.0:
            return "V4BB_BEAR_BREAK"

        # Band walk signals
        if f.bb_band_walk == 1:
            return "V4BB_BULL_WALK"
        if f.bb_band_walk == -1:
            return "V4BB_BEAR_WALK"

        # Reversal signals
        if o.reversal_score > 0:
            return "V4BB_BULL_REVERSAL"
        if o.reversal_score < 0:
            return "V4BB_BEAR_REVERSAL"

        # Squeeze active but no direction
        if f.bb_squeeze_active:
            return "V4BB_NEUT_SQUEEZE"

        # Default: near middle
        return "V4BB_NEUT_MID"
