"""
V4LIQ Signal Logic
Scoring:
    adtv_sub         : -4 to +4 (ADTV tier, weight 40%)
    consistency_sub  : -4 to +4 (volume consistency, weight 20%)
    spread_sub       : -4 to +4 (spread proxy, weight 20%)
    trend_sub        : -4 to +4 (liquidity trend, weight 20%)
    raw_score        : weighted sum, clamped -4..+4
    liq_score        : final after overrides
    liq_norm         : liq_score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import LiqFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class LiqOutput:
    """Scoring output for V4LIQ."""
    symbol: str
    date: str
    data_cutoff_date: str

    liq_score: float = 0.0
    liq_norm: float = 0.0

    adtv_sub: float = 0.0
    consistency_sub: float = 0.0
    spread_sub: float = 0.0
    trend_sub: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class LiqSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: LiqFeatures) -> LiqOutput:
        output = LiqOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # --- Sub-scores ---
        output.adtv_sub = self._adtv_tier(features)
        output.consistency_sub = self._consistency(features)
        output.spread_sub = self._spread(features)
        output.trend_sub = self._trend(features)

        # --- Weighted composite ---
        w = self.cfg["weights"]
        raw = (
            w["adtv"] * output.adtv_sub
            + w["consistency"] * output.consistency_sub
            + w["spread"] * output.spread_sub
            + w["trend"] * output.trend_sub
        )
        raw = max(-4.0, min(4.0, raw))

        # --- Overrides ---
        # Override 1: ADTV_20d < 0.1B => force -4
        if features.adtv_20d < self.cfg["untradeable_threshold"]:
            raw = -4.0

        # Override 2: Zero volume days >= 15 out of 20 => force -4
        if features.zero_volume_days >= self.cfg["zero_vol_force_neg4"]:
            raw = -4.0

        output.liq_score = round(raw, 2)
        output.liq_norm = round(output.liq_score / 4.0, 4)

        # --- Quality ---
        output.signal_quality = self._compute_quality(features)

        # --- Signal code ---
        output.signal_code = self._signal_code(features, output)

        return output

    def _adtv_tier(self, f: LiqFeatures) -> float:
        """ADTV tier sub-score based on ADTV_20d in billion VND."""
        tiers = self.cfg["adtv_tiers"]
        for tier in tiers:
            if f.adtv_20d >= tier["min"]:
                return float(tier["score"])
        return -4.0  # below lowest tier

    def _consistency(self, f: LiqFeatures) -> float:
        """Volume consistency sub-score based on CV and zero-volume days."""
        cv = f.volume_cv
        zv = f.zero_volume_days
        pct = f.pct_days_above_1b

        # +4: CV < 0.5 AND zero=0 AND pct_above_1b = 100%
        if cv < 0.5 and zv == 0 and pct >= 100.0:
            return 4.0
        # +2: CV < 0.7 AND zero=0
        if cv < 0.7 and zv == 0:
            return 2.0
        # +1: CV < 1.0 AND zero <= 1
        if cv < 1.0 and zv <= 1:
            return 1.0
        # 0: CV < 1.0 AND zero <= 3
        if cv < 1.0 and zv <= 3:
            return 0.0
        # -1: CV 1.0-1.5 OR zero 3-5
        if cv < 1.5 or zv <= 5:
            return -1.0
        # -2: CV 1.5-2.0 OR zero 5-10
        if cv < 2.0 or zv <= 10:
            return -2.0
        # -4: CV > 2.0 OR zero > 10
        return -4.0

    def _spread(self, f: LiqFeatures) -> float:
        """Spread proxy sub-score based on HL_Spread_20d_Avg (%)."""
        tiers = self.cfg["spread_tiers"]
        for tier in tiers:
            if f.hl_spread_avg < tier["max"]:
                return float(tier["score"])
        return -4.0  # above highest max threshold

    def _trend(self, f: LiqFeatures) -> float:
        """Liquidity trend sub-score based on ADTV_Ratio."""
        ratio = f.adtv_ratio

        # +4: ratio > 1.5 AND recent breakout
        if ratio > 1.5 and f.has_recent_breakout:
            return 4.0
        # +3: ratio > 1.3
        if ratio > 1.3:
            return 3.0
        # +2: ratio > 1.15
        if ratio > 1.15:
            return 2.0
        # +1: ratio 1.05 - 1.15
        if ratio > 1.05:
            return 1.0
        # 0: ratio 0.90 - 1.05
        if ratio >= 0.90:
            return 0.0
        # -1: ratio 0.75 - 0.90
        if ratio >= 0.75:
            return -1.0
        # -2: ratio 0.60 - 0.75
        if ratio >= 0.60:
            return -2.0
        # -3: ratio < 0.60
        # -4: ratio < 0.40 AND recent drought
        if ratio < 0.40 and f.has_recent_drought:
            return -4.0
        return -3.0

    def _compute_quality(self, f: LiqFeatures) -> int:
        """Signal quality 0-4."""
        q = self.cfg["quality"]

        # HIGH (4): ADTV > 10B, CV < 0.7, zero=0
        if (f.adtv_20d >= q["high"]["min_adtv"]
                and f.volume_cv < q["high"]["max_cv"]
                and f.zero_volume_days <= q["high"]["max_zero_days"]):
            return 4

        # MEDIUM (3): ADTV 2-10B, CV < 1.0, zero <= 3
        if (f.adtv_20d >= q["medium"]["min_adtv"]
                and f.volume_cv < q["medium"]["max_cv"]
                and f.zero_volume_days <= q["medium"]["max_zero_days"]):
            return 3

        # LOW (2): ADTV >= 0.1B (tradeable but poor)
        if f.adtv_20d >= self.cfg["untradeable_threshold"]:
            return 2

        # REJECT (1): untradeable
        if f.adtv_20d > 0:
            return 1

        return 0

    def _signal_code(self, f: LiqFeatures, o: LiqOutput) -> str:
        """Determine the primary signal code."""
        score = o.liq_score

        # Primary tier code based on score
        if score >= 3.5:
            primary = "LIQ_MEGA"
        elif score >= 2.5:
            primary = "LIQ_HIGH"
        elif score >= 1.5:
            primary = "LIQ_GOOD"
        elif score >= 0.5:
            primary = "LIQ_MODERATE"
        elif score >= -0.5:
            primary = "LIQ_LOW"
        elif score >= -1.5:
            primary = "LIQ_VERY_LOW"
        elif score >= -2.5:
            primary = "LIQ_ILLIQUID"
        elif score >= -3.5:
            primary = "LIQ_VERY_ILLIQUID"
        else:
            primary = "LIQ_UNTRADEABLE"

        # Override with trend/event codes if applicable
        if f.has_recent_breakout and f.adtv_ratio > 1.5:
            return "LIQ_SURGE"
        if f.has_recent_drought and f.adtv_ratio < 0.40:
            return "LIQ_DROUGHT"
        if f.adtv_ratio > 1.15:
            return "LIQ_IMPROVING"
        if f.adtv_ratio < 0.85:
            return "LIQ_DECLINING"

        return primary
