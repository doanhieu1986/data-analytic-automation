"""
SQL Generator — Natural Language to SQL
Dùng Claude API để convert câu hỏi tiếng Việt/English thành SQL query.

Usage:
    python sql_generator.py "Top 10 cổ phiếu tăng mạnh nhất tuần này"
    python sql_generator.py --question "..." --db bigquery --save
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import structlog

log = structlog.get_logger()

PROJECT_ROOT = Path(__file__).parent.parent
CONTEXT_DIR = PROJECT_ROOT / "context"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def load_context_files() -> str:
    """
    Load các file context để đưa vào system prompt.
    Đây là phần quan trọng nhất — Claude cần biết schema để generate SQL đúng.
    """
    context_parts = []

    # 1. Data dictionary (quan trọng nhất)
    dd_path = CONTEXT_DIR / "data-dictionary.md"
    if dd_path.exists():
        context_parts.append(f"## Data Dictionary\n\n{dd_path.read_text(encoding='utf-8')}")

    # 2. SQL conventions
    sql_conv_path = CONTEXT_DIR / "sql-conventions.md"
    if sql_conv_path.exists():
        context_parts.append(f"## SQL Conventions\n\n{sql_conv_path.read_text(encoding='utf-8')}")

    # 3. Business rules
    br_path = CONTEXT_DIR / "business-rules.md"
    if br_path.exists():
        context_parts.append(f"## Business Rules\n\n{br_path.read_text(encoding='utf-8')}")

    # 4. Schemas (nếu có)
    for schema_file in CONTEXT_DIR.glob("schemas/**/*.sql"):
        context_parts.append(f"## Schema: {schema_file.name}\n\n```sql\n{schema_file.read_text()}\n```")

    return "\n\n---\n\n".join(context_parts)


def build_system_prompt(db_type: str = "postgres") -> str:
    """Xây dựng system prompt đầy đủ cho Claude."""
    context = load_context_files()
    today = datetime.now().strftime("%Y-%m-%d")

    return f"""Bạn là SQL expert cho team Data Analytics của một công ty chứng khoán Việt Nam.
Nhiệm vụ: Chuyển câu hỏi tiếng Việt hoặc tiếng Anh thành SQL query chính xác.

**Database target:** {db_type}
**Today's date:** {today} (Timezone: Asia/Ho_Chi_Minh, GMT+7)

**Quy tắc bắt buộc:**
1. Chỉ dùng các bảng và cột CÓ TRONG Data Dictionary bên dưới
2. Nếu không tìm được bảng/cột phù hợp, nói rõ thay vì đoán
3. Tuân thủ SQL Conventions (CTE, naming, formatting)
4. Luôn filter trade_date khi query bảng tick_data và ohlcv_daily
5. Xử lý NULL và chia cho 0 (dùng NULLIF)
6. Comment giải thích logic phức tạp

**Output format:**
```sql
-- Query: [câu hỏi gốc]
-- Assumptions: [giả định nếu có]
-- Database: {db_type}
[SQL query]
```

Sau SQL, giải thích ngắn gọn logic và các assumption bằng tiếng Việt.

---

{context}
"""


def generate_sql(question: str, db_type: str = "postgres") -> dict:
    """
    Call Claude API để generate SQL từ câu hỏi tự nhiên.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system_prompt = build_system_prompt(db_type)
    log.info("generating_sql", question=question, db_type=db_type)

    message = client.messages.create(
        model="claude-sonnet-4-6",  # Dùng Sonnet cho tốc độ, đổi sang Opus cho độ chính xác cao hơn
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Generate SQL for: {question}"}
        ],
    )

    response_text = message.content[0].text

    # Parse SQL từ response (extract code block)
    sql = ""
    explanation = ""
    if "```sql" in response_text:
        parts = response_text.split("```sql")
        if len(parts) > 1:
            sql = parts[1].split("```")[0].strip()
            explanation = parts[-1].strip() if len(parts) > 1 else ""
    else:
        sql = response_text  # fallback

    result = {
        "question": question,
        "db_type": db_type,
        "sql": sql,
        "explanation": explanation,
        "full_response": response_text,
        "generated_at": datetime.now().isoformat(),
        "model": "claude-sonnet-4-6",
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    log.info("sql_generated",
             sql_lines=len(sql.splitlines()),
             tokens_used=message.usage.output_tokens)

    return result


def save_result(result: dict, output_dir: Path = None):
    """Lưu kết quả ra file."""
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_dir = OUTPUTS_DIR / f"{date_str}_sql"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save SQL file
    sql_path = output_dir / "query.sql"
    sql_path.write_text(result["sql"], encoding="utf-8")

    # Save full response
    import json
    json_path = output_dir / "result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info("result_saved", sql_path=str(sql_path))
    return sql_path


def main():
    parser = argparse.ArgumentParser(description="Natural Language to SQL Generator")
    parser.add_argument("question", nargs="?", help="Câu hỏi bằng tiếng Việt hoặc English")
    parser.add_argument("--question", "-q", dest="question_flag", help="Câu hỏi (alternative)")
    parser.add_argument(
        "--db",
        choices=["postgres", "bigquery", "redshift", "sqlserver"],
        default="postgres",
        help="Target database",
    )
    parser.add_argument("--save", action="store_true", help="Lưu kết quả ra file")
    args = parser.parse_args()

    question = args.question or args.question_flag
    if not question:
        parser.print_help()
        sys.exit(1)

    # Generate
    result = generate_sql(question, db_type=args.db)

    # Print output
    print("\n" + "=" * 60)
    print(f"Question: {result['question']}")
    print("=" * 60)
    print("\n📝 Generated SQL:\n")
    print(result["sql"])
    print("\n💬 Explanation:\n")
    print(result["explanation"])
    print(f"\n📊 Tokens used: {result['input_tokens']} in / {result['output_tokens']} out")

    if args.save:
        sql_path = save_result(result)
        print(f"\n✅ Saved to: {sql_path}")


if __name__ == "__main__":
    main()
