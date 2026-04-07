# n8n Workflows — Data Analytics Automation

## Tổng quan

n8n là lớp orchestration kết nối các automation triggers với Python scripts và Claude API.

## Architecture

```
Trigger (Schedule / Webhook / Manual)
    ↓
n8n Workflow
    ↓
HTTP Request → Python Script (trên server)
    OR
HTTP Request → Claude API (claude-opus-4-6 hoặc claude-sonnet-4-6)
    ↓
Output → Database / Slack / Email / File
```

---

## Workflow 1: Daily EDA Report (scheduled)

**Trigger:** Hàng ngày lúc 08:00 sáng (sau khi DWH load xong)
**File:** `daily_eda_report.json`

```
[Cron: 0 8 * * 1-5]
    → Execute Command: python scripts/eda_runner.py --table ohlcv_daily --date {{$today}}
    → IF success → Send Slack notification + upload report
    → IF error → Send alert to #data-alerts
```

**n8n nodes cần:**
- Schedule Trigger
- Execute Command (hoặc HTTP Request nếu scripts chạy trên server khác)
- IF node
- Slack node
- Email node

---

## Workflow 2: Data Quality Scan (scheduled)

**Trigger:** Hàng ngày lúc 17:30 sau khi market close
**File:** `daily_dq_scan.json`

```
[Cron: 30 17 * * 1-5]
    → Loop qua list tables cần check
    → Execute: python scripts/dq_scanner.py --table {{table}}
    → Aggregate results
    → IF có CRITICAL issue → alert ngay lên Slack #data-critical
    → Else → daily summary report
```

---

## Workflow 3: Natural Language SQL (webhook)

**Trigger:** Webhook từ UI nội bộ hoặc Slack slash command
**File:** `nl_sql_webhook.json`

```
[POST /webhook/sql]
    body: { "question": "...", "user": "...", "db": "..." }
    ↓
HTTP Request → Claude API
    body: question + schema context
    ↓
Return generated SQL + explanation
    ↓
Log to analytics DB (track usage)
```

**Sample HTTP Request node config:**
```json
{
  "method": "POST",
  "url": "https://api.anthropic.com/v1/messages",
  "headers": {
    "x-api-key": "{{$env.ANTHROPIC_API_KEY}}",
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
  },
  "body": {
    "model": "claude-sonnet-4-6",
    "max_tokens": 2000,
    "system": "[paste nội dung từ context/sql-conventions.md + data-dictionary.md]",
    "messages": [
      {
        "role": "user",
        "content": "Generate SQL for: {{$json.question}}"
      }
    ]
  }
}
```

---

## Workflow 4: Insight Report (scheduled + on-demand)

**Trigger:** Hàng ngày lúc 15:30 (sau ATC) + manual trigger
**File:** `insight_report.json`

```
[Cron: 30 15 * * 1-5]
    → python scripts/insight_engine.py --type market --date {{$today}}
    → Format output thành Markdown
    → Send to Slack #daily-insight
    → Save to shared drive / Confluence
```

---

## Environment variables cần set trong n8n

```
ANTHROPIC_API_KEY=sk-ant-...
DB_HOST=...
DB_PORT=5432
DB_NAME=...
DB_USER=...
DB_PASS=...
GCP_PROJECT_ID=...
BQ_DATASET=...
SLACK_BOT_TOKEN=...
SCRIPTS_BASE_PATH=/path/to/data-analytic-automation/scripts
```

---

## Tips khi build n8n workflows

1. **Error handling:** Luôn add Error Trigger node ở level workflow
2. **Idempotency:** Script phải an toàn khi chạy lại (không tạo duplicate)
3. **Logging:** Dùng n8n execution history để debug
4. **Testing:** Tạo "test" version của mỗi workflow với data sample nhỏ
5. **Secrets:** Lưu credentials vào n8n Credentials, không hardcode trong workflow JSON
