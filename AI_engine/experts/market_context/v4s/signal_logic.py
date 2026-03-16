"""
V4S Signal Logic
Scoring:
    Sector strength sub-score : -4 to +4
    Momentum modifier         : -1 to +1
    Breadth modifier          : -1 to +1
    Stock-within-sector mod   : -1 to +1
    Total clamp               : -4 to +4
    sector_norm               : score / 4
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_builder import SectorFeatures

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class SectorOutput:
    """Scoring output for V4S."""
    symbol: str
    date: str
    data_cutoff_date: str

    sector_score: float = 0.0
    sector_norm: float = 0.0

    sector_strength_sub: float = 0.0
    momentum_mod: float = 0.0
    breadth_mod: float = 0.0
    stock_within_sector_mod: float = 0.0

    signal_quality: int = 0
    signal_code: str = "SEC_NEUTRAL"
    signal_codes: list = None  # all applicable codes

    has_sufficient_data: bool = False
    is_singleton: bool = False

    def __post_init__(self):
        if self.signal_codes is None:
            self.signal_codes = []


class SectorSignalLogic:

    def __init__(self):
        self.cfg = _load_config()

    def compute(self, features: SectorFeatures) -> SectorOutput:
        output = SectorOutput(
            symbol=features.symbol,
            date=features.date,
            data_cutoff_date=features.data_cutoff_date,
        )

        if not features.has_sufficient_data:
            return output

        output.has_sufficient_data = True

        # Singleton sector: score=0, quality=0
        if features.is_singleton:
            output.is_singleton = True
            output.signal_code = "SEC_SINGLETON"
            output.signal_codes = ["SEC_SINGLETON"]
            return output

        num_sectors = features.num_sectors
        if num_sectors == 0:
            return output

        # --- Sector Strength Sub-Score ---
        rank = features.sector_rank_20d
        vs_mkt = features.sector_vs_market_20d
        top_half = rank <= num_sectors / 2
        bottom_half = rank > num_sectors / 2
        middle_third_lo = num_sectors / 3
        middle_third_hi = 2 * num_sectors / 3

        if rank == 1 and vs_mkt > 0.05:
            output.sector_strength_sub = 4.0
        elif rank <= 2 and vs_mkt > 0.03:
            output.sector_strength_sub = 3.0
        elif rank <= 3 and vs_mkt > 0.01:
            output.sector_strength_sub = 2.0
        elif top_half and vs_mkt > 0:
            output.sector_strength_sub = 1.0
        elif middle_third_lo < rank <= middle_third_hi:
            output.sector_strength_sub = 0.0
        elif rank == num_sectors and vs_mkt < -0.05:
            output.sector_strength_sub = -4.0
        elif rank >= num_sectors - 1 and vs_mkt < -0.03:
            output.sector_strength_sub = -3.0
        elif rank >= num_sectors - 2 and vs_mkt < -0.01:
            output.sector_strength_sub = -2.0
        elif bottom_half and vs_mkt < 0:
            output.sector_strength_sub = -1.0
        else:
            output.sector_strength_sub = 0.0

        # --- Momentum Modifier ---
        momentum = features.sector_momentum
        rank_change = features.sector_rank_change_10d
        rotation_threshold = self.cfg["periods"]["rotation_threshold"]

        if momentum > 0 and top_half:
            output.momentum_mod += 1.0
        elif momentum < 0 and top_half:
            output.momentum_mod -= 1.0
        elif momentum < 0 and bottom_half:
            output.momentum_mod -= 1.0

        if rank_change >= rotation_threshold:
            output.momentum_mod += 1.0
        elif rank_change <= -rotation_threshold:
            output.momentum_mod -= 1.0

        # --- Breadth Modifier ---
        pct_above = features.sector_pct_above_sma50
        if pct_above > 80:
            output.breadth_mod += 1.0
        elif pct_above < 20:
            output.breadth_mod -= 1.0

        # --- Stock-within-Sector Modifier ---
        if features.is_sector_leader and features.stock_vs_sector_20d > 0.03:
            output.stock_within_sector_mod += 1.0
        elif features.is_sector_laggard and features.stock_vs_sector_20d < -0.03:
            output.stock_within_sector_mod -= 1.0

        # --- Final Score ---
        raw = (output.sector_strength_sub + output.momentum_mod +
               output.breadth_mod + output.stock_within_sector_mod)
        output.sector_score = max(-4.0, min(4.0, raw))
        output.sector_norm = output.sector_score / 4.0

        # --- Signal Quality ---
        output.signal_quality = self._compute_quality(features, output)

        # --- Signal Codes ---
        codes = self._determine_signal_codes(features, output)
        output.signal_codes = codes
        output.signal_code = codes[0] if codes else "SEC_NEUTRAL"

        return output

    def _compute_quality(self, f: SectorFeatures, o: SectorOutput) -> int:
        """
        Quality assessment:
        4 = HIGH: rank consistent, breadth confirms, momentum aligns
        3 = MEDIUM: rank clear but one metric diverges
        2 = LOW: sector in middle, or mixed signals
        1 = TRANSITIONAL: rank changed 3+ recently
        0 = no data / singleton
        """
        if f.is_singleton:
            return 0

        num_sectors = f.num_sectors
        if num_sectors == 0:
            return 0

        rotation_threshold = self.cfg["periods"]["rotation_threshold"]
        rank = f.sector_rank_20d

        # Transitional: big rank change
        if abs(f.sector_rank_change_10d) >= rotation_threshold:
            return 1

        # Count confirming signals
        confirms = 0
        total_checks = 0

        # Check if rank is clearly top or bottom
        is_clear_rank = rank <= 3 or rank >= num_sectors - 2
        if is_clear_rank:
            confirms += 1
        total_checks += 1

        # Check if breadth confirms direction
        if o.sector_strength_sub > 0 and f.sector_pct_above_sma50 > 50:
            confirms += 1
        elif o.sector_strength_sub < 0 and f.sector_pct_above_sma50 < 50:
            confirms += 1
        elif o.sector_strength_sub == 0:
            confirms += 1
        total_checks += 1

        # Check if momentum confirms
        if o.sector_strength_sub > 0 and f.sector_momentum > 0:
            confirms += 1
        elif o.sector_strength_sub < 0 and f.sector_momentum < 0:
            confirms += 1
        elif o.sector_strength_sub == 0:
            confirms += 1
        total_checks += 1

        if confirms == total_checks and is_clear_rank:
            return 4
        elif confirms >= total_checks - 1 and is_clear_rank:
            return 3
        elif confirms >= total_checks - 1:
            return 2
        else:
            return 2

    def _determine_signal_codes(
        self, f: SectorFeatures, o: SectorOutput
    ) -> list[str]:
        """Determine all applicable signal codes."""
        codes = []
        rank = f.sector_rank_20d
        num_sectors = f.num_sectors
        rotation_threshold = self.cfg["periods"]["rotation_threshold"]

        # Primary sector signal
        if rank == 1:
            codes.append("SEC_TOP_SECTOR")
        elif rank <= 3:
            codes.append("SEC_STRONG_SECTOR")
        elif rank >= num_sectors and num_sectors > 0:
            codes.append("SEC_WORST_SECTOR")
        elif rank >= num_sectors - 2 and num_sectors > 0:
            codes.append("SEC_WEAK_SECTOR")

        # Momentum / acceleration
        if f.sector_momentum > 0 and rank <= num_sectors / 2:
            codes.append("SEC_SECTOR_ACCEL")
        elif f.sector_momentum < 0:
            codes.append("SEC_SECTOR_DECEL")

        # Rotation
        if f.sector_rank_change_10d >= rotation_threshold:
            codes.append("SEC_ROTATION_IN")
        elif f.sector_rank_change_10d <= -rotation_threshold:
            codes.append("SEC_ROTATION_OUT")

        # Stock within sector
        if f.is_sector_leader:
            codes.append("SEC_LEADER_IN_SECTOR")
        if f.is_sector_laggard:
            codes.append("SEC_LAGGARD_IN_SECTOR")

        if not codes:
            codes.append("SEC_NEUTRAL")

        return codes
