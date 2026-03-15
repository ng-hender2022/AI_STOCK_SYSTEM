# SECTOR_RULEBOOK — AI_STOCK v2
Generated: 2026-03-15
Expert ID: V4S
Scale: -4 → +4

---

## 1. INDICATORS / METRICS USED (with parameters)

### 1.1 Sector Classification
| Sector Code | Sector Name | Typical HOSE/HNX Stocks (examples) |
|-------------|------------|-------------------------------------|
| `BANK` | Banking & Finance | VCB, BID, CTG, TCB, MBB, ACB, VPB, STB, HDB, TPB, LPB, SHB, EIB |
| `REAL` | Real Estate | VHM, VIC, NVL, KDH, DXG, NLG, PDR, HDG, DIG, SCR |
| `STEEL` | Steel & Materials | HPG, HSG, NKG, TLH, POM |
| `RETAIL` | Retail & Consumer | MWG, FRT, PNJ, DGW |
| `FOOD` | Food & Beverage | VNM, MSN, SAB, KDC, QNS |
| `CHEM` | Chemicals & Fertilizers | DPM, DCM, DGC, CSV, LAS |
| `TECH` | Technology & IT | FPT, CMG, ELC |
| `ENERGY` | Oil & Gas & Power | GAS, PLX, PVD, PVS, POW, PPC, REE, NT2, VSH |
| `PROP_MAT` | Construction & Building Materials | CTD, HBC, VCG, HHV, FCN |
| `LOGISTICS` | Logistics & Transportation | GMD, VTP, VOS, HAH, SGP |
| `SECURITIES` | Securities Companies | SSI, VCI, HCM, VND, SHS |
| `OTHER` | Other / Uncategorized | Stocks not fitting above sectors |

**Note**: Sector assignments are maintained in a static mapping file. Review and update quarterly.

### 1.2 Sector Performance Metrics
| Metric | Definition | Params |
|--------|-----------|--------|
| **Sector_Return_5d** | Equal-weighted average 5-day return of all stocks in sector | `period: 5` |
| **Sector_Return_20d** | Equal-weighted average 20-day return of all stocks in sector | `period: 20` |
| **Sector_Return_60d** | Equal-weighted average 60-day return of all stocks in sector | `period: 60` |
| **Sector_vs_Market_5d** | Sector_Return_5d - VNINDEX_Return_5d | — |
| **Sector_vs_Market_20d** | Sector_Return_20d - VNINDEX_Return_20d | — |
| **Sector_Rank_5d** | Rank of sector by 5d return among all sectors (1 = best) | — |
| **Sector_Rank_20d** | Rank of sector by 20d return among all sectors (1 = best) | — |

### 1.3 Sector Breadth Metrics
| Metric | Definition | Params |
|--------|-----------|--------|
| **Sector_Pct_Advancing** | % of stocks in sector with positive daily return | Daily |
| **Sector_Pct_Above_SMA20** | % of stocks in sector above their 20-day SMA | `sma: 20` |
| **Sector_Pct_Above_SMA50** | % of stocks in sector above their 50-day SMA | `sma: 50` |
| **Sector_Breadth_5d_Avg** | 5-day average of Sector_Pct_Advancing | `avg_period: 5` |

### 1.4 Sector Momentum & Rotation
| Metric | Definition | Params |
|--------|-----------|--------|
| **Sector_Momentum** | Sector_Return_5d - Sector_Return_20d (short vs medium term) — positive = accelerating | — |
| **Sector_Rank_Change_10d** | Change in Sector_Rank_20d over last 10 trading days | `period: 10` |
| **Rotation_Signal** | Fired when a sector's rank improves/declines by 3+ positions in 10 days | `threshold: 3` |
| **Sector_RS_Trend** | 10-day SMA of Sector_vs_Market_20d — rising or falling | `sma: 10` |

