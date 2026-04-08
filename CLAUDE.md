# Data Analytics Automation — CLAUDE.md
# Context file cho Claude Code. Đọc file này trước khi làm bất kỳ task nào.

## 1. Tổng quan dự án

Đây là hệ thống automation phân tích dữ liệu cho **team Data Analytics** của một công ty chứng khoán Việt Nam.

**Mục tiêu chính:**
- Tự động hóa EDA (Exploratory Data Analysis) trên các dataset mới
- Scan data quality và báo cáo vấn đề dữ liệu
- Xử lý và transform dữ liệu từ nhiều nguồn
- Generate SQL từ natural language query (Text-to-SQL)
- Tự động rút ra insight từ dữ liệu thị trường và nội bộ

**Tech stack:**
- Orchestration: Antigravity (internal platform) + n8n
- AI: Claude Code (agentic), Claude API (programmatic)
- Database: PostgreSQL / SQL Server (OLTP), BigQuery / Redshift / Snowflake (DWH)
- File sources: CSV, Excel, Parquet (từ sàn, đối tác)
- Market data: HOSE, HNX, Bloomberg API

---

## 2. Cấu trúc thư mục

```
data-analytic-automation/
├── CLAUDE.md                    ← File này (đọc trước tiên)
├── context/
│   ├── business-rules.md        ← Nghiệp vụ chứng khoán, định nghĩa KPI
│   ├── data-dictionary.md       ← Từ điển dữ liệu: bảng, cột, ý nghĩa
│   ├── sql-conventions.md       ← Quy ước viết SQL + bảng so sánh platform
│   └── flows/                   ← Logic nghiệp vụ từng luồng (đọc khi generate code)
│       └── oa_logic.md          ← Luồng mở tài khoản: 7 bước, drop-off, lỗi
├── scripts/
│   ├── eda_runner.py            ← Script EDA tự động
│   ├── dq_scanner.py            ← Script data quality
│   └── sql_generator.py         ← Text-to-SQL với context
├── n8n/
│   └── workflows/               ← n8n workflow JSON exports
└── outputs/                     ← Kết quả SQL queries và báo cáo được generate ra
    └── YYYY-MM-DD_<task>/       ← Mỗi task một thư mục có timestamp
        ├── data_flow.md         ← Mô tả luồng xử lý dữ liệu + Mermaid diagram (luôn tạo kèm)
        ├── trino/               ← SQL cho Trino engine
        ├── postgres/            ← SQL cho PostgreSQL
        └── oracle/              ← SQL cho Oracle
```

---

## 3. Nguyên tắc làm việc

### Khi làm việc với data
- **LUÔN** đọc `context/data-dictionary.md` trước khi viết SQL hoặc query
- **LUÔN** đọc `context/business-rules.md` khi diễn giải số liệu
- Không assume tên cột — kiểm tra schema thực tế trong `context/schemas/`
- Với dữ liệu thị trường: timezone là **GMT+7 (Việt Nam)**, ngày giao dịch theo lịch HOSE

### Khi generate SQL
- Tuân thủ `context/sql-conventions.md`
- **Luôn hỏi hoặc xác nhận platform** trước khi viết: Trino / PostgreSQL / Oracle / BigQuery
- Tạo file trong `outputs/<YYYY-MM-DD>_<task>/<platform>/`
- Nếu cần nhiều platform: tạo subfolder riêng cho từng cái, không viết chung 1 file
- **Luôn tạo kèm `data_flow.md`** trong thư mục task: mô tả từng bước xử lý (CTE), ánh xạ về logic nghiệp vụ, kèm Mermaid diagram
- Dùng CTEs thay vì subquery lồng nhau
- Luôn có comment giải thích logic phức tạp
- Kiểm tra xem table tồn tại trong schema trước khi dùng

### Khi viết Python
- Python version: **3.11+**
- Package quản lý bằng: **[pip / poetry / uv — điền vào]**
- Logging dùng `structlog`, không dùng `print()`
- Kết quả EDA/DQ export ra `outputs/` với timestamp

