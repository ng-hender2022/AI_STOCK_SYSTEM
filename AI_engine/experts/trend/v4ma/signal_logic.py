"""
V4MA Signal Logic
Scoring:
    Alignment score  : -3 to +3 (based on close vs all MAs)
    Cross bonus      : -1 to +1 (golden/death cross, short cross)
    Total clamp      : -4 to +4
    ma_norm          : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import MAFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class MAOutput:
    """Scoring output for V4MA."""
    symbol: str
    date: str
    data_cutoff_date: str

    ma_score: float = 0.0
    ma_norm: float = 0.0

    alignment: str = "neutral"
    alignment_score: float = 0.0
    cross_signal: str = "none"
    cross_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class MASignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: MAFeatures) -> MAOutput:
        output = MAOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]

        # --- Alignment score ---
        c = features.close
        e10, e20 = features.ema10, features.ema20
        s50, s100, s200 = features.sma50, features.sma100, features.sma200

        if c > e10 > e20 > s50 > s100 > s200:
            output.alignment = "all_bullish"
            output.alignment_score = float(scoring["alignment"]["all_bullish"])
        elif c > e20 > s50 > s100:
            output.alignment = "strong_bullish"
            output.alignment_score = float(scoring["alignment"]["strong_bullish"])
        elif c > e20 > s50:
            output.alignment = "mild_bullish"
            output.alignment_score = float(scoring["alignment"]["mild_bullish"])
        elif c < e10 < e20 < s50 < s100 < s200:
            output.alignment = "all_bearish"
            output.alignment_score = float(scoring["alignment"]["all_bearish"])
        elif c < e20 < s50 < s100:
            output.alignment = "strong_bearish"
            output.alignment_score = float(scoring["alignment"]["strong_bearish"])
        elif c < e20 < s50:
            output.alignment = "mild_bearish"
            output.alignment_score = float(scoring["alignment"]["mild_bearish"])
        else:
            output.alignment = "neutral"
            output.alignment_score = 0.0

        # --- Cross score ---
        cross_cfg = scoring["cross"]
        if features.golden_cross:
            output.cross_signal = "golden_cross"
            output.cross_score = float(cross_cfg["golden_cross"])
        elif features.death_cross:
            output.cross_signal = "death_cross"
            output.cross_score = float(cross_cfg["death_cross"])
        elif features.short_cross_up:
            output.cross_signal = "short_cross_up"
            output.cross_score = float(cross_cfg["short_cross_up"])
        elif features.short_cross_down:
            output.cross_signal = "short_cross_down"
            output.cross_score = float(cross_cfg["short_cross_down"])

        # --- Total ---
        raw = output.alignment_score + output.cross_score
        output.ma_score = max(-4.0, min(4.0, raw))
        output.ma_norm = output.ma_score / 4.0

        # --- Quality ---
        output.signal_quality = self._compute_quality(features)

        # --- Signal code ---
        output.signal_code = self._signal_code(output)

        return output

    def _compute_quality(self, f: MAFeatures) -> int:
        """Quality based on how many MAs confirm same direction as close."""
        c = f.close
        bullish = sum([c > f.ema10, c > f.ema20, c > f.sma50, c > f.sma100, c > f.sma200])
        bearish = sum([c < f.ema10, c < f.ema20, c < f.sma50, c < f.sma100, c < f.sma200])
        aligned = max(bullish, bearish)
        q_cfg = self.cfg["quality"]
        if aligned >= q_cfg["level_4"]:
            return 4
        elif aligned >= q_cfg["level_3"]:
            return 3
        elif aligned >= q_cfg["level_2"]:
            return 2
        elif aligned >= q_cfg["level_1"]:
            return 1
        return 0

    def _signal_code(self, o: MAOutput) -> str:
        if o.cross_signal == "golden_cross":
            return "V4MA_BULL_CROSS_GOLDEN"
        if o.cross_signal == "death_cross":
            return "V4MA_BEAR_CROSS_DEATH"
        if o.cross_signal == "short_cross_up":
            return "V4MA_BULL_CROSS_SHORT"
        if o.cross_signal == "short_cross_down":
            return "V4MA_BEAR_CROSS_SHORT"
        if o.alignment_score >= 2:
            return "V4MA_BULL_TREND_ALIGNED"
        if o.alignment_score <= -2:
            return "V4MA_BEAR_TREND_ALIGNED"
        if o.alignment_score > 0:
            return "V4MA_BULL_CROSS_SHORT"
        if o.alignment_score < 0:
            return "V4MA_BEAR_CROSS_SHORT"
        return "V4MA_NEUT_MIXED"
