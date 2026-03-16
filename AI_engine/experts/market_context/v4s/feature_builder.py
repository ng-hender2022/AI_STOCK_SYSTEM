"""
V4S Feature Builder
Computes sector-level metrics and per-stock sector features.

DATA LEAKAGE RULE: Day T only uses data up to close of T-1.
"""

import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
MASTER_UNIVERSE_PATH = Path(r"D:\AI\AI_brain\SYSTEM\MASTER_UNIVERSE.md")


def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_universe() -> list[str]:
    """Load sorted A-Z symbol list from MASTER_UNIVERSE.md."""
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## DANH SACH DAY DU.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"## DANH S.*?```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Cannot parse universe from {MASTER_UNIVERSE_PATH}")
    raw = match.group(1)
    return [s.strip() for s in raw.replace("\n", ",").split(",") if s.strip()]


def load_sector_mapping() -> dict[str, str]:
    """Load Symbol -> Sector mapping table from MASTER_UNIVERSE.md."""
    text = MASTER_UNIVERSE_PATH.read_text(encoding="utf-8")
    match = re.search(r"## SYMBOL .* SECTOR MAPPING.*?\n\|.*?\n\|.*?\n(.*?)(\n---|\n##|\Z)",
                      text, re.DOTALL | re.IGNORECASE)
    if not match:
        # Fallback: find the table after "SYMBOL → SECTOR MAPPING" or similar
        match = re.search(r"SYMBOL.*SECTOR.*MAPPING.*?\n\|.*?\n\|.*?\n(.*?)(\n---|\n##|\Z)",
                          text, re.DOTALL | re.IGNORECASE)
    if not match:
        raise RuntimeError(f"Cannot parse sector mapping from {MASTER_UNIVERSE_PATH}")

    mapping = {}
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # parts: ['', 'SYMBOL', 'SECTOR', ''] typically
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            sym = parts[0].strip()
            sector = parts[1].strip()
            if sym and sector and sym != "Symbol" and sector != "Sector":
                mapping[sym] = sector
    return mapping


@dataclass
class SectorMetrics:
    """Sector-level metrics for a given date."""
    sector_name: str
    sector_return_5d: float = 0.0
    sector_return_20d: float = 0.0
    sector_vs_market_20d: float = 0.0
    sector_rank_20d: int = 0       # 1 = best
    sector_pct_above_sma50: float = 0.0
    sector_momentum: float = 0.0   # return_5d - return_20d
    sector_rank_change_10d: int = 0
    num_stocks: int = 0
    is_singleton: bool = False


@dataclass
class SectorFeatures:
    """All sector features for 1 symbol, day T."""
    symbol: str
    date: str
    data_cutoff_date: str
    sector_name: str = ""

    # Sector-level
    sector_return_20d: float = 0.0
    sector_vs_market_20d: float = 0.0
    sector_rank_20d: int = 0
    sector_pct_above_sma50: float = 0.0
    sector_momentum: float = 0.0
    sector_rank_change_10d: int = 0
    sector_return_5d: float = 0.0
    num_sectors: int = 0
    num_stocks_in_sector: int = 0
    is_singleton: bool = False

    # Stock-within-sector
    stock_return_20d: float = 0.0
    stock_vs_sector_20d: float = 0.0
    stock_rank_in_sector: int = 0
    is_sector_leader: bool = False
    is_sector_laggard: bool = False

    has_sufficient_data: bool = False