### Output format
- Báo cáo EDA: Markdown + HTML (dùng ydata-profiling hoặc pandas)
- Data quality report: JSON + Markdown summary
- SQL generated: file `.sql` + explain plan
- Insight: Markdown với section Headers rõ ràng

---

## 4. Domain knowledge — Chứng khoán Việt Nam

### Thời gian giao dịch
- HOSE: 09:00–11:30 và 13:00–14:45 (ATO/ATC riêng)
- HNX: 09:00–11:30 và 13:00–14:45
- Phiên ATO: 09:00–09:15 | Phiên ATC: 14:30–14:45

### Các bảng dữ liệu cốt lõi (điền vào theo thực tế)
| Tên bảng | Mô tả | Database |
|---|---|---|
| `tick_data` | Dữ liệu giá từng tick | [ĐIỀN] |
| `ohlcv_daily` | OHLCV ngày | [ĐIỀN] |
| `account_portfolio` | Danh mục khách hàng | [ĐIỀN] |
| `transactions` | Lịch sử giao dịch | [ĐIỀN] |
| `customer_info` | Thông tin KH | [ĐIỀN] |

### KPI quan trọng (điền theo định nghĩa nội bộ)
- **NAV**: Net Asset Value — [công thức]
- **P&L**: Realized/Unrealized — [công thức]
- **Margin ratio**: [công thức]
- **Trading volume**: [định nghĩa khớp lệnh/đặt lệnh]

---

## 5. Kết nối dữ liệu

### PostgreSQL / SQL Server
```python
# Dùng biến môi trường, không hardcode
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ["DB_PORT"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
```

### BigQuery / DWH
```python
PROJECT_ID = os.environ["GCP_PROJECT_ID"]
DATASET = os.environ["BQ_DATASET"]
```

### Market Data API
```python
MARKET_API_KEY = os.environ["MARKET_API_KEY"]
MARKET_API_BASE = os.environ["MARKET_API_BASE_URL"]
```

**Credentials file:** `.env` (không commit lên git) — xem `.env.example`

---

## 6. Antigravity Integration

> **TODO:** Điền thông tin về Antigravity platform
>
> - Antigravity là gì? (scheduler? data platform? pipeline tool?)
> - Cách trigger job từ Antigravity
> - Cách đọc/ghi data qua Antigravity
> - API endpoints hoặc SDK usage

---

## 7. n8n Integration

n8n dùng để orchestrate các tác vụ automation và trigger Claude Code/scripts:

- Webhook trigger → gọi script Python
- Schedule trigger → chạy EDA/DQ định kỳ
- HTTP Request node → gọi Claude API trực tiếp

Xem workflows JSON trong `n8n/workflows/`.

**n8n base URL:** `[ĐIỀN URL n8n instance]`

---

## 8. Files quan trọng cần đọc thêm

Khi nhận task, đọc theo thứ tự:
1. File này (`CLAUDE.md`) — luôn đọc trước
2. `context/data-dictionary.md` — khi làm việc với data
3. `context/business-rules.md` — khi diễn giải/phân tích
4. `context/flows/<tên_luồng>_logic.md` — khi task đề cập đến một luồng nghiệp vụ cụ thể
5. `context/sql-conventions.md` — khi generate SQL

---

## 9. Câu hỏi thường gặp khi Claude Code bị confused

**Q: Table/column tên gì?**
→ Đọc `context/data-dictionary.md` và `context/schemas/`

**Q: Số liệu này tính thế nào?**
→ Đọc `context/business-rules.md`

**Q: Output lưu ở đâu?**
→ Thư mục `outputs/` với format `outputs/YYYY-MM-DD_task-name/`

**Q: Khi nào dùng DWH, khi nào dùng PostgreSQL?**
→ OLTP (realtime, transactional): PostgreSQL/SQL Server
→ Analytics, historical, aggregation: DWH (BigQuery/Redshift)
