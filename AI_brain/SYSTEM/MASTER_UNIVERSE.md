# MASTER UNIVERSE — AI_STOCK

Version: 1.0
Date: 2026-03-15
Status: LOCKED

---

## QUY TẮC BẮT BUỘC

**Mọi tool, module, script trong hệ thống AI_STOCK phải lấy universe từ file này.**

- KHÔNG hardcode danh sách mã trong code
- KHÔNG tự thêm/bỏ mã mà không cập nhật file này
- Mọi thay đổi universe phải được approve và cập nhật version

---

## UNIVERSE SUMMARY

| Item | Giá trị |
|---|---|
| Tổng symbols | 92 |
| Tradable stocks | 91 |
| Index reference | 1 (VNINDEX) |
| Số sectors | 14 |
| Source | config.py V4 — March 2026 |

---

## VNINDEX

| Symbol | Loại | Ghi chú |
|---|---|---|
| VNINDEX | Index | Market reference — không tradable |

---

## 91 TRADABLE STOCKS THEO SECTOR

### Ngân hàng (13 mã)
ACB, BID, CTG, EIB, HDB, MBB, MSB, SHB, STB, TCB, TPB, VCB, VPB

### Chứng khoán (10 mã)
AGR, BSI, FTS, HCM, MBS, SHS, SSI, VCI, VIX, VND

### Bất động sản (12 mã)
BCM, CEO, DIG, DXG, IDC, KBC, KDH, NLG, NVL, PDR, VHM, VIC

### Dầu khí (6 mã)
BSR, GAS, OIL, PLX, PVD, PVS

### Công nghiệp / Hạ tầng (9 mã)
C4G, CTD, FCN, GEX, HHV, LCG, PC1, REE, VGC

### Thép / Vật liệu (5 mã)
HPG, HSG, HT1, KSB, NKG

### Bán lẻ / Tiêu dùng (7 mã)
DGW, FRT, MSN, MWG, PNJ, SAB, VRE

### Công nghệ (3 mã)
CMG, ELC, FPT

### Phân bón / Hóa chất (4 mã)
CSV, DCM, DGC, DPM

### Dệt may / Xuất khẩu (5 mã)
GIL, MSH, STK, TNG, VGT

### Logistics / Cảng (5 mã)
GMD, HAH, PVT, SCS, VSC

### Điện / Năng lượng (4 mã)
BWE, GEG, NT2, POW

### Hàng không (2 mã)
HVN, VJC

### Khác (6 mã)
AAA, ANV, BMP, PAN, PET, VHC

---

## DANH SÁCH ĐẦY ĐỦ (SORTED A-Z)

```
AAA, ACB, AGR, ANV, BCM, BID, BMP, BSI, BSR, BWE,
C4G, CEO, CMG, CSV, CTD, CTG, DCM, DGC, DGW, DIG,
DPM, DXG, EIB, ELC, FCN, FPT, FRT, FTS, GAS, GEG,
GEX, GIL, GMD, HAH, HCM, HDB, HHV, HPG, HSG, HT1,
HVN, IDC, KBC, KDH, KSB, LCG, MBB, MBS, MSB, MSH,
MSN, MWG, NKG, NLG, NT2, NVL, OIL, PAN, PC1, PDR,
PET, PLX, PNJ, POW, PVD, PVS, PVT, REE, SAB, SCS,
SHB, SHS, SSI, STB, STK, TCB, TNG, TPB, VCB, VCI,
VGC, VGT, VHC, VHM, VIC, VIX, VJC, VND, VPB, VRE,
VSC,
VNINDEX
```

Total: 91 stocks + VNINDEX = **92 symbols**

---

## SYMBOL → SECTOR MAPPING

| Symbol | Sector |
|---|---|
| AAA | Khác |
| ACB | Ngân hàng |
| AGR | Chứng khoán |
| ANV | Khác |
| BCM | Bất động sản |
| BID | Ngân hàng |
| BMP | Khác |
| BSI | Chứng khoán |
| BSR | Dầu khí |
| BWE | Điện/Năng lượng |
| C4G | Công nghiệp/Hạ tầng |
| CEO | Bất động sản |
| CMG | Công nghệ |
| CSV | Phân bón/Hóa chất |
| CTD | Công nghiệp/Hạ tầng |
| CTG | Ngân hàng |
| DCM | Phân bón/Hóa chất |
| DGC | Phân bón/Hóa chất |
| DGW | Bán lẻ/Tiêu dùng |
| DIG | Bất động sản |
| DPM | Phân bón/Hóa chất |
| DXG | Bất động sản |
| EIB | Ngân hàng |
| ELC | Công nghệ |
| FCN | Công nghiệp/Hạ tầng |
| FPT | Công nghệ |
| FRT | Bán lẻ/Tiêu dùng |
| FTS | Chứng khoán |
| GAS | Dầu khí |
| GEG | Điện/Năng lượng |
| GEX | Công nghiệp/Hạ tầng |
| GIL | Dệt may/Xuất khẩu |
| GMD | Logistics/Cảng |
| HAH | Logistics/Cảng |
| HCM | Chứng khoán |
| HDB | Ngân hàng |
| HHV | Công nghiệp/Hạ tầng |
| HPG | Thép/Vật liệu |
| HSG | Thép/Vật liệu |
| HT1 | Thép/Vật liệu |
| HVN | Hàng không |
| IDC | Bất động sản |
| KBC | Bất động sản |
| KDH | Bất động sản |
| KSB | Thép/Vật liệu |
| LCG | Công nghiệp/Hạ tầng |
| MBB | Ngân hàng |
| MBS | Chứng khoán |
| MSB | Ngân hàng |
| MSH | Dệt may/Xuất khẩu |
| MSN | Bán lẻ/Tiêu dùng |
| MWG | Bán lẻ/Tiêu dùng |
| NKG | Thép/Vật liệu |
| NLG | Bất động sản |
| NT2 | Điện/Năng lượng |
| NVL | Bất động sản |
| OIL | Dầu khí |
| PAN | Khác |
| PC1 | Công nghiệp/Hạ tầng |
| PDR | Bất động sản |
| PET | Khác |
| PLX | Dầu khí |
| PNJ | Bán lẻ/Tiêu dùng |
| POW | Điện/Năng lượng |
| PVD | Dầu khí |
| PVS | Dầu khí |
| PVT | Logistics/Cảng |
| REE | Công nghiệp/Hạ tầng |
| SAB | Bán lẻ/Tiêu dùng |
| SCS | Logistics/Cảng |
| SHB | Ngân hàng |
| SHS | Chứng khoán |
| SSI | Chứng khoán |
| STB | Ngân hàng |
| STK | Dệt may/Xuất khẩu |
| TCB | Ngân hàng |
| TNG | Dệt may/Xuất khẩu |
| TPB | Ngân hàng |
| VCB | Ngân hàng |
| VCI | Chứng khoán |
| VGC | Công nghiệp/Hạ tầng |
| VGT | Dệt may/Xuất khẩu |
| VHC | Khác |
| VHM | Bất động sản |
| VIC | Bất động sản |
| VIX | Chứng khoán |
| VJC | Hàng không |
| VND | Chứng khoán |
| VPB | Ngân hàng |
| VRE | Bán lẻ/Tiêu dùng |
| VSC | Logistics/Cảng |
| VNINDEX | Index |

---

## CHANGELOG

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-03-15 | Initial — 91 stocks + VNINDEX, sourced from V4 config.py |

---

*File này là SINGLE SOURCE OF TRUTH cho universe của hệ thống AI_STOCK.*
*Mọi thay đổi phải được approve trước khi cập nhật.*