class SectorFeatureBuilder:
    """
    Build sector features from market.db.

    Usage:
        builder = SectorFeatureBuilder(db_path)
        features = builder.build(symbol, target_date, sector_mapping)
        batch = builder.build_all(symbols, target_date, sector_mapping)
    """

    def __init__(self, db_path: str | Path, sector_mapping: dict[str, str] | None = None):
        self.db_path = str(db_path)
        self.cfg = _load_config()
        self.sector_mapping = sector_mapping or {}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_cutoff_date(self, conn: sqlite3.Connection, target_date: str) -> str | None:
        """Get the latest date strictly before target_date for any symbol."""
        row = conn.execute(
            "SELECT MAX(date) as d FROM prices_daily WHERE date < ?",
            (target_date,),
        ).fetchone()
        if row and row["d"]:
            return row["d"]
        return None

    def _fetch_returns(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, period: int
    ) -> float | None:
        """Compute return over `period` trading days ending at cutoff_date."""
        rows = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, period + 1),
        ).fetchall()
        if len(rows) < period + 1:
            return None
        close_now = rows[0]["close"]
        close_past = rows[period]["close"]
        if close_past == 0:
            return None
        return (close_now - close_past) / close_past

    def _is_above_sma(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str, sma_period: int
    ) -> bool | None:
        """Check if stock's close is above its SMA at cutoff_date."""
        rows = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol=? AND date<=? ORDER BY date DESC LIMIT ?",
            (symbol, cutoff_date, sma_period),
        ).fetchall()
        if len(rows) < sma_period:
            return None
        close_now = rows[0]["close"]
        sma = np.mean([r["close"] for r in rows])
        return close_now > sma

    def _count_history_days(
        self, conn: sqlite3.Connection, symbol: str, cutoff_date: str
    ) -> int:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM prices_daily WHERE symbol=? AND date<=?",
            (symbol, cutoff_date),
        ).fetchone()
        return row["cnt"] if row else 0

    def _compute_sector_metrics(
        self, conn: sqlite3.Connection, cutoff_date: str, sector_stocks: dict[str, list[str]],
        vnindex_return_20d: float | None
    ) -> dict[str, SectorMetrics]:
        """Compute metrics for all sectors."""
        cfg = self.cfg
        period_short = cfg["periods"]["return_short"]
        period_medium = cfg["periods"]["return_medium"]
        sma_period = cfg["periods"]["sma_breadth"]
        min_hist = cfg["min_history_days"]

        sector_metrics: dict[str, SectorMetrics] = {}

        for sector_name, stocks in sector_stocks.items():
            sm = SectorMetrics(sector_name=sector_name)
            returns_5d = []
            returns_20d = []
            above_sma50 = []

            valid_stocks = []
            for s in stocks:
                hist_count = self._count_history_days(conn, s, cutoff_date)
                if hist_count < min_hist:
                    continue
                valid_stocks.append(s)

            sm.num_stocks = len(valid_stocks)
            if sm.num_stocks == 0:
                sector_metrics[sector_name] = sm
                continue

            if sm.num_stocks == 1:
                sm.is_singleton = True
                sector_metrics[sector_name] = sm
                continue

            for s in valid_stocks:
                r5 = self._fetch_returns(conn, s, cutoff_date, period_short)
                r20 = self._fetch_returns(conn, s, cutoff_date, period_medium)
                above = self._is_above_sma(conn, s, cutoff_date, sma_period)
                if r5 is not None:
                    returns_5d.append(r5)
                if r20 is not None:
                    returns_20d.append(r20)
                if above is not None:
                    above_sma50.append(above)

            if returns_20d:
                sm.sector_return_20d = float(np.mean(returns_20d))
            if returns_5d:
                sm.sector_return_5d = float(np.mean(returns_5d))
            if above_sma50:
                sm.sector_pct_above_sma50 = float(np.sum(above_sma50) / len(above_sma50) * 100)

            sm.sector_momentum = sm.sector_return_5d - sm.sector_return_20d

            if vnindex_return_20d is not None:
                sm.sector_vs_market_20d = sm.sector_return_20d - vnindex_return_20d

            sector_metrics[sector_name] = sm

        # Rank sectors by 20d return (1 = best)
        ranked = sorted(
            [(name, m) for name, m in sector_metrics.items()
             if m.num_stocks >= 2],
            key=lambda x: x[1].sector_return_20d,
            reverse=True,
        )
        for rank_idx, (name, m) in enumerate(ranked, start=1):
            m.sector_rank_20d = rank_idx

        return sector_metrics

    def _compute_sector_rank_change(
        self, conn: sqlite3.Connection, target_date: str, cutoff_date: str,
        sector_stocks: dict[str, list[str]],
    ) -> dict[str, int]:
        """Compute rank change over last 10 trading days."""
        lookback = self.cfg["periods"]["rank_change_lookback"]
        period_medium = self.cfg["periods"]["return_medium"]
        min_hist = self.cfg["min_history_days"]

        # Find the date ~10 trading days ago
        rows = conn.execute(
            "SELECT DISTINCT date FROM prices_daily WHERE date<=? ORDER BY date DESC LIMIT ?",
            (cutoff_date, lookback + 1),
        ).fetchall()
        if len(rows) < lookback + 1:
            return {}
        past_date = rows[-1]["date"]

        # Compute sector returns at past_date
        past_returns: dict[str, float] = {}
        for sector_name, stocks in sector_stocks.items():
            rets = []
            for s in stocks:
                hist_count = self._count_history_days(conn, s, past_date)
                if hist_count < min_hist:
                    continue
                r = self._fetch_returns(conn, s, past_date, period_medium)
                if r is not None:
                    rets.append(r)
            if len(rets) >= 2:
                past_returns[sector_name] = float(np.mean(rets))

        # Rank past
        past_ranked = sorted(past_returns.items(), key=lambda x: x[1], reverse=True)
        past_rank = {name: i + 1 for i, (name, _) in enumerate(past_ranked)}

        return past_rank

    def build_all(
        self, symbols: list[str], target_date: str,
        sector_mapping: dict[str, str] | None = None,
    ) -> list[SectorFeatures]:
        """Build sector features for all symbols."""
        if sector_mapping is None:
            sector_mapping = self.sector_mapping

        conn = self._connect()
        try:
            cutoff_date = self._get_cutoff_date(conn, target_date)
            if not cutoff_date:
                return [
                    SectorFeatures(symbol=s, date=target_date, data_cutoff_date="")
                    for s in symbols
                ]

            # Group stocks by sector (only those in our symbol list)
            sector_stocks: dict[str, list[str]] = {}
            for sym in symbols:
                if sym == "VNINDEX":
                    continue
                sec = sector_mapping.get(sym, "")
                if not sec or sec == "Index":
                    continue
                sector_stocks.setdefault(sec, []).append(sym)

            # VNINDEX return for relative calculation
            vnindex_return_20d = self._fetch_returns(
                conn, "VNINDEX", cutoff_date, self.cfg["periods"]["return_medium"]
            )

            # Compute sector metrics
            sector_metrics = self._compute_sector_metrics(
                conn, cutoff_date, sector_stocks, vnindex_return_20d
            )

            num_ranked_sectors = sum(
                1 for m in sector_metrics.values() if m.sector_rank_20d > 0
            )

            # Compute rank change
            past_ranks = self._compute_sector_rank_change(
                conn, target_date, cutoff_date, sector_stocks
            )
            for name, m in sector_metrics.items():
                if name in past_ranks and m.sector_rank_20d > 0:
                    m.sector_rank_change_10d = past_ranks[name] - m.sector_rank_20d
                    # positive = improved (rank number decreased = better)

            # Per-stock features within each sector
            stock_returns_20d: dict[str, float | None] = {}
            for sym in symbols:
                if sym == "VNINDEX":
                    continue
                stock_returns_20d[sym] = self._fetch_returns(
                    conn, sym, cutoff_date, self.cfg["periods"]["return_medium"]
                )

            # Compute within-sector rankings
            sector_stock_rankings: dict[str, list[tuple[str, float]]] = {}
            for sec_name, stocks in sector_stocks.items():
                ranked_stocks = []
                for s in stocks:
                    r = stock_returns_20d.get(s)
                    if r is not None:
                        ranked_stocks.append((s, r))
                ranked_stocks.sort(key=lambda x: x[1], reverse=True)
                sector_stock_rankings[sec_name] = ranked_stocks

            # Build features for each symbol
            results = []
            for sym in symbols:
                if sym == "VNINDEX":
                    continue

                sec = sector_mapping.get(sym, "")
                feat = SectorFeatures(
                    symbol=sym, date=target_date,
                    data_cutoff_date=cutoff_date, sector_name=sec,
                )

                if not sec or sec == "Index":
                    results.append(feat)
                    continue

                sm = sector_metrics.get(sec)
                if sm is None:
                    results.append(feat)
                    continue

                # Check sufficient data for this stock
                hist_count = self._count_history_days(conn, sym, cutoff_date)
                if hist_count < self.cfg["min_history_days"]:
                    results.append(feat)
                    continue

                feat.has_sufficient_data = True
                feat.is_singleton = sm.is_singleton
                feat.num_stocks_in_sector = sm.num_stocks
                feat.num_sectors = num_ranked_sectors

                if sm.is_singleton:
                    results.append(feat)
                    continue

                feat.sector_return_20d = sm.sector_return_20d
                feat.sector_return_5d = sm.sector_return_5d
                feat.sector_vs_market_20d = sm.sector_vs_market_20d
                feat.sector_rank_20d = sm.sector_rank_20d
                feat.sector_pct_above_sma50 = sm.sector_pct_above_sma50
                feat.sector_momentum = sm.sector_momentum
                feat.sector_rank_change_10d = sm.sector_rank_change_10d

                # Stock within sector
                stock_r20 = stock_returns_20d.get(sym)
                if stock_r20 is not None:
                    feat.stock_return_20d = stock_r20
                    feat.stock_vs_sector_20d = stock_r20 - sm.sector_return_20d

                rankings = sector_stock_rankings.get(sec, [])
                for rank_idx, (ranked_sym, _) in enumerate(rankings, start=1):
                    if ranked_sym == sym:
                        feat.stock_rank_in_sector = rank_idx
                        if rank_idx == 1 and len(rankings) > 1:
                            feat.is_sector_leader = True
                        if rank_idx == len(rankings) and len(rankings) > 1:
                            feat.is_sector_laggard = True
                        break

                results.append(feat)

            return results
        finally:
            conn.close()

    def build(
        self, symbol: str, target_date: str,
        sector_mapping: dict[str, str] | None = None,
    ) -> SectorFeatures:
        """Build features for a single symbol (still needs all sector data)."""
        if sector_mapping is None:
            sector_mapping = self.sector_mapping

        all_symbols = list(sector_mapping.keys())
        if "VNINDEX" not in all_symbols:
            all_symbols.append("VNINDEX")

        results = self.build_all(all_symbols, target_date, sector_mapping)
        for feat in results:
            if feat.symbol == symbol:
                return feat

        return SectorFeatures(symbol=symbol, date=target_date, data_cutoff_date="")
