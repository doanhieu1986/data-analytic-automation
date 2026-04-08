# SQL Conventions — Quy ước viết SQL

> Claude Code PHẢI tuân theo các quy ước này khi generate SQL.
> Mục tiêu: SQL phải readable, performant, và nhất quán với style của team.

---

## 1. Naming conventions

```sql
-- ✅ Đúng: lowercase, snake_case
SELECT trade_date, ticker, close_price
FROM market_data.ohlcv_daily

-- ❌ Sai: camelCase, UPPERCASE tên cột
SELECT TradeDate, Ticker, ClosePrice
FROM MarketData.OhlcvDaily
```

- **Bảng:** `schema.table_name` — luôn có schema prefix
- **Alias:** ngắn gọn, có nghĩa — `od` cho `ohlcv_daily`, `tx` cho `transactions`
- **CTE:** đặt tên mô tả chức năng — `daily_returns`, `top_accounts`

---

## 2. Cấu trúc query — dùng CTE

```sql
-- ✅ Preferred style: CTE thay vì subquery lồng nhau
WITH
daily_returns AS (
    SELECT
        trade_date,
        ticker,
        close_price,
        LAG(close_price) OVER (PARTITION BY ticker ORDER BY trade_date) AS prev_close,
        (close_price - LAG(close_price) OVER (PARTITION BY ticker ORDER BY trade_date))
            / NULLIF(LAG(close_price) OVER (PARTITION BY ticker ORDER BY trade_date), 0) AS daily_return
    FROM market_data.ohlcv_daily
    WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
),

active_tickers AS (
    SELECT DISTINCT ticker
    FROM market_data.ohlcv_daily
    WHERE trade_date = CURRENT_DATE - 1
      AND volume > 0
)

SELECT
    dr.trade_date,
    dr.ticker,
    dr.daily_return,
    dr.close_price
FROM daily_returns dr
INNER JOIN active_tickers at ON dr.ticker = at.ticker
WHERE dr.daily_return IS NOT NULL
ORDER BY dr.trade_date DESC, ABS(dr.daily_return) DESC
;
```

---

## 3. Formatting rules

```sql
-- Keywords: UPPERCASE
SELECT, FROM, WHERE, JOIN, GROUP BY, ORDER BY, HAVING, WITH, AS, ON, AND, OR, NOT

-- Indent: 4 spaces (không dùng TAB)
SELECT
    column1,
    column2,
    column3
FROM table1

-- Dấu phẩy: đầu dòng (leading comma) — để dễ comment out
SELECT
    trade_date
    , ticker
    , close_price
    , volume

-- Mỗi condition WHERE trên 1 dòng
WHERE trade_date >= '2024-01-01'
  AND ticker IN ('VNM', 'HPG', 'VCB')
  AND volume > 100000
```

---

## 4. Performance rules

```sql
-- ✅ Luôn filter date range trước (partition pruning)
WHERE trade_date BETWEEN '2024-01-01' AND '2024-03-31'

-- ✅ Dùng EXISTS thay vì IN với subquery lớn
WHERE EXISTS (
    SELECT 1 FROM customers c WHERE c.account_id = t.account_id
)

-- ❌ Tránh SELECT * trong production query
SELECT * FROM tick_data  -- BAD: bảng này hàng trăm triệu rows

-- ✅ Chỉ lấy cột cần thiết
SELECT trade_date, ticker, match_price, match_volume
FROM tick_data
WHERE trade_date = CURRENT_DATE

-- ✅ Với bảng lớn (tick_data, transactions): luôn có WHERE trade_date
-- Bảng tick_data có partition theo trade_date
```

---

## 5. Comments trong SQL

```sql
-- Single line comment: mô tả logic phức tạp

/*
 * Block comment: mô tả toàn bộ query
 * Mục đích: Tính top 10 cổ phiếu tăng mạnh nhất tuần
 * Input: trade_date range
 * Output: ticker, weekly_return, volume
 */

-- CTE comments: giải thích từng bước
WITH
-- Bước 1: Lấy giá đóng cửa đầu tuần và cuối tuần
weekly_prices AS (
    ...
),

-- Bước 2: Tính % thay đổi
weekly_returns AS (
    ...
)
```

---

## 6. Xử lý NULL

```sql
-- Dùng COALESCE thay vì CASE WHEN ... IS NULL
SELECT COALESCE(volume, 0) AS volume

-- Tránh chia cho 0 với NULLIF
SELECT value / NULLIF(volume, 0) AS avg_price

-- Filter NULL explicit khi cần
WHERE close_price IS NOT NULL
```

---

## 7. Date/Time handling

```sql
-- Timezone: luôn làm việc với GMT+7
-- BigQuery:
WHERE DATE(DATETIME(created_at, 'Asia/Ho_Chi_Minh')) = CURRENT_DATE

-- PostgreSQL:
WHERE trade_date AT TIME ZONE 'Asia/Ho_Chi_Minh' >= '2024-01-01'

-- Format ngày Việt Nam: DD/MM/YYYY (khi display)
-- Format trong DB: YYYY-MM-DD (ISO 8601)
```

---

## 8. Platform syntax — Bảng so sánh

