"""
V4V Signal Logic
Scoring:
    Confirmation score : -2 to +2 (volume-price confirmation)
    Trend score        : -1 to +1 (volume trend)
    Divergence score   : -1 to +1 (volume-price divergence)
    Total clamp        : -4 to +4
    volume_norm        : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import VolFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class VolOutput:
    """Scoring output for V4V."""
    symbol: str
    date: str
    data_cutoff_date: str

    volume_score: float = 0.0
    volume_norm: float = 0.0

    confirmation_score: float = 0.0
    trend_score: float = 0.0
    divergence_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class VolSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: VolFeatures) -> VolOutput:
        output = VolOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # --- Confirmation score (-2 to +2) ---
        output.confirmation_score = self._confirmation(features)

        # --- Trend score (-1 to +1) ---
        output.trend_score = self._trend(features)

        # --- Divergence score (-1 to +1) ---
        output.divergence_score = self._divergence(features)

        # --- Total ---
        raw = output.confirmation_score + output.trend_score + output.divergence_score
        output.volume_score = max(-4.0, min(4.0, raw))
        output.volume_norm = output.volume_score / 4.0

        # --- Quality ---
        output.signal_quality = self._compute_quality(features)

        # --- Signal code ---
        output.signal_code = self._signal_code(features, output)

        return output

    def _confirmation(self, f: VolFeatures) -> float:
        """Volume-Price Confirmation: -2 to +2."""
        cfg = self.cfg["scoring"]["confirmation"]
        price_up = f.price_return > 0
        surge = f.vol_ratio > self.cfg["surge_threshold"]
        above_avg = f.vol_ratio > self.cfg["above_avg_threshold"]
        below_avg = f.vol_ratio < self.cfg["below_avg_threshold"]

        if price_up:
            if surge:
                return float(cfg["price_up_surge"])          # +2
            elif above_avg:
                return float(cfg["price_up_above_avg"])      # +1
            elif below_avg:
                return float(cfg["price_up_below_avg"])      # -0.5
        else:
            if surge:
                return float(cfg["price_down_surge"])        # -2
            elif above_avg:
                return float(cfg["price_down_above_avg"])    # -1
            elif below_avg:
                return float(cfg["price_down_below_avg"])    # +0.5
        return 0.0

    def _trend(self, f: VolFeatures) -> float:
        """Volume Trend: -1 to +1."""
        if f.vol_trend_5 > self.cfg["trend_expand"]:
            return float(self.cfg["scoring"]["trend"]["expanding"])     # +1
        elif f.vol_trend_5 < self.cfg["trend_contract"]:
            return float(self.cfg["scoring"]["trend"]["contracting"])   # -1
        return 0.0

    def _divergence(self, f: VolFeatures) -> float:
        """Volume-Price Divergence: -1 to +1."""
        price_falling = f.price_return < 0
        price_rising = f.price_return > 0
        vol_declining = f.vol_trend_5 < 1.0  # below 20-day avg trend

        if price_falling and vol_declining:
            return float(self.cfg["scoring"]["divergence"]["exhaustion"])   # +1 (exhausted selling)
        elif price_rising and vol_declining:
            return float(self.cfg["scoring"]["divergence"]["weak_rally"])   # -1 (weak rally)
        return 0.0

    def _compute_quality(self, f: VolFeatures) -> int:
        """Signal quality 0-4."""
        q = self.cfg["quality"]

        # Level 4: climax + reversal pattern (climax volume)
        if f.climax:
            return q["climax_reversal"]

        # Level 3: surge (>2x) + clear direction
        if f.vol_ratio > self.cfg["surge_threshold"] and abs(f.price_return) > 0.005:
            return q["surge_direction"]

        # Level 2: above avg + direction match
        if f.vol_ratio > self.cfg["above_avg_threshold"] and abs(f.price_return) > 0.002:
            return q["above_avg_match"]

        # Level 1: mild change or divergence
        if abs(f.vol_ratio - 1.0) > 0.1 or (f.price_return > 0 and f.vol_trend_5 < 1.0) or (f.price_return < 0 and f.vol_trend_5 < 1.0):
            return q["mild"]

        return q["normal"]

    def _signal_code(self, f: VolFeatures, o: VolOutput) -> str:
        """Determine the signal code."""
        price_up = f.price_return > 0
        price_down = f.price_return < 0
        surge = f.vol_ratio > self.cfg["surge_threshold"]
        vol_declining = f.vol_trend_5 < 1.0
        drying = f.vol_ratio < self.cfg["drying_threshold"]

        # Climax signals
        if f.climax:
            if price_down:
                return "V4V_BULL_CLIMAX_BOT"   # climax at bottom (potential reversal up)
            else:
                return "V4V_BEAR_CLIMAX_TOP"   # climax at top (potential reversal down)

        # Surge/expansion signals
        if surge:
            if price_up:
                return "V4V_BULL_EXPAND"
            else:
                return "V4V_BEAR_EXPAND"

        # Divergence signals
        if price_up and vol_declining:
            return "V4V_BEAR_DIV"        # price up but volume declining = bearish divergence
        if price_down and vol_declining:
            return "V4V_BULL_DIV"        # price down but volume declining = bullish divergence

        # Drying up
        if drying:
            return "V4V_NEUT_DRY"

        # Confirmation signals (above avg volume confirming direction)
        if f.vol_ratio > self.cfg["above_avg_threshold"]:
            if price_up:
                return "V4V_BULL_CONFIRM"
            elif price_down:
                return "V4V_BEAR_CONFIRM"

        # Default: use overall score direction for mild confirmation
        if o.volume_score > 0:
            return "V4V_BULL_CONFIRM"
        elif o.volume_score < 0:
            return "V4V_BEAR_CONFIRM"
        return "V4V_NEUT_DRY"
