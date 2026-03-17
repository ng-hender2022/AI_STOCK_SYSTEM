# PENDING IMPLEMENTATION
# Thực hiện SAU KHI Plan A train xong
# Files rulebook đã có trong D:\AI\AI_brain\SYSTEM\KNOWLEDGE\

================================================================
TASK 1: R0 Fix
================================================================
File: D:\AI\AI_engine\r_layer\r0_baseline\config.yaml
Change: max_iter=2000

================================================================
TASK 2 + 3: R7 CatBoost Update (gộp chung, retrain R7 only)
================================================================
Rulebooks:
  - KNOWLEDGE\AI_STOCK_MONOTONIC_CONSTRAINT_MAP.md ✅ (đã có)
  - KNOWLEDGE\AI_STOCK_REGIME_AWARE_TRAINING.md ✅ (đã có)

2a. model.py - Monotonic Constraints:
  Positive (=1): trend_persistence, ma_alignment_score, trend_strength_max,
    rs_rank, sector_momentum, momentum_score_avg,
    volume_ratio_5, volume_ratio_20, volume_pressure,
    liquidity_shock, liquidity_shock_avg,
    trend_score_avg, trend_alignment_score, expert_agreement_pct
  Negative (=-1): atr_pct, atr_percentile, bb_width, volatility_score
  Neutral (=0): rsi_norm, sto_norm, macd_hist_slope,
    candle_pattern_code, pattern_type_code, breakout20_flag, breakout60_flag

2b. config.yaml:
  iterations=2000, depth=6, learning_rate=0.02
  l2_leaf_reg=8, loss_function=Logloss, eval_metric=AUC
  task_type=GPU, devices=0

2c. trainer.py - Sample Weighting:
  Strong Bear (<= -3): weight=5.0
  Bear (<= -2):        weight=3.0
  Sideways (-1..+1):   weight=1.5
  Bull (>= +2):        weight=1.0

2d. meta_builder.py - Thêm 2 regime features:
  regime_duration: đếm ngày liên tiếp cùng regime direction
  regime_transition: regime_score[t] - regime_score[t-3]

2e. evaluation: report per-regime metrics (Bull/Sideways/Bear)

================================================================
TASK 4: Feature Drift Detection
================================================================
Rulebook: KNOWLEDGE\FEATURE_DRIFT_DETECTION.md (tạo mới khi implement)

4a. Tạo D:\AI\AI_engine\r_layer\feature_drift_detector.py
4b. models.db: thêm bảng feature_importance_history
4c. Tích hợp vào r_orchestrator.py
4d. Report: D:\AI\AI_data\reports\feature_drift_report.txt

================================================================
EXECUTION ORDER:
================================================================
Step 1: Implement TASK 1,2,3,4 (code changes only, no training)
Step 2: Chạy tests verify
Step 3: Xóa R Layer data (models.db tables)
Step 4: Retrain R7 ONLY (R0,R2,R3,R4,R5,R6 giữ nguyên)
Step 5: OOS evaluation với EV metrics per regime
Step 6: So sánh Plan A before/after
Step 7: Backup Plan A final

================================================================
STATUS: ⏳ WAITING FOR PLAN A TRAINING TO COMPLETE
================================================================
