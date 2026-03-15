# DATA LEAKAGE PREVENTION RULES

Version: 1.0
Date: 2026-03-15
Status: LOCKED — KHÔNG được vi phạm bất kỳ hoàn cảnh nào

## QUY TẮC CỐT LÕI

Ngày T chỉ được dùng data từ T-1 trở về trước.

## FEATURE MATRIX NGÀY T

ĐƯỢC PHÉP:
- OHLCV close của ngày T-1 trở về trước
- Expert signals tính từ data đến hết ngày T-1
- Regime score tính từ data đến hết ngày T-1
- Meta features tính từ expert signals đến T-1

KHÔNG ĐƯỢC PHÉP:
- Bất kỳ giá nào của ngày T (open, high, low, close)
- Intraday data của ngày T
- Bất kỳ thông tin nào xảy ra sau thời điểm tính feature

## LABEL NGÀY T

- t1_return: chỉ available sau close ngày T+1
- t5_return: chỉ available sau close ngày T+5
- t10_return: chỉ available sau close ngày T+10
- t20_return: chỉ available sau close ngày T+20
- Label KHÔNG BAO GIỜ được tính trước khi ngày đó đóng cửa

## VDATA PACKAGING RULE

Khi đóng gói training package ngày T:
- features_date = T (nhưng chỉ dùng data đến T-1)
- label_available_date_t1 = T+1
- label_available_date_t5 = T+5
- label_available_date_t10 = T+10
- label_available_date_t20 = T+20

Vdata PHẢI kiểm tra label_available_date trước khi gắn label vào package.

## R LAYER RULE

- R Layer KHÔNG được nhận bất kỳ future data nào
- Training pipeline PHẢI dùng TimeSeriesSplit hoặc walk-forward validation
- KHÔNG dùng random split cho time series data
- Validation set PHẢI là period sau training set (chronological)

## KIỂM TRA BẮT BUỘC

Trước khi train bất kỳ R model nào, pipeline phải verify:
- feature_date < label_date (với mọi horizon)
- Không có future close trong feature columns
- Train period kết thúc trước validation period bắt đầu

## VI PHẠM

Nếu phát hiện leakage:
- Dừng training ngay lập tức
- Log lỗi vào audit.db
- Không publish prediction
- Báo cáo vào SYSTEM_HEALTH.md
