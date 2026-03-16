"""
V4P Signal Logic
Scoring (3 components, clamped -4..+4):
    Trend structure score : -2 to +2
    Range/Breakout score  : -1 to +1
    SMA20 score           : -1 to +1
    price_action_norm     : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import PAFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class PAOutput:
    """Scoring output for V4P."""
    symbol: str
    date: str
    data_cutoff_date: str

    price_action_score: float = 0.0
    price_action_norm: float = 0.0

    trend_score: float = 0.0
    range_score: float = 0.0
    sma20_score: float = 0.0

    signal_quality: int = 0
    signal_code: str = ""
    has_sufficient_data: bool = False


class PASignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: PAFeatures) -> PAOutput:
        output = PAOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]

        # --- 1. Trend structure score (-2..+2) ---
        bull_pts = features.hh_count + features.hl_count
        bear_pts = features.lh_count + features.ll_count

        if features.trend_structure == "UPTREND":
            if bull_pts >= 4:
                output.trend_score = float(scoring["trend"]["uptrend"])  # +2
            else:
                output.trend_score = float(scoring["trend"]["mild_up"])  # +1
        elif features.trend_structure == "DOWNTREND":
            if bear_pts >= 4:
                output.trend_score = float(scoring["trend"]["downtrend"])  # -2
            else:
                output.trend_score = float(scoring["trend"]["mild_down"])  # -1
        else:
            # CONSOLIDATION: check for slight bias
            if bull_pts > bear_pts and bull_pts >= 1:
                output.trend_score = float(scoring["trend"]["mild_up"])  # +1
            elif bear_pts > bull_pts and bear_pts >= 1:
                output.trend_score = float(scoring["trend"]["mild_down"])  # -1
            else:
                output.trend_score = float(scoring["trend"]["consolidation"])  # 0

        # --- 2. Range / Breakout score (-1..+1) ---
        if features.breakout_flag:
            output.range_score = float(scoring["range"]["breakout"])  # +1
        elif features.breakdown_flag:
            output.range_score = float(scoring["range"]["breakdown"])  # -1
        else:
            output.range_score = float(scoring["range"]["neutral"])  # 0

        # --- 3. SMA20 score (-1..+1) ---
        close_above_sma = features.close > features.sma20
        close_below_sma = features.close < features.sma20
        slope_positive = features.sma20_slope > 0
        slope_negative = features.sma20_slope < 0

        if close_above_sma and slope_positive:
            output.sma20_score = float(scoring["sma20"]["bullish"])  # +1
        elif close_below_sma and slope_negative:
            output.sma20_score = float(scoring["sma20"]["bearish"])  # -1
        else:
            output.sma20_score = float(scoring["sma20"]["neutral"])  # 0

        # --- Total score (clamped -4..+4) ---
        raw = output.trend_score + output.range_score + output.sma20_score
        output.price_action_score = max(-4.0, min(4.0, raw))
        output.price_action_norm = output.price_action_score / 4.0

        # --- Signal quality ---
        output.signal_quality = self._compute_quality(output, features)

        # --- Signal code ---
        output.signal_code = self._signal_code(output, features)

        return output

    def _compute_quality(self, o: PAOutput, f: PAFeatures) -> int:
        """
        Quality 0-4:
            4 = breakout/breakdown + trend confirm + SMA20 confirm
            3 = trend + breakout (or trend + SMA)
            2 = trend only (clear structure)
            1 = weak / partial
            0 = none
        """
        has_trend = f.trend_structure in ("UPTREND", "DOWNTREND")
        has_breakout = f.breakout_flag or f.breakdown_flag
        has_sma_confirm = abs(o.sma20_score) > 0

        # Check directional alignment
        trend_dir = 1 if f.trend_structure == "UPTREND" else (-1 if f.trend_structure == "DOWNTREND" else 0)
        breakout_dir = 1 if f.breakout_flag else (-1 if f.breakdown_flag else 0)
        sma_dir = 1 if o.sma20_score > 0 else (-1 if o.sma20_score < 0 else 0)

        confirms = 0
        if has_trend:
            confirms += 1
        if has_breakout and breakout_dir == trend_dir:
            confirms += 1
        elif has_breakout and trend_dir == 0:
            confirms += 1
        if has_sma_confirm and sma_dir == trend_dir:
            confirms += 1
        elif has_sma_confirm and trend_dir == 0:
            confirms += 1

        if has_trend and has_breakout and has_sma_confirm:
            # All three aligned in same direction
            all_same = (trend_dir == breakout_dir == sma_dir) or (trend_dir != 0 and breakout_dir == trend_dir and sma_dir == trend_dir)
            if all_same:
                return 4
            return 3
        if has_trend and (has_breakout or has_sma_confirm):
            return 3
        if has_trend:
            return 2
        if has_breakout or has_sma_confirm:
            return 1
        return 0

    def _signal_code(self, o: PAOutput, f: PAFeatures) -> str:
        """Determine signal code based on output."""
        # Breakout / Breakdown signals take priority
        if f.breakout_flag and f.trend_structure == "DOWNTREND":
            return "V4P_BULL_REVERSAL"
        if f.breakdown_flag and f.trend_structure == "UPTREND":
            return "V4P_BEAR_REVERSAL"
        if f.breakout_flag:
            return "V4P_BULL_BREAK"
        if f.breakdown_flag:
            return "V4P_BEAR_BREAK"

        # Trend signals
        if o.price_action_score >= 2:
            return "V4P_BULL_TREND"
        if o.price_action_score <= -2:
            return "V4P_BEAR_TREND"

        # Consolidation / neutral
        return "V4P_NEUT_CONSOLIDATION"
