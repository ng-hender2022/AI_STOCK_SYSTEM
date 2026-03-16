"""
V4RS Feature Builder
Computes RS ratios (stock vs VNINDEX), RS_Line, RS trend, and cross-universe
percentile ranks for all 91 stocks.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sma(data: np.ndarray, period: int) -> np.ndarray:
    """Compute SMA. Returns array same length as data (NaN-padded)."""
    result = np.full_like(data, np.nan, dtype=float)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result


def _pct_return(prices: np.ndarray, period: int) -> float:
    """Compute period return from the last `period` prices.
    Returns NaN if insufficient data."""
    if len(prices) < period + 1:
        return float("nan")
    p_end = prices[-1]
    p_start = prices[-(period + 1)]
    if abs(p_start) < 1e-9:
        return float("nan")
    return (p_end - p_start) / p_start


def _linreg_slope(data: np.ndarray, period: int) -> float:
    """Linear regression slope of last `period` values, standardized by mean."""
    if len(data) < period:
        return float("nan")
    segment = data[-period:]
    if np.any(np.isnan(segment)):
        return float("nan")
    x = np.arange(period, dtype=float)
    mean_y = np.mean(segment)
    if abs(mean_y) < 1e-9:
        return 0.0
    # slope = cov(x,y) / var(x)
    slope = np.polyfit(x, segment, 1)[0]
    return float(slope / mean_y)


@dataclass
class RSFeatures:
    """All RS features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str

    # RS ratios (stock_return / vnindex_return)
    rs_5d: float = float("nan")
    rs_20d: float = float("nan")
    rs_60d: float = float("nan")

    # Absolute returns (for edge case: vnindex flat)
    stock_ret_5d: float = float("nan")
    stock_ret_20d: float = float("nan")
    stock_ret_60d: float = float("nan")

    # RS rank among universe (percentile 0-100, 100=best)
    rs_rank_20d: float = float("nan")

    # Decile (1=top 10%, 10=bottom 10%)
    rs_decile: int = 5

    # RS trend
    rs_trend: str = "FLAT"   # RISING / FLAT / FALLING

    # RS rank change over 10 days
    rs_rank_change_10d: float = 0.0

    # RS slope and acceleration
    rs_slope: float = 0.0
    rs_acceleration: float = 0.0

    # Whether all 3 RS periods agree in direction (>1 or <1)
    all_periods_agree: bool = False
    all_periods_direction: int = 0  # +1 if all outperform, -1 if all underperform, 0 mixed

    # VNINDEX flat flag
    vnindex_flat: bool = False

    has_sufficient_data: bool = False


