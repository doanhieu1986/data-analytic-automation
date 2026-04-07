# Data Dictionary — Từ điển Dữ liệu

> Mô tả tất cả các bảng và cột quan trọng. Claude Code đọc file này để biết
> schema thực tế trước khi viết SQL hay phân tích dữ liệu.
>
> **Cách dùng:** Điền thông tin thực tế vào các section bên dưới.
> Có thể dùng lệnh: `SELECT table_name, column_name, data_type FROM information_schema.columns`
> để export schema tự động rồi paste vào đây.

---

## Cách thêm bảng mới

Copy template dưới đây cho mỗi bảng:

```
### schema.table_name
**Mô tả:** [Mục đích của bảng]
**Database:** [postgres / bigquery / redshift]
**Update frequency:** [realtime / daily / weekly]
**Row count (approx):** [X triệu rows]
**Owner:** [team/người phụ trách]

| Column | Type | Nullable | Mô tả | Ví dụ |
|--------|------|----------|-------|-------|
| id | BIGINT | NO | Primary key | 12345 |
```

---

## 1. Market Data (Dữ liệu thị trường)

### [schema].ohlcv_daily
**Mô tả:** Dữ liệu giá OHLCV theo ngày của tất cả cổ phiếu
**Database:** [ĐIỀN — BigQuery/Redshift]
**Update frequency:** Daily, sau 17:00
**Nguồn:** HOSE, HNX feed

| Column | Type | Nullable | Mô tả | Ví dụ |
|--------|------|----------|-------|-------|
| `trade_date` | DATE | NO | Ngày giao dịch | 2024-03-15 |
| `ticker` | VARCHAR(10) | NO | Mã CK | VNM |
| `exchange` | VARCHAR(10) | NO | Sàn giao dịch | HOSE |
| `open_price` | BIGINT | YES | Giá mở cửa (VND) | 78000 |
| `high_price` | BIGINT | YES | Giá cao nhất | 79500 |
| `low_price` | BIGINT | YES | Giá thấp nhất | 77500 |
| `close_price` | BIGINT | YES | Giá đóng cửa | 78500 |
| `adj_close_price` | NUMERIC | YES | Giá đóng cửa điều chỉnh | 78500.00 |
| `volume` | BIGINT | YES | Khối lượng khớp | 1250000 |
| `value` | BIGINT | YES | Giá trị khớp (VND) | 98125000000 |
| `created_at` | TIMESTAMP | NO | Thời điểm insert | 2024-03-15 17:30:00 |

> **TODO:** Cập nhật tên schema/table thực tế

---

### [schema].tick_data
**Mô tả:** Dữ liệu tick từng lệnh khớp trong phiên
**Database:** [ĐIỀN]
**Update frequency:** Realtime trong giờ giao dịch
**Lưu ý:** Bảng này rất lớn, luôn filter theo `trade_date` trước

| Column | Type | Nullable | Mô tả | Ví dụ |
|--------|------|----------|-------|-------|
| `id` | BIGINT | NO | PK | 1234567 |
| `trade_date` | DATE | NO | Ngày giao dịch | 2024-03-15 |
| `trade_time` | TIME | NO | Giờ khớp lệnh | 09:32:45 |
| `ticker` | VARCHAR(10) | NO | Mã CK | HPG |
| `match_price` | BIGINT | NO | Giá khớp (VND) | 25600 |
| `match_volume` | INT | NO | Khối lượng khớp | 5000 |
| `trade_type` | VARCHAR(5) | YES | Loại lệnh: B/S/U | B |

---

## 2. Customer / Account Data (Dữ liệu khách hàng)

### [schema].customers
**Mô tả:** Thông tin khách hàng
**Database:** [ĐIỀN — PostgreSQL/SQL Server]
**PII:** Có — cần có permission đặc biệt khi truy vấn

| Column | Type | Nullable | Mô tả |
|--------|------|----------|-------|
| `customer_id` | VARCHAR(20) | NO | Mã KH nội bộ |
| `account_id` | VARCHAR(20) | NO | Số tài khoản CK |
| `full_name` | VARCHAR(200) | NO | Họ tên |
| `customer_type` | VARCHAR(20) | NO | Standard/Silver/Gold/Platinum |
| `broker_id` | VARCHAR(20) | YES | Broker phụ trách |
| `open_date` | DATE | NO | Ngày mở tài khoản |
| `status` | VARCHAR(20) | NO | ACTIVE/INACTIVE/SUSPENDED |

