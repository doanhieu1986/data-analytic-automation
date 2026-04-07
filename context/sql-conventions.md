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

## 8. Database-specific notes

### PostgreSQL / SQL Server
- Dùng `ILIKE` thay `LIKE` để case-insensitive search
- Window functions: `OVER (PARTITION BY ... ORDER BY ...)`

### BigQuery
- Tên đầy đủ: `project_id.dataset.table_name`
- Partition filter bắt buộc với bảng lớn: `WHERE _PARTITIONDATE = DATE('2024-03-15')`
- Dùng `DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)` thay `CURRENT_DATE - 30`
- Array/Struct: UNNEST khi cần flatten

### Shared conventions
- Không dùng `SELECT *` trong production
- Limit kết quả khi explore: `LIMIT 1000`
- Explain plan trước khi chạy query nặng

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
