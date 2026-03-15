"""
V4I Ichimoku Signal Logic
Scoring rules:
    Cloud position  : above=+2, inside=0, below=-2
    TK signal       : tenkan>kijun=+1, tenkan<kijun=-1
    Chikou confirm  : chikou>price_26=+1, chikou<price_26=-1
    Future cloud    : bullish+aligned=+1, bearish+aligned=-1
    Total clamp     : -4..+4
    Normalized      : ichimoku_norm = score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import IchimokuFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class IchimokuOutput:
    """Scoring output for V4I on 1 symbol, 1 date."""
    symbol: str
    date: str
    data_cutoff_date: str

    # Main scores
    ichimoku_score: float = 0.0         # -4..+4
    ichimoku_norm: float = 0.0          # -1..+1 (score/4)

    # Component signals
    cloud_position: str = "inside"      # above / inside / below
    cloud_position_score: float = 0.0
    tk_signal: str = "neutral"          # bullish / bearish / neutral
    tk_signal_score: float = 0.0
    chikou_confirm: str = "neutral"     # bullish / bearish / neutral
    chikou_confirm_score: float = 0.0
    future_cloud: str = "flat"          # bullish / bearish / flat
    future_cloud_score: float = 0.0

    # Time theory
    time_resonance: float = 0.0         # 0..1
    days_since_pivot: int = 0
    near_cycle: int = 0                 # 0 if none, else cycle number (9,26,...)

    # Quality & metadata
    signal_quality: int = 0             # 0..4
    signal_code: str = ""
    has_sufficient_data: bool = False


class IchimokuSignalLogic:
    """
    Rulebook scoring for V4I.

    Usage:
        logic = IchimokuSignalLogic()
        output = logic.compute(features)
    """

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: IchimokuFeatures) -> IchimokuOutput:
        """Compute Ichimoku score from features."""
        output = IchimokuOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True
        scoring = self.cfg["scoring"]

        # --- 1. Cloud position ---
        if features.close > features.cloud_top:
            output.cloud_position = "above"
            output.cloud_position_score = float(scoring["cloud_position"]["above"])
        elif features.close < features.cloud_bottom:
            output.cloud_position = "below"
            output.cloud_position_score = float(scoring["cloud_position"]["below"])
        else:
            output.cloud_position = "inside"
            output.cloud_position_score = float(scoring["cloud_position"]["inside"])

        # --- 2. Tenkan vs Kijun ---
        if features.tenkan > features.kijun:
            output.tk_signal = "bullish"
            output.tk_signal_score = float(scoring["tk_signal"]["tenkan_above"])
        elif features.tenkan < features.kijun:
            output.tk_signal = "bearish"
            output.tk_signal_score = float(scoring["tk_signal"]["tenkan_below"])
        else:
            output.tk_signal = "neutral"
            output.tk_signal_score = 0.0

        # --- 3. Chikou confirmation ---
        if features.price_26_ago > 0:
            if features.chikou > features.price_26_ago:
                output.chikou_confirm = "bullish"
                output.chikou_confirm_score = float(
                    scoring["chikou_confirm"]["above_price_26"]
                )
            elif features.chikou < features.price_26_ago:
                output.chikou_confirm = "bearish"
                output.chikou_confirm_score = float(
                    scoring["chikou_confirm"]["below_price_26"]
                )

        # --- 4. Future cloud bonus ---
        # Only awarded when strong alignment exists
        future_bullish = features.senkou_a_future > features.senkou_b_future
        future_bearish = features.senkou_a_future < features.senkou_b_future

        bullish_count = sum([
            output.cloud_position_score > 0,
            output.tk_signal_score > 0,
            output.chikou_confirm_score > 0,
        ])
        bearish_count = sum([
            output.cloud_position_score < 0,
            output.tk_signal_score < 0,
            output.chikou_confirm_score < 0,
        ])

        if future_bullish and bullish_count >= 2:
            output.future_cloud = "bullish"
            output.future_cloud_score = float(
                scoring["future_cloud_bonus"]["bullish_aligned"]
            )
        elif future_bearish and bearish_count >= 2:
            output.future_cloud = "bearish"
            output.future_cloud_score = float(
                scoring["future_cloud_bonus"]["bearish_aligned"]
            )
        else:
            if future_bullish:
                output.future_cloud = "bullish"
            elif future_bearish:
                output.future_cloud = "bearish"
            else:
                output.future_cloud = "flat"
            output.future_cloud_score = 0.0

        # --- 5. Total score ---
        raw = (
            output.cloud_position_score
            + output.tk_signal_score
            + output.chikou_confirm_score
            + output.future_cloud_score
        )
        output.ichimoku_score = max(-4.0, min(4.0, raw))
        output.ichimoku_norm = output.ichimoku_score / 4.0

        # --- 6. Time theory ---
        self._compute_time_resonance(output, features)

        # --- 7. Signal quality ---
        output.signal_quality = self._compute_quality(output)

        # --- 8. Signal code ---
        output.signal_code = self._determine_signal_code(output)

        return output

    def _compute_time_resonance(
        self, output: IchimokuOutput, features: IchimokuFeatures
    ) -> None:
        """Detect proximity to Ichimoku time cycles."""
        time_cfg = self.cfg["time_theory"]
        cycles = time_cfg["key_cycles"]
        tolerance = time_cfg["tolerance"]
        days = features.days_since_pivot

        if days <= 0:
            output.time_resonance = 0.0
            return

        best_dist = float("inf")
        best_cycle = 0
        for c in cycles:
            dist = abs(days - c)
            if dist < best_dist:
                best_dist = dist
                best_cycle = c

        if best_dist <= tolerance:
            output.near_cycle = best_cycle
            output.time_resonance = 1.0 - (best_dist / (tolerance + 1))
        else:
            output.time_resonance = 0.0

        output.days_since_pivot = days

    def _compute_quality(self, output: IchimokuOutput) -> int:
        """
        Signal quality 0..4 based on component alignment.
        Count how many components agree on the same direction.
        """
        bullish = sum([
            output.cloud_position_score > 0,
            output.tk_signal_score > 0,
            output.chikou_confirm_score > 0,
            output.future_cloud_score > 0,
        ])
        bearish = sum([
            output.cloud_position_score < 0,
            output.tk_signal_score < 0,
            output.chikou_confirm_score < 0,
            output.future_cloud_score < 0,
        ])

        aligned = max(bullish, bearish)
        quality_cfg = self.cfg["quality"]

        if aligned >= quality_cfg["level_4"]:
            return 4
        elif aligned >= quality_cfg["level_3"]:
            return 3
        elif aligned >= quality_cfg["level_2"]:
            return 2
        elif aligned >= quality_cfg["level_1"]:
            return 1
        return 0

    def _determine_signal_code(self, output: IchimokuOutput) -> str:
        """Determine signal code per SIGNAL_CODEBOOK."""
        if output.ichimoku_score == 0:
            return "V4I_NEUT_INSIDE_CLOUD"

        if output.ichimoku_score >= 3:
            if output.cloud_position == "above":
                return "V4I_BULL_BREAK_CLOUD"
            return "V4I_BULL_TREND_ABOVE"
        elif output.ichimoku_score >= 1:
            if output.tk_signal == "bullish":
                return "V4I_BULL_CROSS_TK"
            return "V4I_BULL_TREND_ABOVE"
        elif output.ichimoku_score <= -3:
            if output.cloud_position == "below":
                return "V4I_BEAR_BREAK_CLOUD"
            return "V4I_BEAR_TREND_BELOW"
        elif output.ichimoku_score <= -1:
            if output.tk_signal == "bearish":
                return "V4I_BEAR_CROSS_TK"
            return "V4I_BEAR_TREND_BELOW"

        return "V4I_NEUT_INSIDE_CLOUD"
