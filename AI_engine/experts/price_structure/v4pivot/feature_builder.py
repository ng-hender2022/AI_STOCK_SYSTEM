"""
V4PIVOT Feature Builder
Computes standard pivot points (P, R1, R2, S1, S2) across daily, weekly,
and monthly timeframes.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
  - Daily pivot uses yesterday's HLC.
  - Weekly pivot uses last completed week's HLC.
  - Monthly pivot uses last completed month's HLC.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _compute_pivot_levels(h: float, l: float, c: float) -> dict:
    """Compute standard pivot point and support/resistance levels."""
    p = (h + l + c) / 3.0
    r1 = 2.0 * p - l
    r2 = p + (h - l)
    s1 = 2.0 * p - h
    s2 = p - (h - l)
    return {"P": p, "R1": r1, "R2": r2, "S1": s1, "S2": s2}


@dataclass
class PivotFeatures:
    """All Pivot Point features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    close: float = 0.0

    # --- Daily pivot levels (from T-1 HLC) ---
    pivot: float = 0.0
    r1: float = 0.0
    r2: float = 0.0
    s1: float = 0.0
    s2: float = 0.0

    # --- Previous daily pivot (T-2) for alignment ---
    prev_pivot: float = 0.0

    # --- Weekly pivot levels ---
    weekly_pivot: float = 0.0
    weekly_r1: float = 0.0
    weekly_s1: float = 0.0
    prev_weekly_pivot: float = 0.0

    # --- Monthly pivot levels ---
    monthly_pivot: float = 0.0
    monthly_r1: float = 0.0
    monthly_s1: float = 0.0
    prev_monthly_pivot: float = 0.0

    has_sufficient_data: bool = False