class RSFeatureBuilder:
    """
    Build RS features from market.db.
    Requires VNINDEX data + all universe stocks for ranking.

    Usage:
        builder = RSFeatureBuilder(db_path)
        features = builder.build("FPT", "2026-03-16", universe=["FPT","VNM",...])
        batch = builder.build_batch(["FPT","VNM"], "2026-03-16")
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.cfg = _load_config()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_closes(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, lookback: int
    ) -> list[dict]:
        """Fetch date+close up to cutoff_date, most recent `lookback` rows."""
        rows = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, lookback),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def build_batch(
        self, symbols: list[str], target_date: str
    ) -> list[RSFeatures]:
        """Build RS features for all symbols. Computes cross-universe rank internally."""
        conn = self._connect()
        try:
            benchmark = self.cfg["benchmark"]
            min_hist = self.cfg["min_history_days"]
            lookback = min_hist + 40  # extra buffer for SMA30 + rank change

            # Find cutoff date
            row = conn.execute(
                "SELECT date FROM prices_daily WHERE symbol=? AND date<? ORDER BY date DESC LIMIT 1",
                (benchmark, target_date),
            ).fetchone()
            if not row:
                return [RSFeatures(symbol=s, date=target_date, data_cutoff_date="") for s in symbols]
            cutoff = row["date"]

            # Fetch benchmark data
            bench_hist = self._fetch_closes(conn, benchmark, cutoff, lookback)
            if len(bench_hist) < min_hist:
                return [RSFeatures(symbol=s, date=target_date, data_cutoff_date=cutoff) for s in symbols]
            bench_closes = np.array([d["close"] for d in bench_hist], dtype=float)

            # Compute benchmark returns
            bench_ret_5d = _pct_return(bench_closes, 5)
            bench_ret_20d = _pct_return(bench_closes, 20)
            bench_ret_60d = _pct_return(bench_closes, 60)

            flat_threshold = self.cfg["vnindex_flat_threshold"]
            vnindex_flat_5d = abs(bench_ret_5d) < flat_threshold if not np.isnan(bench_ret_5d) else True
            vnindex_flat_20d = abs(bench_ret_20d) < flat_threshold if not np.isnan(bench_ret_20d) else True
            vnindex_flat_60d = abs(bench_ret_60d) < flat_threshold if not np.isnan(bench_ret_60d) else True

            # Fetch all symbols' data and compute returns
            all_symbols_data = {}
            for sym in symbols:
                if sym == benchmark:
                    continue
                hist = self._fetch_closes(conn, sym, cutoff, lookback)
                if len(hist) < min_hist:
                    all_symbols_data[sym] = None
                    continue
                closes = np.array([d["close"] for d in hist], dtype=float)
                dates = [d["date"] for d in hist]

                ret_5d = _pct_return(closes, 5)
                ret_20d = _pct_return(closes, 20)
                ret_60d = _pct_return(closes, 60)

                all_symbols_data[sym] = {
                    "closes": closes,
                    "dates": dates,
                    "ret_5d": ret_5d,
                    "ret_20d": ret_20d,
                    "ret_60d": ret_60d,
                }

            # Compute 20d return rank across all symbols with valid data
            valid_symbols_20d = {}
            for sym, data in all_symbols_data.items():
                if data is not None and not np.isnan(data["ret_20d"]):
                    if vnindex_flat_20d:
                        # Use absolute return for ranking when VNINDEX is flat
                        valid_symbols_20d[sym] = data["ret_20d"]
                    else:
                        valid_symbols_20d[sym] = data["ret_20d"] / bench_ret_20d if bench_ret_20d != 0 else data["ret_20d"]

            # Sort by value to get rank (higher = better)
            if valid_symbols_20d:
                sorted_syms = sorted(valid_symbols_20d.keys(), key=lambda s: valid_symbols_20d[s])
                n_valid = len(sorted_syms)
                rank_map = {}
                for idx, sym in enumerate(sorted_syms):
                    rank_map[sym] = (idx / max(n_valid - 1, 1)) * 100.0  # percentile 0-100
            else:
                rank_map = {}

            # Compute rank 10 days ago for rank change
            rank_map_10d_ago = self._compute_rank_at_offset(
                conn, all_symbols_data, bench_closes, cutoff, 10, flat_threshold
            )

            # Build features for each symbol
            results = []
            for sym in symbols:
                feat = RSFeatures(symbol=sym, date=target_date, data_cutoff_date=cutoff)

                if sym == benchmark:
                    # Benchmark itself: neutral RS
                    feat.rs_5d = 1.0
                    feat.rs_20d = 1.0
                    feat.rs_60d = 1.0
                    feat.rs_rank_20d = 50.0
                    feat.rs_decile = 5
                    feat.rs_trend = "FLAT"
                    feat.has_sufficient_data = True
                    results.append(feat)
                    continue

                data = all_symbols_data.get(sym)
                if data is None:
                    results.append(feat)
                    continue

                feat.has_sufficient_data = True

                # RS ratios
                feat.stock_ret_5d = float(data["ret_5d"])
                feat.stock_ret_20d = float(data["ret_20d"])
                feat.stock_ret_60d = float(data["ret_60d"])

                vnindex_flat_any = vnindex_flat_5d or vnindex_flat_20d or vnindex_flat_60d
                feat.vnindex_flat = bool(vnindex_flat_any)

                if not vnindex_flat_5d and not np.isnan(bench_ret_5d) and abs(bench_ret_5d) > 1e-9:
                    feat.rs_5d = float(data["ret_5d"] / bench_ret_5d) if not np.isnan(data["ret_5d"]) else float("nan")
                else:
                    feat.rs_5d = float(data["ret_5d"]) if not np.isnan(data["ret_5d"]) else float("nan")

                if not vnindex_flat_20d and not np.isnan(bench_ret_20d) and abs(bench_ret_20d) > 1e-9:
                    feat.rs_20d = float(data["ret_20d"] / bench_ret_20d) if not np.isnan(data["ret_20d"]) else float("nan")
                else:
                    feat.rs_20d = float(data["ret_20d"]) if not np.isnan(data["ret_20d"]) else float("nan")

                if not vnindex_flat_60d and not np.isnan(bench_ret_60d) and abs(bench_ret_60d) > 1e-9:
                    feat.rs_60d = float(data["ret_60d"] / bench_ret_60d) if not np.isnan(data["ret_60d"]) else float("nan")
                else:
                    feat.rs_60d = float(data["ret_60d"]) if not np.isnan(data["ret_60d"]) else float("nan")

                # Rank
                feat.rs_rank_20d = float(rank_map.get(sym, 50.0))

                # Decile (1=top, 10=bottom)
                feat.rs_decile = self._rank_to_decile(feat.rs_rank_20d)

                # RS Line (cumulative ratio) and trend
                closes = data["closes"]
                # Use min(len(closes), len(bench_closes)) aligned from the end
                min_len = min(len(closes), len(bench_closes))
                stock_tail = closes[-min_len:]
                bench_tail = bench_closes[-min_len:]
                rs_line = stock_tail / (bench_tail + 1e-12)
                # Normalize to 100 at start
                rs_line = rs_line / (rs_line[0] + 1e-12) * 100.0

                sma_short = self.cfg["rs_sma_short"]
                sma_long = self.cfg["rs_sma_long"]

                sma10_arr = _sma(rs_line, sma_short)
                sma30_arr = _sma(rs_line, sma_long)

                feat.rs_trend = self._compute_trend(sma10_arr, sma30_arr)

                # RS slope
                slope_period = self.cfg["slope_period"]
                feat.rs_slope = _linreg_slope(rs_line, slope_period)

                # RS acceleration
                accel_period = self.cfg["accel_period"]
                if len(rs_line) >= slope_period + accel_period:
                    slope_now = _linreg_slope(rs_line, slope_period)
                    slope_prev = _linreg_slope(rs_line[:-accel_period], slope_period)
                    if not np.isnan(slope_now) and not np.isnan(slope_prev):
                        feat.rs_acceleration = float(slope_now - slope_prev)

                # Rank change over 10 days
                rank_10d_ago = rank_map_10d_ago.get(sym, feat.rs_rank_20d)
                feat.rs_rank_change_10d = float(feat.rs_rank_20d - rank_10d_ago)

                # All periods agree
                rs_vals = [feat.rs_5d, feat.rs_20d, feat.rs_60d]
                valid_rs = [v for v in rs_vals if not np.isnan(v)]
                if len(valid_rs) == 3:
                    if all(v > 1.0 for v in valid_rs) or (vnindex_flat_any and all(v > 0 for v in valid_rs)):
                        feat.all_periods_agree = True
                        feat.all_periods_direction = 1
                    elif all(v < 1.0 for v in valid_rs) or (vnindex_flat_any and all(v < 0 for v in valid_rs)):
                        feat.all_periods_agree = True
                        feat.all_periods_direction = -1

                results.append(feat)

            return results

        finally:
            conn.close()

    def build(
        self, symbol: str, target_date: str, universe: list[str] | None = None
    ) -> RSFeatures:
        """Build RS features for a single symbol. Needs full universe for ranking."""
        if universe is None:
            universe = [symbol]
        if symbol not in universe:
            universe = [symbol] + universe
        batch = self.build_batch(universe, target_date)
        for feat in batch:
            if feat.symbol == symbol:
                return feat
        return RSFeatures(symbol=symbol, date=target_date, data_cutoff_date="")

    def _rank_to_decile(self, percentile: float) -> int:
        """Convert percentile (0=worst, 100=best) to decile (1=top, 10=bottom)."""
        if percentile >= 90:
            return 1
        elif percentile >= 80:
            return 2
        elif percentile >= 70:
            return 3
        elif percentile >= 60:
            return 4
        elif percentile >= 50:
            return 5
        elif percentile >= 40:
            return 6
        elif percentile >= 30:
            return 7
        elif percentile >= 20:
            return 8
        elif percentile >= 10:
            return 9
        else:
            return 10

    def _compute_trend(self, sma_short: np.ndarray, sma_long: np.ndarray) -> str:
        """Compute RS trend: RISING, FALLING, or FLAT.
        RISING: SMA10 > SMA30 and both slopes positive.
        FALLING: SMA10 < SMA30 and both slopes negative.
        FLAT: otherwise.
        """
        if len(sma_short) < 2 or len(sma_long) < 2:
            return "FLAT"
        last = len(sma_short) - 1
        if np.isnan(sma_short[last]) or np.isnan(sma_long[last]):
            return "FLAT"

        short_above = sma_short[last] > sma_long[last]
        short_below = sma_short[last] < sma_long[last]

        # Compute slopes (recent change)
        slope_window = min(5, last)
        if slope_window < 1:
            return "FLAT"

        short_slope = sma_short[last] - sma_short[last - slope_window]
        long_slope = sma_long[last] - sma_long[last - slope_window]

        # Handle NaN slopes
        if np.isnan(short_slope) or np.isnan(long_slope):
            return "FLAT"

        if short_above and short_slope > 0 and long_slope > 0:
            return "RISING"
        elif short_below and short_slope < 0 and long_slope < 0:
            return "FALLING"
        return "FLAT"

    def _compute_rank_at_offset(
        self,
        conn: sqlite3.Connection,
        all_symbols_data: dict,
        bench_closes: np.ndarray,
        cutoff: str,
        offset_days: int,
        flat_threshold: float,
    ) -> dict[str, float]:
        """Approximate rank map as of `offset_days` trading days ago.
        Uses already-fetched data shifted by offset."""
        if len(bench_closes) <= offset_days + 20:
            return {}

        bench_past = bench_closes[:-(offset_days)]
        bench_ret_20d_past = _pct_return(bench_past, 20)
        vnindex_flat = abs(bench_ret_20d_past) < flat_threshold if not np.isnan(bench_ret_20d_past) else True

        valid_returns = {}
        for sym, data in all_symbols_data.items():
            if data is None:
                continue
            closes = data["closes"]
            if len(closes) <= offset_days + 20:
                continue
            past_closes = closes[:-(offset_days)]
            ret = _pct_return(past_closes, 20)
            if np.isnan(ret):
                continue
            if vnindex_flat:
                valid_returns[sym] = ret
            else:
                valid_returns[sym] = ret / bench_ret_20d_past if bench_ret_20d_past != 0 else ret

        if not valid_returns:
            return {}

        sorted_syms = sorted(valid_returns.keys(), key=lambda s: valid_returns[s])
        n = len(sorted_syms)
        rank_map = {}
        for idx, sym in enumerate(sorted_syms):
            rank_map[sym] = (idx / max(n - 1, 1)) * 100.0
        return rank_map