> Khi generate SQL, **luôn hỏi hoặc chỉ định platform** trước khi viết.
> Output lưu vào `outputs/<task>/<platform>/` để phân biệt rõ.

| Tính năng | Trino | PostgreSQL | Oracle | BigQuery |
|-----------|-------|------------|--------|----------|
| **String match (case-insensitive)** | `LIKE` (case-sensitive) | `ILIKE` | `UPPER(col) LIKE UPPER(...)` | `LIKE` (case-sensitive) |
| **Date literal** | `DATE '2024-01-01'` | `'2024-01-01'::date` | `DATE '2024-01-01'` hoặc `TO_DATE('2024-01-01','YYYY-MM-DD')` | `DATE '2024-01-01'` |
| **Ngày hiện tại** | `CURRENT_DATE` | `CURRENT_DATE` | `TRUNC(SYSDATE)` | `CURRENT_DATE` |
| **Inline value list** | `SELECT v UNION ALL SELECT v` | `SELECT * FROM (VALUES (1,'a'),(2,'b')) t(col1,col2)` | `SELECT v FROM DUAL UNION ALL SELECT v FROM DUAL` | `SELECT v UNION ALL SELECT v` |
| **Giới hạn rows** | `LIMIT n` | `LIMIT n` | `FETCH FIRST n ROWS ONLY` | `LIMIT n` |
| **Null-safe coalesce** | `COALESCE` | `COALESCE` | `COALESCE` hoặc `NVL` | `COALESCE` hoặc `IFNULL` |
| **Tên bảng đầy đủ** | `catalog.schema.table` | `schema.table` | `schema.table` | `project.dataset.table` |
| **CTE** | `WITH ... AS (...)` | `WITH ... AS (...)` | `WITH ... AS (...)` | `WITH ... AS (...)` |
| **Window functions** | Hỗ trợ đầy đủ | Hỗ trợ đầy đủ | Hỗ trợ đầy đủ (10g+) | Hỗ trợ đầy đủ |
| **Partition pruning** | `WHERE data_date = DATE '...'` | `WHERE data_date = '...'::date` | `WHERE data_date = DATE '...'` | `WHERE _PARTITIONDATE = '...'` |
| **String concat** | `\|\|` hoặc `concat()` | `\|\|` hoặc `concat()` | `\|\|` hoặc `concat()` | `\|\|` hoặc `CONCAT()` |

### Quy tắc output theo platform

```
outputs/<YYYY-MM-DD>_<task>/
├── trino/
│   ├── funnel_dropoff.sql
│   └── error_detail.sql
├── postgres/
│   ├── funnel_dropoff.sql
│   └── error_detail.sql
└── oracle/
    ├── funnel_dropoff.sql
    └── error_detail.sql
```

### Lưu ý quan trọng theo platform

**Trino**
- Default catalog/schema cần chỉ định: `hive.bronze.table` hoặc dùng `USE catalog.schema`
- Không hỗ trợ `SELECT` không có `FROM` (khác Oracle/SQL Server)

**PostgreSQL**
- Dùng `ILIKE` cho string matching để tránh lỗi case
- Cast date: `'2024-01-01'::date` hoặc `CAST('2024-01-01' AS DATE)`
- `VALUES` clause gọn hơn `UNION ALL` cho inline lookup table

**Oracle**
- `SELECT` bắt buộc có `FROM` → inline values dùng `FROM DUAL`
- `LIMIT` không tồn tại → thay bằng `FETCH FIRST n ROWS ONLY` (12c+) hoặc `WHERE ROWNUM <= n`
- Unicode: đảm bảo DB charset là `AL32UTF8` nếu dùng tiếng Việt có dấu
- Tránh dùng reserved words làm alias (e.g. `key`, `date`, `comment`)

**BigQuery**
- Tên đầy đủ: `` `project_id.dataset.table` `` (backtick nếu có ký tự đặc biệt)
- Partition filter bắt buộc với bảng lớn: `WHERE _PARTITIONDATE = '2024-03-15'`
- Dùng `DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)` thay `CURRENT_DATE - 30`
- Array/Struct: `UNNEST` khi cần flatten

---

## 9. Template queries thường dùng

### Template: Top N theo metric
```sql
WITH ranked AS (
    SELECT
        ticker,
        [metric],
        RANK() OVER (ORDER BY [metric] DESC) AS rnk
    FROM [table]
    WHERE trade_date = '[date]'
)
SELECT * FROM ranked WHERE rnk <= 10
```

### Template: So sánh kỳ này vs kỳ trước
```sql
WITH
current_period AS (
    SELECT ticker, SUM(volume) AS vol
    FROM ohlcv_daily
    WHERE trade_date BETWEEN '[start1]' AND '[end1]'
    GROUP BY ticker
),
prior_period AS (
    SELECT ticker, SUM(volume) AS vol
    FROM ohlcv_daily
    WHERE trade_date BETWEEN '[start2]' AND '[end2]'
    GROUP BY ticker
)
SELECT
    c.ticker,
    c.vol AS current_vol,
    p.vol AS prior_vol,
    (c.vol - p.vol) * 100.0 / NULLIF(p.vol, 0) AS pct_change
FROM current_period c
LEFT JOIN prior_period p USING (ticker)
ORDER BY pct_change DESC
```
