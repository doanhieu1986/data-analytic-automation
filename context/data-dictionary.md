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

## 1. Dữ liệu nguồn (lakehouse)

### [bronze].cpm_event_raw
**Mô tả:** Dữ liệu hành vi của khách hàng thực hiện trên SmartOne App của VPS
**Database:** [Trino_superset]
**Update frequency:** Daily, sau 22:00
**Nguồn:** Countly

| Column | Type | Nullable | Mô tả | Ví dụ |
|--------|------|----------|-------|-------|
| `key` | VARCHAR(100) | YES | Mã định danh event | oa_registration_vanity |
| `count` | VARCHAR(10) | YES | Số lượng event, mặc định tất cả là 1 | 1 |
| `timestamp` | VARCHAR(10) | YES | Thời gian thực hiện event | 1760595309050 |
| `acountid` | BIGINT | YES | Mã định danh tài khoản khách hàng | H53165 |
| `sessionid` | BIGINT | YES | Mã định danh phiên đăng nhập của khách hàng | 6885EA91E1EE5C1B56B1E334F1A2BAC0 |
| `version_app` | BIGINT | YES | Phiên bản App hoặc Web khách hàng sử dụng | 5.12.35 |
| `did` | BIGINT | YES | Mã định danh thiết bị truy cập (device id) | 98125000000 |
| `user_agent` | TIMESTAMP | YES | chuỗi văn bản đặc trưng được trình duyệt web (như Chrome, Safari) hoặc ứng dụng gửi đến máy chủ khi truy cập trang web | Mozilla/5.0 (Windows NT 10.0; Win64; x64) |
| `app_key` | TIMESTAMP | YES | Mã định danh app để phân biệt các app trên hệ thống Countly | 2024-03-15 17:30:00 |
| `segmentation` | TIMESTAMP | YES | Thông tin mô tả chi tiết của event (như payload trên GA4) | {'error_description': 'Hệ thống bận xử lý thông tin. Quý khách vui lòng thử lại sau ít phút', 'error_code': '-1986'} |
| `data_date` | TIMESTAMP | YES | Ngày event xảy ra | 2025-10-16 |

---

## 2. Lookup / Mapping

### app_key mapping (để mapping trường app_key trong bảng cpm_event_raw)
```
'6168e3f8862b9874c216785f85bc667242323248' - 'SMO_Product'
'366fc43c9c51af029b75759c92c50704f682a2e7' - 'SMO_Web_Product'
'8ea6ed739abe65cc81e1c7c257c40c9b687fcbac' - 'SMO_Web_SMP_Product'
'c8012556dc612e8ef8eec9988bbbd1fcf4e67fac' - 'SMO_Web_banggia_Product'
'cea1780ca2bf534dff9175ea791b743593b40d3f' - 'OpenAccount_product'
'9ed68bc0c88cc2c4164a67cf7c04e43d4a424114' - 'SMO_Web_Viettel'
'51e21d8ee8a88c208c08048d4d2abbb6a0fb612f' - 'SMP_Product'
'9c0e579d58d3dab15f69021fe184e427f3c92dde' - 'AIPRO_Prod'
```