# PENDING IMPLEMENTATION
# Updated: 2026-03-17

================================================================
COMPLETED ✅
================================================================
- R0 max_iter=2000
- R7 monotonic constraints (23 features)
- R7 regime-aware training (bear 5x weight)
- R7 v4: bear block + T-1 leakage fix + pre-listing cleanup
- R7 v4: 5,591 signals, 10/13 phases EV+
- Feature drift detector
- 8 regime interaction features (140 features total)

================================================================
IN PROGRESS 🔄
================================================================
- RegimeFilter shared module (regime_filter.py)
  Apply cho: R0, R2, R3, R4, R5, R6, R7
  File: D:\AI\AI_engine\r_layer\regime_filter.py

================================================================
PENDING ⏳
================================================================
- V4CHANNEL expert build
- Retrain tất cả R models với RegimeFilter
- Backup Plan A final
- OOS evaluation full sau RegimeFilter

================================================================
REGIME LOGIC (đã confirm):
================================================================
Strong Bull (>=+2):          threshold=0.55
Bull (+1..+2):               threshold=0.60
Neutral (0) đi ngang:        threshold=0.65
Neutral (0) từ -1 lên:       threshold=0.60
Neutral (0) từ +1 xuống:     threshold=0.70
Weak Bear (-1) từ -2 lên:    threshold=0.70
Weak Bear (-1) đi ngang:     BLOCK BUY
Weak Bear (-1) cải thiện:    threshold=0.60
Weak Bear (-1) giảm tiếp:    BLOCK BUY
Bear (<=-2):                  BLOCK BUY hoàn toàn

SELL active khi regime <= 0:
  Triggers: MA20 break, Fibo break, Volume spike bearish
  Strength: delta<-0.3=STRONG, abs<=0.3=NORMAL, >0.3=WEAK

================================================================
Git: commit 2ce1a56
================================================================
