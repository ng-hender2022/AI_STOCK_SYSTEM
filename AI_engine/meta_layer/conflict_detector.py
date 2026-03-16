"""
Conflict Detector
Detects disagreements between experts.
Computes conflict score (0=aligned, 1=max conflict)
and alignment score (0=no alignment, 1=perfect).
"""

import numpy as np
from .meta_builder import EXPERT_GROUPS


class ConflictDetector:
    """
    Detect and measure expert conflicts.

    Usage:
        detector = ConflictDetector()
        conflict = detector.compute_conflict_score(norms)
        alignment = detector.compute_alignment_score(norms)
        pairs = detector.find_conflicting_pairs(norms)
    """

    def compute_conflict_score(self, norms: dict[str, float]) -> float:
        """
        Conflict score: 0 (all agree) to 1 (max disagreement).
        Based on standard deviation of normalized scores.
        """
        if len(norms) < 2:
            return 0.0
        values = list(norms.values())
        std = float(np.std(values))
        # Max possible std for values in [-1, 1] is 1.0
        return min(1.0, std)

    def compute_alignment_score(self, norms: dict[str, float]) -> float:
        """
        Alignment score: 0 (no alignment) to 1 (perfect agreement).
        Based on proportion of experts agreeing on direction.
        """
        if not norms:
            return 0.0

        bullish = sum(1 for v in norms.values() if v > 0.05)
        bearish = sum(1 for v in norms.values() if v < -0.05)
        total = len(norms)

        max_agree = max(bullish, bearish)
        return max_agree / total

    def find_conflicting_pairs(
        self, norms: dict[str, float], threshold: float = 0.5
    ) -> list[dict]:
        """
        Find pairs of experts that strongly disagree.
        Threshold: minimum absolute difference to flag as conflict.

        Returns list of {expert_a, expert_b, score_a, score_b, diff, type}
        """
        conflicts = []
        ids = sorted(norms.keys())

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                sa, sb = norms[a], norms[b]

                # Direction conflict: one bullish, one bearish
                if (sa > 0.05 and sb < -0.05) or (sa < -0.05 and sb > 0.05):
                    diff = abs(sa - sb)
                    if diff >= threshold:
                        conflicts.append({
                            "expert_a": a,
                            "expert_b": b,
                            "score_a": round(sa, 4),
                            "score_b": round(sb, 4),
                            "diff": round(diff, 4),
                            "type": "DIRECTION",
                        })

        return conflicts

    def find_group_conflicts(self, norms: dict[str, float]) -> list[dict]:
        """
        Find conflicts between expert groups.
        E.g., TREND group bullish but MOMENTUM group bearish.
        """
        group_avgs = {}
        for group_name, group_ids in EXPERT_GROUPS.items():
            values = [norms[eid] for eid in group_ids if eid in norms]
            if values:
                group_avgs[group_name] = sum(values) / len(values)

        conflicts = []
        groups = sorted(group_avgs.keys())
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                ga, gb = groups[i], groups[j]
                sa, sb = group_avgs[ga], group_avgs[gb]
                if (sa > 0.1 and sb < -0.1) or (sa < -0.1 and sb > 0.1):
                    conflicts.append({
                        "group_a": ga,
                        "group_b": gb,
                        "score_a": round(sa, 4),
                        "score_b": round(sb, 4),
                        "type": "GROUP_DIRECTION",
                    })

        return conflicts
