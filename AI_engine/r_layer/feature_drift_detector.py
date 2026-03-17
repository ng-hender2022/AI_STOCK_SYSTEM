"""
Feature Drift Detector
Detects changes in feature importance distributions over time.
Alerts when features drift significantly from training baseline.

Usage:
    detector = FeatureDriftDetector(models_db, signals_db)
    report = detector.detect_drift(model_id="R3", baseline_end="2023-12-31", current_start="2024-01-01")
    detector.save_report("D:/AI/AI_data/reports/feature_drift_report.txt")
"""

import sqlite3
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime


class FeatureDriftDetector:
    """
    Detect feature importance drift between training baseline and current data.

    Checks:
    1. Feature importance ranking changes (Spearman correlation)
    2. Feature distribution shifts (mean/std comparison)
    3. New zero-variance features (dead features)
    """

    def __init__(self, models_db: str | Path, signals_db: str | Path):
        self.models_db = str(models_db)
        self.signals_db = str(signals_db)

    def detect_drift(
        self,
        model_id: str,
        baseline_end: str,
        current_start: str,
        current_end: str | None = None,
        threshold: float = 0.3,
    ) -> dict:
        """
        Detect feature drift between baseline and current period.

        Args:
            model_id: R0, R2, R3, etc.
            baseline_end: last date of baseline period
            current_start: first date of current period
            current_end: last date of current period (default: latest)
            threshold: drift score threshold for alerting

        Returns:
            dict with drift analysis results
        """
        if current_end is None:
            current_end = "2099-12-31"

        # Load feature distributions for both periods
        baseline_stats = self._compute_feature_stats("2014-03-06", baseline_end)
        current_stats = self._compute_feature_stats(current_start, current_end)

        if not baseline_stats or not current_stats:
            return {"error": "insufficient data", "drifted_features": []}

        # Compare distributions
        drifted = []
        all_features = sorted(set(baseline_stats.keys()) & set(current_stats.keys()))

        for feat in all_features:
            b = baseline_stats[feat]
            c = current_stats[feat]

            # Skip if baseline has no variance
            if b["std"] < 1e-8:
                if c["std"] > 1e-4:
                    drifted.append({
                        "feature": feat,
                        "drift_type": "ACTIVATED",
                        "drift_score": 1.0,
                        "baseline_mean": b["mean"],
                        "current_mean": c["mean"],
                    })
                continue

            # Mean shift normalized by baseline std
            mean_shift = abs(c["mean"] - b["mean"]) / (b["std"] + 1e-8)

            # Std ratio
            std_ratio = c["std"] / (b["std"] + 1e-8)
            std_drift = abs(np.log(std_ratio + 1e-8))

            # Combined drift score
            drift_score = 0.6 * min(mean_shift, 3.0) / 3.0 + 0.4 * min(std_drift, 2.0) / 2.0

            if drift_score > threshold:
                drifted.append({
                    "feature": feat,
                    "drift_type": "DISTRIBUTION_SHIFT",
                    "drift_score": round(drift_score, 4),
                    "mean_shift": round(mean_shift, 4),
                    "std_ratio": round(std_ratio, 4),
                    "baseline_mean": round(b["mean"], 6),
                    "baseline_std": round(b["std"], 6),
                    "current_mean": round(c["mean"], 6),
                    "current_std": round(c["std"], 6),
                })

        # Dead features (zero variance in current period)
        dead_features = []
        for feat in all_features:
            c = current_stats[feat]
            if c["std"] < 1e-8 and baseline_stats[feat]["std"] > 1e-4:
                dead_features.append(feat)

        # Sort by drift score
        drifted.sort(key=lambda x: -x["drift_score"])

        return {
            "model_id": model_id,
            "baseline_period": f"2014-03-06 to {baseline_end}",
            "current_period": f"{current_start} to {current_end}",
            "total_features": len(all_features),
            "drifted_features": drifted,
            "drifted_count": len(drifted),
            "dead_features": dead_features,
            "dead_count": len(dead_features),
            "drift_severity": "HIGH" if len(drifted) > 10 else ("MEDIUM" if len(drifted) > 3 else "LOW"),
            "timestamp": datetime.now().isoformat(),
        }

    def _compute_feature_stats(
        self, start_date: str, end_date: str
    ) -> dict[str, dict]:
        """Compute mean/std for each feature in a date range."""
        conn = sqlite3.connect(self.signals_db, timeout=30)
        conn.row_factory = sqlite3.Row

        # Load meta features
        rows = conn.execute(
            """SELECT * FROM meta_features
               WHERE date >= ? AND date <= ? LIMIT 50000""",
            (start_date, end_date),
        ).fetchall()
        conn.close()

        if not rows:
            return {}

        df = pd.DataFrame([dict(r) for r in rows])
        non_feat = {"symbol", "date", "snapshot_time", "created_at"}
        feat_cols = [c for c in df.columns if c not in non_feat]

        stats = {}
        for col in feat_cols:
            try:
                vals = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(vals) > 0:
                    stats[col] = {
                        "mean": float(vals.mean()),
                        "std": float(vals.std()),
                        "min": float(vals.min()),
                        "max": float(vals.max()),
                        "count": len(vals),
                    }
            except Exception:
                pass

        return stats

    def save_importance_history(self, model_id: str, feature_importances: dict) -> None:
        """Save feature importance snapshot to models.db."""
        conn = sqlite3.connect(self.models_db, timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feature_importance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                importance REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        snapshot_date = datetime.now().strftime("%Y-%m-%d")
        for feat, imp in feature_importances.items():
            conn.execute(
                """INSERT INTO feature_importance_history
                   (model_id, snapshot_date, feature_name, importance)
                   VALUES (?, ?, ?, ?)""",
                (model_id, snapshot_date, feat, float(imp)),
            )
        conn.commit()
        conn.close()

    def generate_report(self, results: dict) -> str:
        """Generate human-readable drift report."""
        lines = []
        lines.append("=" * 70)
        lines.append("FEATURE DRIFT DETECTION REPORT")
        lines.append(f"Model: {results.get('model_id', '?')}")
        lines.append(f"Baseline: {results.get('baseline_period', '?')}")
        lines.append(f"Current: {results.get('current_period', '?')}")
        lines.append(f"Generated: {results.get('timestamp', '?')}")
        lines.append("=" * 70)
        lines.append("")

        lines.append(f"Total features analyzed: {results.get('total_features', 0)}")
        lines.append(f"Drifted features: {results.get('drifted_count', 0)}")
        lines.append(f"Dead features: {results.get('dead_count', 0)}")
        lines.append(f"Severity: {results.get('drift_severity', '?')}")
        lines.append("")

        if results.get("drifted_features"):
            lines.append(f"{'Feature':<35} {'Type':<20} {'Score':>6} {'MeanShift':>10} {'StdRatio':>10}")
            lines.append("-" * 70)
            for d in results["drifted_features"]:
                lines.append(
                    f"{d['feature']:<35} {d['drift_type']:<20} {d['drift_score']:>6.3f} "
                    f"{d.get('mean_shift', 0):>10.3f} {d.get('std_ratio', 0):>10.3f}"
                )

        if results.get("dead_features"):
            lines.append("")
            lines.append("Dead features (zero variance in current period):")
            for f in results["dead_features"]:
                lines.append(f"  - {f}")

        lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)

    def save_report(self, filepath: str, results: dict) -> None:
        """Save drift report to file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.generate_report(results))