### 1.5 Stock-within-Sector Metrics
| Metric | Definition | Params |
|--------|-----------|--------|
| **Stock_vs_Sector** | Stock return - Sector average return (for each period) | Same periods |
| **Stock_Sector_Rank** | Rank of stock within its sector by 20d return | — |
| **Is_Sector_Leader** | Stock_Sector_Rank = 1 | Boolean |
| **Is_Sector_Laggard** | Stock_Sector_Rank = last | Boolean |

---

## 2. SCORING RULES (detailed score mapping table)

### 2.1 Sector Strength Sub-Score (for the stock's sector)

| Condition | Sub-Score |
|-----------|-----------|
| Sector_Rank_20d = 1 AND Sector_vs_Market_20d > +5% | +4 |
| Sector_Rank_20d in top 2 AND Sector_vs_Market_20d > +3% | +3 |
| Sector_Rank_20d in top 3 AND Sector_vs_Market_20d > +1% | +2 |
| Sector_Rank_20d in top half AND Sector_vs_Market_20d > 0% | +1 |
| Sector_Rank_20d in middle third | 0 |
| Sector_Rank_20d in bottom half AND Sector_vs_Market_20d < 0% | -1 |
| Sector_Rank_20d in bottom 3 AND Sector_vs_Market_20d < -1% | -2 |
| Sector_Rank_20d in bottom 2 AND Sector_vs_Market_20d < -3% | -3 |
| Sector_Rank_20d = last AND Sector_vs_Market_20d < -5% | -4 |

### 2.2 Sector Momentum Modifier

| Condition | Modifier |
|-----------|----------|
| Sector_Momentum > 0 (sector accelerating) AND sector in top half | +1 |
| Sector_Momentum > 0 AND sector in bottom half (bounce attempt) | 0 |
| Sector_Momentum < 0 (sector decelerating) AND sector in top half | -1 |
| Sector_Momentum < 0 AND sector in bottom half (still declining) | -1 |
| Sector_Rank_Change_10d improvement >= +3 positions | +1 (rotation into sector) |
| Sector_Rank_Change_10d decline >= -3 positions | -1 (rotation out of sector) |

### 2.3 Sector Breadth Modifier

| Condition | Modifier |
|-----------|----------|
| Sector_Pct_Above_SMA50 > 80% | +1 |
| Sector_Pct_Above_SMA50 < 20% | -1 |
| Sector_Breadth_5d_Avg > 70% (most stocks advancing consistently) | +1 |
| Sector_Breadth_5d_Avg < 30% (most stocks declining consistently) | -1 |

### 2.4 Stock-within-Sector Modifier

| Condition | Modifier |
|-----------|----------|
| Is_Sector_Leader AND Stock_vs_Sector > +3% (20d) | +1 |
| Is_Sector_Laggard AND Stock_vs_Sector < -3% (20d) | -1 |

### 2.5 Final Score Calculation
```
raw_score = sector_strength_sub + sector_momentum_mod + sector_breadth_mod + stock_within_sector_mod
final_score = clamp(raw_score, -4, +4)
```

---

## 3. SIGNAL CODES (reference SIGNAL_CODEBOOK)

| Code | Meaning | Typical Score |
|------|---------|---------------|
| `SEC_TOP_SECTOR` | Stock is in the #1 ranked sector | +3 to +4 |
| `SEC_STRONG_SECTOR` | Stock is in a top-3 sector | +2 to +3 |
| `SEC_WEAK_SECTOR` | Stock is in a bottom-3 sector | -2 to -3 |
| `SEC_WORST_SECTOR` | Stock is in the last-ranked sector | -3 to -4 |
| `SEC_SECTOR_ACCEL` | Sector is accelerating (momentum positive, rank improving) | +1 modifier |
| `SEC_SECTOR_DECEL` | Sector is decelerating (momentum negative, rank declining) | -1 modifier |
| `SEC_ROTATION_IN` | Sector rank improved by 3+ positions in 10 days — money rotating in | +1 modifier |
| `SEC_ROTATION_OUT` | Sector rank declined by 3+ positions in 10 days — money rotating out | -1 modifier |
| `SEC_LEADER_IN_SECTOR` | Stock is the #1 performer within its sector | +1 modifier |
| `SEC_LAGGARD_IN_SECTOR` | Stock is the worst performer within its sector | -1 modifier |
| `SEC_BROAD_SECTOR_ADVANCE` | >80% of sector stocks above SMA50 | Bullish |
| `SEC_BROAD_SECTOR_DECLINE` | <20% of sector stocks above SMA50 | Bearish |
| `SEC_NEUTRAL` | Sector in middle, no strong signal | 0 |
| `SEC_SECTOR_DIVERGENCE` | Sector ranking changed significantly but stock did not follow | Flag only |

