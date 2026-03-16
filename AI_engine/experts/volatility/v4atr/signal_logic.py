"""
V4ATR Signal Logic
Scoring:
    atr_score    : 0 to 4 (volatility magnitude, direction-neutral)
    atr_norm     : atr_score / 4 (range 0..1)
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import ATRFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class ATROutput:
    """Scoring output for V4ATR."""
    symbol: str
    date: str
    data_cutoff_date: str

    atr_score: int = 0          # 0..4
    atr_norm: float = 0.0       # atr_score / 4

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class ATRSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: ATRFeatures) -> ATROutput:
        output = ATROutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # --- Scores (already computed in feature_builder) ---
        output.atr_score = features.atr_score
        output.atr_norm = features.atr_norm

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(features)

        # --- Signal code ---
        output.signal_code = self._signal_code(features)

        return output

    def _compute_quality(self, f: ATRFeatures) -> int:
        """Signal quality 0-4."""
        q = self.cfg["quality"]
        pct = f.atr_percentile

        # Quality 4: Extreme ATR with clear setup (climax + expanding or squeeze + contracting)
        if (pct > 95 and f.atr_expanding) or (pct < 5 and f.atr_contracting):
            return q["extreme_setup"]

        # Quality 3: ATR at percentile extremes (>90 or <10)
        if pct > 90 or pct < 10:
            return q["percentile_extreme"]

        # Quality 2: Noticeable expansion/contraction
        if f.atr_expanding or f.atr_contracting:
            return q["noticeable_change"]

        # Quality 1: Slightly outside normal (percentile <25 or >75)
        if pct < 25 or pct > 75:
            return q["slightly_outside"]

        # Quality 0: Normal range
        return q["normal"]

    def _signal_code(self, f: ATRFeatures) -> str:
        """Determine the signal code."""
        pct = f.atr_percentile
        price_up = f.price_return > 0
        price_down = f.price_return < 0
        regime_cfg = self.cfg["regime"]

        # SQUEEZE: very low ATR, potential squeeze
        if f.vol_regime == "SQUEEZE":
            return "V4ATR_NEUT_SQUEEZE"

        # CLIMAX: ATR extreme, exhaustion
        if pct > regime_cfg["climax_percentile"]:
            # Extreme ATR with price direction -> panic or exhaustion
            if price_down:
                return "V4ATR_BEAR_EXTREME"
            return "V4ATR_NEUT_CLIMAX"

        # EXPANSION: ATR expanding with direction
        if f.atr_expanding:
            if price_up:
                return "V4ATR_BULL_EXPAND"
            elif price_down:
                return "V4ATR_BEAR_EXPAND"

        # Normal volatility
        return "V4ATR_NEUT_NORMAL"