---

### [schema].account_balance
**Mô tả:** Số dư tài khoản cuối ngày
**Database:** [ĐIỀN]
**Update frequency:** Daily EOD (sau thanh toán T+2)

| Column | Type | Nullable | Mô tả |
|--------|------|----------|-------|
| `snapshot_date` | DATE | NO | Ngày chốt số dư |
| `account_id` | VARCHAR(20) | NO | Số tài khoản |
| `cash_balance` | BIGINT | NO | Số dư tiền mặt (VND) |
| `stock_value` | BIGINT | NO | Giá trị cổ phiếu (mark-to-market) |
| `total_asset` | BIGINT | NO | Tổng tài sản |
| `margin_debt` | BIGINT | NO | Dư nợ margin |
| `nav` | BIGINT | NO | NAV thuần |

---

### [schema].portfolio_positions
**Mô tả:** Danh mục nắm giữ của từng tài khoản
**Database:** [ĐIỀN]

| Column | Type | Nullable | Mô tả |
|--------|------|----------|-------|
| `snapshot_date` | DATE | NO | Ngày snapshot |
| `account_id` | VARCHAR(20) | NO | Tài khoản |
| `ticker` | VARCHAR(10) | NO | Mã CK |
| `quantity` | INT | NO | Số lượng đang giữ |
| `avg_cost` | BIGINT | NO | Giá vốn bình quân (VND) |
| `market_price` | BIGINT | NO | Giá thị trường |
| `market_value` | BIGINT | NO | Giá trị thị trường |
| `unrealized_pnl` | BIGINT | NO | Lãi/lỗ chưa thực hiện |

---

### [schema].transactions
**Mô tả:** Lịch sử lệnh giao dịch
**Database:** [ĐIỀN]

| Column | Type | Nullable | Mô tả |
|--------|------|----------|-------|
| `order_id` | VARCHAR(30) | NO | Mã lệnh |
| `trade_date` | DATE | NO | Ngày giao dịch |
| `account_id` | VARCHAR(20) | NO | Tài khoản |
| `ticker` | VARCHAR(10) | NO | Mã CK |
| `side` | CHAR(1) | NO | B (mua) / S (bán) |
| `order_price` | BIGINT | NO | Giá đặt |
| `order_volume` | INT | NO | Khối lượng đặt |
| `match_price` | BIGINT | YES | Giá khớp (NULL nếu chưa khớp) |
| `match_volume` | INT | YES | Khối lượng khớp |
| `fee` | BIGINT | NO | Phí giao dịch |
| `tax` | BIGINT | NO | Thuế TNCN |
| `status` | VARCHAR(20) | NO | MATCHED/PENDING/CANCELLED |

---

## 3. Reference Data

### [schema].tickers_master
**Mô tả:** Danh sách tất cả mã chứng khoán và thông tin công ty

| Column | Type | Mô tả |
|--------|------|-------|
| `ticker` | VARCHAR(10) | Mã CK |
| `company_name` | VARCHAR(500) | Tên công ty |
| `exchange` | VARCHAR(10) | HOSE/HNX/UPCoM |
| `sector` | VARCHAR(100) | Ngành (ICB Level 2) |
| `industry` | VARCHAR(100) | Ngành chi tiết (ICB Level 4) |
| `market_cap_category` | VARCHAR(20) | Large/Mid/Small cap |
| `listing_date` | DATE | Ngày niêm yết |
| `is_active` | BOOLEAN | Còn giao dịch? |

---

## 4. Lookup / Mapping

### Sector mapping (ICB)
```
10 — Năng lượng
15 — Vật liệu cơ bản
20 — Công nghiệp
25 — Hàng tiêu dùng không thiết yếu
30 — Hàng tiêu dùng thiết yếu
35 — Y tế
40 — Tài chính (Ngân hàng, CK, Bảo hiểm)
45 — Công nghệ thông tin
50 — Dịch vụ viễn thông
55 — Tiện ích
60 — Bất động sản
```

---

## 5. Những gì CHƯA có trong DB (cần lấy từ API)

- Dữ liệu realtime giá: → gọi HOSE/HNX API
- Tin tức công ty: → Bloomberg hoặc nguồn khác
- Báo cáo tài chính quarterly: → [ĐIỀN nguồn]
- Foreign ownership data: → [ĐIỀN nguồn]
