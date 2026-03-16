"""
R Layer Ensemble Engine
Combines R0-R5 predictions into final ensemble score.
"""

import sqlite3
from pathlib import Path


class EnsembleEngine:
    """
    Combine 6 R model predictions into ensemble score.

    ensemble_score = weighted_average(r0..r5)
    ensemble_confidence = 1 - std(r0..r5) / 4
    ensemble_direction = +1 if score > threshold, -1 if < -threshold, 0 otherwise

    Usage:
        engine = EnsembleEngine(models_db)
        engine.compute_ensemble("2014-07-29")
    """

    DEFAULT_WEIGHTS = {
        "r0": 0.10,  # baseline gets less weight
        "r1": 0.15,
        "r2": 0.20,
        "r3": 0.25,  # GBDT gets most weight
        "r4": 0.15,
        "r5": 0.15,
    }

    DIRECTION_THRESHOLD = 0.5

    def __init__(self, models_db: str | Path, weights: dict | None = None):
        self.models_db = str(models_db)
        self.weights = weights or self.DEFAULT_WEIGHTS

    def compute_ensemble(self, date: str) -> dict:
        """
        Compute ensemble for all symbols on a date.
        Reads individual R scores from r_predictions, writes ensemble columns.
        """
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM r_predictions WHERE date=? AND snapshot_time='EOD'",
            (date,),
        ).fetchall()

        if not rows:
            conn.close()
            return {"date": date, "symbols": 0}

        import numpy as np

        updated = 0
        for row in rows:
            scores = {}
            for rid in ["r0", "r1", "r2", "r3", "r4", "r5"]:
                col = f"{rid}_score"
                val = row[col] if col in row.keys() else None
                if val is not None:
                    scores[rid] = float(val)

            if not scores:
                continue

            # Weighted average (only use available scores)
            total_weight = sum(self.weights.get(k, 0) for k in scores)
            if total_weight == 0:
                continue

            ensemble = sum(scores[k] * self.weights.get(k, 0) for k in scores) / total_weight
            ensemble = max(-4.0, min(4.0, ensemble))

            # Confidence = 1 - normalized std
            vals = list(scores.values())
            std = float(np.std(vals)) if len(vals) > 1 else 0.0
            confidence = max(0.0, min(1.0, 1 - std / 4))

            # Direction
            if ensemble > self.DIRECTION_THRESHOLD:
                direction = 1
            elif ensemble < -self.DIRECTION_THRESHOLD:
                direction = -1
            else:
                direction = 0

            conn.execute(
                """UPDATE r_predictions
                   SET ensemble_score=?, ensemble_confidence=?, ensemble_direction=?
                   WHERE symbol=? AND date=? AND snapshot_time='EOD'""",
                (round(ensemble, 4), round(confidence, 4), direction,
                 row["symbol"], date),
            )
            updated += 1

        conn.commit()
        conn.close()
        return {"date": date, "symbols": updated}