class PivotFeatureBuilder:
    """
    Build Pivot Point features from market.db.

    Usage:
        builder = PivotFeatureBuilder(db_path)
        features = builder.build("FPT", "2026-03-16")
        batch = builder.build_batch(["FPT", "VNM"], "2026-03-16")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_history(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, lookback: int
    ) -> list[dict]:
        rows = conn.execute(
            "SELECT date, open, high, low, close FROM prices_daily "
            "WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def _find_last_completed_week_hlc(
        self, hist: list[dict], target_date_str: str
    ) -> tuple[float, float, float, float, float, float] | None:
        """Find last completed week's H, L, C and the week before that.

        Returns (h, l, c, prev_h, prev_l, prev_c) or None.
        A completed week = Mon-Fri where the target_date is after that Friday.
        """
        target = date.fromisoformat(target_date_str)

        # Group bars by ISO week
        weeks: dict[tuple[int, int], list[dict]] = {}
        for bar in hist:
            d = date.fromisoformat(bar["date"])
            key = d.isocalendar()[:2]  # (year, week)
            weeks.setdefault(key, []).append(bar)

        # Sort weeks and filter completed ones (all bars before target_date)
        sorted_keys = sorted(weeks.keys())
        completed = []
        for key in sorted_keys:
            bars = weeks[key]
            # A week is completed if all its trading days are before target_date
            last_bar_date = date.fromisoformat(max(b["date"] for b in bars))
            # Week is completed if the last trading day in the week + at least
            # the next day is <= target_date (i.e., we are past that week)
            if last_bar_date < target:
                # Also check that the week has ended (Saturday/Sunday passed)
                # The week ends on Friday (weekday=4). If last bar is Friday
                # or the next Monday is <= target, the week is complete.
                days_to_end_of_week = 4 - last_bar_date.weekday()
                if days_to_end_of_week <= 0 or (last_bar_date + timedelta(days=max(1, days_to_end_of_week + 1))) <= target:
                    completed.append(key)

        if not completed:
            return None

        last_week_key = completed[-1]
        last_week_bars = weeks[last_week_key]
        h = max(b["high"] for b in last_week_bars)
        l = min(b["low"] for b in last_week_bars)
        c = last_week_bars[-1]["close"]  # bars are in chronological order within hist

        # Sort bars by date to ensure correct close
        last_week_bars_sorted = sorted(last_week_bars, key=lambda b: b["date"])
        c = last_week_bars_sorted[-1]["close"]

        # Previous week
        prev_h, prev_l, prev_c = 0.0, 0.0, 0.0
        if len(completed) >= 2:
            prev_week_key = completed[-2]
            prev_bars = sorted(weeks[prev_week_key], key=lambda b: b["date"])
            prev_h = max(b["high"] for b in prev_bars)
            prev_l = min(b["low"] for b in prev_bars)
            prev_c = prev_bars[-1]["close"]

        return h, l, c, prev_h, prev_l, prev_c

    def _find_last_completed_month_hlc(
        self, hist: list[dict], target_date_str: str
    ) -> tuple[float, float, float, float, float, float] | None:
        """Find last completed month's H, L, C and the month before that.

        Returns (h, l, c, prev_h, prev_l, prev_c) or None.
        """
        target = date.fromisoformat(target_date_str)

        # Group bars by (year, month)
        months: dict[tuple[int, int], list[dict]] = {}
        for bar in hist:
            d = date.fromisoformat(bar["date"])
            key = (d.year, d.month)
            months.setdefault(key, []).append(bar)

        # A month is completed if target is in a later month
        completed = []
        for key in sorted(months.keys()):
            y, m = key
            if (y, m) < (target.year, target.month):
                completed.append(key)

        if not completed:
            return None

        last_month_key = completed[-1]
        last_month_bars = sorted(months[last_month_key], key=lambda b: b["date"])
        h = max(b["high"] for b in last_month_bars)
        l = min(b["low"] for b in last_month_bars)
        c = last_month_bars[-1]["close"]

        # Previous month
        prev_h, prev_l, prev_c = 0.0, 0.0, 0.0
        if len(completed) >= 2:
            prev_month_key = completed[-2]
            prev_bars = sorted(months[prev_month_key], key=lambda b: b["date"])
            prev_h = max(b["high"] for b in prev_bars)
            prev_l = min(b["low"] for b in prev_bars)
            prev_c = prev_bars[-1]["close"]

        return h, l, c, prev_h, prev_l, prev_c

    def build(self, symbol: str, target_date: str) -> PivotFeatures:
        """Build Pivot features. Uses only data < target_date."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (symbol, target_date),
            ).fetchone()

            if not row:
                return PivotFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

            cutoff = row["date"]
            min_hist = self.cfg["min_history_days"]
            # Fetch enough history for monthly pivot computation
            hist = self._fetch_history(conn, symbol, cutoff, lookback=min_hist + 60)

            feat = PivotFeatures(symbol=symbol, date=target_date, data_cutoff_date=cutoff)
            if len(hist) < min_hist:
                return feat

            self._compute(feat, hist, target_date)
            feat.has_sufficient_data = True
            return feat
        finally:
            conn.close()

    def build_batch(self, symbols: list[str], target_date: str) -> list[PivotFeatures]:
        conn = self._connect()
        results = []
        try:
            for sym in symbols:
                row = conn.execute(
                    "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                    (sym, target_date),
                ).fetchone()
                if not row:
                    results.append(PivotFeatures(symbol=sym, date=target_date, data_cutoff_date=""))
                    continue

                cutoff = row["date"]
                min_hist = self.cfg["min_history_days"]
                hist = self._fetch_history(conn, sym, cutoff, lookback=min_hist + 60)
                feat = PivotFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)
                if len(hist) >= min_hist:
                    self._compute(feat, hist, target_date)
                    feat.has_sufficient_data = True
                results.append(feat)
        finally:
            conn.close()
        return results

    def _compute(self, feat: PivotFeatures, hist: list[dict], target_date: str) -> None:
        n = len(hist)

        # Close is the last available bar (T-1)
        feat.close = float(hist[-1]["close"])

        # --- Daily pivot from T-1 HLC ---
        last_bar = hist[-1]
        daily = _compute_pivot_levels(
            float(last_bar["high"]), float(last_bar["low"]), float(last_bar["close"])
        )
        feat.pivot = daily["P"]
        feat.r1 = daily["R1"]
        feat.r2 = daily["R2"]
        feat.s1 = daily["S1"]
        feat.s2 = daily["S2"]

        # --- Previous daily pivot (T-2 HLC) for alignment ---
        if n >= 2:
            prev_bar = hist[-2]
            prev_daily = _compute_pivot_levels(
                float(prev_bar["high"]), float(prev_bar["low"]), float(prev_bar["close"])
            )
            feat.prev_pivot = prev_daily["P"]

        # --- Weekly pivot ---
        weekly_result = self._find_last_completed_week_hlc(hist, target_date)
        if weekly_result:
            wh, wl, wc, pwh, pwl, pwc = weekly_result
            weekly = _compute_pivot_levels(wh, wl, wc)
            feat.weekly_pivot = weekly["P"]
            feat.weekly_r1 = weekly["R1"]
            feat.weekly_s1 = weekly["S1"]
            if pwh > 0:
                prev_weekly = _compute_pivot_levels(pwh, pwl, pwc)
                feat.prev_weekly_pivot = prev_weekly["P"]

        # --- Monthly pivot ---
        monthly_result = self._find_last_completed_month_hlc(hist, target_date)
        if monthly_result:
            mh, ml, mc, pmh, pml, pmc = monthly_result
            monthly = _compute_pivot_levels(mh, ml, mc)
            feat.monthly_pivot = monthly["P"]
            feat.monthly_r1 = monthly["R1"]
            feat.monthly_s1 = monthly["S1"]
            if pmh > 0:
                prev_monthly = _compute_pivot_levels(pmh, pml, pmc)
                feat.prev_monthly_pivot = prev_monthly["P"]