---

## 4. SIGNAL QUALITY RULES

### 4.1 Confidence Assessment
| Level | Criteria |
|-------|----------|
| **HIGH** | Sector rank consistent across 5d and 20d, breadth confirms, momentum aligns, stock rank in sector aligns |
| **MEDIUM** | Sector rank clear (top/bottom 3) but one metric diverges (e.g., momentum reversing) |
| **LOW** | Sector in middle of rankings, or 5d and 20d ranks diverge significantly |
| **TRANSITIONAL** | Sector rank changed by 3+ positions recently — signal may not persist |

### 4.2 Minimum Sector Size
- Sectors with fewer than 3 stocks in the 91-stock universe: flag `SEC_SMALL_SECTOR`
- Small sectors have higher variance — reduce confidence by one level
- If a sector has only 1 stock, output that stock's sector score = 0 with code `SEC_SINGLETON` (sector analysis is meaningless for single-stock sectors)

### 4.3 Recalculation
- Sector scores recalculated **daily at end of session**
- Rotation signals require 10 days of rank history
- Score valid for **1 trading day**

### 4.4 Staleness
- If a stock in a sector is halted for 5+ days, exclude it from sector calculations
- If >50% of a sector's stocks are halted, flag `SEC_SECTOR_HALTED` and set score to 0

---

## 5. EDGE CASES

### 5.1 Sector with One Dominant Stock
- Banking sector is dominated by VCB (largest by market cap). Equal-weighted sector return prevents cap-weighted distortion, but VCB's move can still diverge significantly from sector average.
- If a single stock contributes >40% of sector trading value on a given day, flag `SEC_DOMINATED_BY_SINGLE` — the sector signal may be driven by one name.

### 5.2 Sector Reclassification
- If a stock is reclassified to a different sector (e.g., due to business change): recompute sector history with new classification. Emit `SEC_RECLASSIFICATION`.
- Do not compare sector rankings before and after reclassification for rotation signals.

### 5.3 IPO/New Addition to Sector
- When a new stock joins a sector in the 91-stock universe: exclude from sector calculations for 20 trading days.
- After 20 days, include in all calculations.
- If the new stock is large relative to sector, flag `SEC_NEW_MEMBER_IMPACT`.

### 5.4 Cross-Sector Stocks
- Some conglomerates span multiple sectors (e.g., VIC/VHM real estate + retail + healthcare). Assign to primary sector by revenue source.
- Flag `SEC_CONGLOMERATE` for stocks with significant revenue from multiple sectors.

### 5.5 Sector Earnings Season Effects
- Vietnam earnings reports cluster around specific periods (Q1: April, Q2: July-August, Q3: October, Q4: January-February).
- During earnings season, sector returns may be driven by first reporters. Flag `SEC_EARNINGS_SEASON` during these windows.
- First mover effect: if the first stock reporting in a sector has extreme results (>10% move), the entire sector may reprice before other stocks report.

### 5.6 All Sectors Moving Together
- If all sectors have Sector_vs_Market within +/-1%, sector differentiation is minimal. Flag `SEC_LOW_DISPERSION`.
- In this case, sector signal is unreliable. Cap all sector scores at +/-1.

---

