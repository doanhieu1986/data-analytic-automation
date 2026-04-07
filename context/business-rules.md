# Business Rules — Nghiệp vụ Chứng khoán

> File này định nghĩa các quy tắc nghiệp vụ, KPI, và logic tính toán.
> Claude Code PHẢI đọc file này trước khi diễn giải bất kỳ số liệu nào.

---

## 1. Lịch giao dịch

| Sàn | Phiên sáng | Phiên chiều | ATO | ATC |
|-----|-----------|-------------|-----|-----|
| HOSE | 09:00–11:30 | 13:00–14:45 | 09:00–09:15 | 14:30–14:45 |
| HNX | 09:00–11:30 | 13:00–14:30 | 09:00–09:00 | 14:15–14:30 |
| UPCoM | 09:00–11:30 | 13:00–14:45 | — | — |

**Ngày không giao dịch:** Thứ 7, Chủ nhật, ngày lễ theo lịch VN

---

## 2. Định nghĩa KPI cốt lõi

### 2.1 P&L (Lãi/Lỗ)

```
Unrealized P&L = (Giá thị trường hiện tại - Giá vốn bình quân) × Số lượng đang nắm giữ
Realized P&L   = (Giá bán - Giá vốn) × Số lượng đã bán - Phí giao dịch
Total P&L      = Realized P&L + Unrealized P&L
```

**Lưu ý:**
- Giá vốn bình quân tính theo phương pháp **[FIFO / Bình quân gia quyền — điền vào]**
- Phí giao dịch bao gồm: phí môi giới + thuế TNCN (0.1% giá trị bán)

### 2.2 NAV (Net Asset Value)

```
NAV = Tổng giá trị tài sản - Tổng nợ (margin, phí chờ thanh toán)
Giá trị tài sản = Tiền mặt + Σ(Giá thị trường × Số lượng) + CK chờ về
```

### 2.3 Margin Ratio

```
Tỷ lệ ký quỹ = (Tài sản ròng / Tổng giá trị danh mục) × 100%
Call margin khi: Tỷ lệ ký quỹ < [X]%  ← điền ngưỡng thực tế
Force sell khi: Tỷ lệ ký quỹ < [Y]%   ← điền ngưỡng thực tế
```

### 2.4 Market Cap

```
Market Cap = Giá đóng cửa × Số lượng cổ phiếu lưu hành
```

### 2.5 Volume metrics

- **Khớp lệnh (Matched volume):** Khối lượng thực sự được khớp
- **Đặt lệnh (Order volume):** Khối lượng đặt (có thể chưa khớp)
- **ADTV (Average Daily Trading Volume):** Trung bình 20/30 phiên gần nhất

---

## 3. Phân loại khách hàng

| Loại | Định nghĩa | Ngưỡng tài sản |
|------|-----------|----------------|
| Standard | KH thường | < [X] VND |
| Silver | KH trung bình | [X] – [Y] VND |
| Gold | KH VIP | [Y] – [Z] VND |
| Platinum | KH VVIP | > [Z] VND |

> **TODO:** Điền ngưỡng thực tế từ tài liệu nội bộ

---

## 4. Quy tắc xử lý dữ liệu

### 4.1 Giá trị NULL / Missing
- Giá cổ phiếu NULL → ngày nghỉ, không giao dịch (không phải lỗi dữ liệu)
- Volume = 0 → hợp lệ (không có giao dịch trong phiên)
- Số dư KH NULL → kiểm tra lại, có thể lỗi ETL

### 4.2 Điều chỉnh giá (Price adjustment)
- Sau khi **chia cổ tức, chia cổ phiếu thưởng, quyền mua**: giá lịch sử cần điều chỉnh ngược
- Cột giá điều chỉnh trong DWH: `adj_close_price` (nếu có)
- Phân tích kỹ thuật: **PHẢI dùng giá điều chỉnh**
- Báo cáo P&L KH: dùng **giá thực tế** (không điều chỉnh)

### 4.3 Đơn vị tiền tệ
- Tất cả số tiền: **VND**, không có số thập phân
- Giá cổ phiếu HOSE/HNX: đơn vị **nghìn đồng (VND × 1000)** khi hiển thị, lưu trong DB là **VND nguyên**
- Khi báo cáo: convert sang triệu hoặc tỷ cho dễ đọc

---

## 5. Thuật ngữ chuyên ngành → tên cột DB

| Thuật ngữ | Tên cột phổ biến | Ghi chú |
|-----------|----------------|---------|
| Mã chứng khoán | `ticker`, `stock_code`, `symbol` | Điền tên thực tế |
| Ngày giao dịch | `trade_date`, `trading_date` | |
| Giá khớp | `match_price`, `close_price` | |
| Khối lượng khớp | `match_volume`, `volume` | |
| Tài khoản KH | `account_id`, `customer_id` | |
| Số dư tiền | `cash_balance` | |

> **TODO:** Cập nhật mapping thực tế theo schema của công ty

---

## 6. Các trường hợp đặc biệt cần chú ý

- **Cổ phiếu bị đình chỉ giao dịch:** volume = 0, giá = giá phiên cuối
- **Cổ phiếu mới niêm yết (IPO):** không có dữ liệu lịch sử → handle `NaN` khi tính indicator
- **Giá trần/sàn:** HOSE ±7%, HNX ±10%, UPCoM ±15%
- **Lô giao dịch tối thiểu:** HOSE/HNX = 100 cổ phiếu