## 6. VIETNAM MARKET NOTES (specific adaptations for HOSE/HNX)

### 6.1 Dominant Sectors on HOSE
By market cap weight in VNINDEX:
1. **Banking**: ~30-35% of VNINDEX weight. When banking is strong, VNINDEX is strong almost by definition.
2. **Real Estate**: ~10-15%. Highly cyclical, interest-rate sensitive.
3. **Food & Beverage**: ~8-10%. Defensive, less volatile.
4. **Steel**: ~3-5%. Highly cyclical, China-dependent.
5. **Technology**: ~5-8%. FPT dominates. Growth narrative.

**Implication**: A bullish banking sector almost guarantees a bullish VNINDEX due to weight. Sector analysis is most valuable for non-banking sectors where the signal is not mechanically linked to the index.

### 6.2 Sector Rotation Patterns in Vietnam
Historical rotation patterns:
- **Early Bull**: Securities > Banks > Real Estate (leverage beneficiaries lead)
- **Mid Bull**: Steel > Construction > Tech (cyclicals + growth)
- **Late Bull**: Retail > Food (defensive rotation begins)
- **Bear**: Food > Utilities (defensive sectors, but all decline)
- **Recovery**: Securities > Banks (liquidity-sensitive first)

Use these patterns as a sanity check: if securities are rallying from a beaten-down level, it may signal early bull regime. Cross-reference with V4REG.

### 6.3 Interest Rate Sensitivity
| Sector | Rate Sensitivity | Notes |
|--------|-----------------|-------|
| Banking | HIGH (inverse short-term) | Rate cuts boost lending demand, but compress NIM |
| Real Estate | VERY HIGH (inverse) | Lower rates = cheaper mortgages, higher property demand |
| Securities | HIGH (inverse) | Lower rates boost trading activity and margin lending |
| Utilities | MODERATE (inverse) | Lower discount rate increases PV of future cash flows |
| Steel | LOW | Driven more by commodity prices and China demand |
| Tech | LOW-MODERATE | Growth stocks benefit from lower rates theoretically |
| Food/Retail | LOW | Consumer demand driven |

### 6.4 Commodity-Linked Sectors
| Sector | Commodity Link | Data Source |
|--------|---------------|-------------|
| Steel | HRC steel price (China), iron ore | Monitor ChinaScope / Platts |
| Energy (O&G) | Brent crude oil | International benchmarks |
| Chemicals/Fertilizers | Urea, DAP prices | International + domestic |
| Food | Sugar, dairy commodity prices | For VNM, MSN etc. |

When commodity prices move sharply (>5% in a week), the linked sector will likely follow. This can precede the sector return metrics by 1-3 days.

### 6.5 Government-Linked Sectors
- State-owned enterprises (SOEs) are concentrated in Banking (VCB, BID, CTG), Energy (GAS, PVD), and Telecom
- SOEs may have different price behavior: less volatile, potential government intervention
- Divestment announcements for SOEs can create one-off sector moves. Flag `SEC_SOE_DIVESTMENT` when known.

### 6.6 Cross-Reference with Other Experts
| Expert | Cross-Reference Logic |
|--------|-----------------------|
| V4REG | If regime is STRONG_BEAR, cap positive sector scores at +2 (even best sector declines in bear markets) |
| V4RS | RS leader in top sector = highest conviction. RS laggard in top sector = avoid despite sector strength |
| V4LIQ | If sector is top-ranked but component stocks have low liquidity (V4LIQ <= -2), discount sector score by 1 |
| V4BR | If market breadth is narrow (V4BR <= 0), strong sector scores may be misleading — rally is concentrated |

### 6.7 Sector ETFs and Index Funds
- Vietnam has limited sector ETFs, but some funds track VN30/VNDIAMOND/VNFIN
- VNFIN (financial sector index) can serve as a real-time proxy for banking sector strength
- If VNFIN diverges from computed banking sector return, investigate — could be ETF-specific flow distortion
