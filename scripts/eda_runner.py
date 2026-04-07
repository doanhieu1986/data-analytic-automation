"""
EDA Runner — Automated Exploratory Data Analysis
Chạy EDA trên bảng dữ liệu hoặc file CSV/Parquet và export report.

Usage:
    python eda_runner.py --table schema.ohlcv_daily --date 2024-03-15
    python eda_runner.py --file data/sample.csv
    python eda_runner.py --query "SELECT * FROM ohlcv_daily WHERE trade_date='2024-03-15'"
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import structlog

# ── Logging setup ────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
log = structlog.get_logger()

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def load_from_file(file_path: str) -> pd.DataFrame:
    """Load data từ CSV, Excel, hoặc Parquet."""
    path = Path(file_path)
    log.info("loading_file", path=str(path), suffix=path.suffix)

    if path.suffix == ".csv":
        return pd.read_csv(path)
    elif path.suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif path.suffix == ".parquet":
        return pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")


def load_from_db(table: str = None, query: str = None, date: str = None) -> pd.DataFrame:
    """
    Load data từ database.
    TODO: Implement kết nối DB thực tế theo config trong CLAUDE.md
    """
    import sqlalchemy

    # Lấy connection string từ env vars (xem CLAUDE.md section 5)
    db_url = (
        f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASS']}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )
    engine = sqlalchemy.create_engine(db_url)

    if query:
        log.info("loading_query", query=query[:100])
        return pd.read_sql(query, engine)
    elif table:
        sql = f"SELECT * FROM {table}"
        if date:
            # Assume có cột trade_date — điều chỉnh theo schema thực tế
            sql += f" WHERE trade_date = '{date}'"
        sql += " LIMIT 500000"  # Safety limit
        log.info("loading_table", table=table, date=date)
        return pd.read_sql(sql, engine)
    else:
        raise ValueError("Phải chỉ định table hoặc query")


def run_eda(df: pd.DataFrame, dataset_name: str, output_dir: Path) -> dict:
    """
    Chạy EDA đầy đủ và trả về dict findings.
    """
    log.info("eda_start", shape=df.shape, dataset=dataset_name)
    findings = {
        "dataset": dataset_name,
        "run_at": datetime.now().isoformat(),
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "issues": [],
        "summary": {},
    }

    # 1. Basic info
    findings["columns"] = {
        col: {
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isna().sum()),
            "null_pct": round(df[col].isna().mean() * 100, 2),
            "unique_count": int(df[col].nunique()),
        }
        for col in df.columns
    }

    # 2. Flag high null columns (> 20%)
    for col, info in findings["columns"].items():
        if info["null_pct"] > 20:
            findings["issues"].append({
                "severity": "WARNING",
                "column": col,
                "issue": f"High null rate: {info['null_pct']}%",
            })

    # 3. Numeric stats
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if numeric_cols:
        desc = df[numeric_cols].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
        findings["numeric_stats"] = desc.to_dict()

    # 4. Duplicate check
    dup_count = int(df.duplicated().sum())
    findings["duplicate_rows"] = dup_count
    if dup_count > 0:
        findings["issues"].append({
            "severity": "WARNING" if dup_count < len(df) * 0.01 else "CRITICAL",
            "issue": f"Duplicate rows: {dup_count} ({dup_count/len(df)*100:.2f}%)",
        })

    # 5. Categorical value counts (top 20)
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    findings["categorical_summary"] = {}
    for col in cat_cols[:10]:  # limit to 10 cols
        findings["categorical_summary"][col] = df[col].value_counts().head(20).to_dict()

    # 6. Generate HTML report (ydata-profiling)
    try:
        from ydata_profiling import ProfileReport
        profile = ProfileReport(df, title=f"EDA: {dataset_name}", minimal=False)
        html_path = output_dir / "report.html"
        profile.to_file(html_path)
        log.info("profile_report_saved", path=str(html_path))
        findings["html_report"] = str(html_path)
    except ImportError:
        log.warning("ydata_profiling_not_installed", hint="pip install ydata-profiling")
        # Fallback: basic HTML từ pandas
        html_path = output_dir / "report.html"
        df.describe(include="all").to_html(html_path)
        findings["html_report"] = str(html_path)

    # 7. Save findings JSON
    json_path = output_dir / "findings.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2, default=str)

    # 8. Generate summary Markdown
    _write_summary_md(findings, output_dir)

    log.info("eda_complete", issues=len(findings["issues"]), output=str(output_dir))
    return findings


def _write_summary_md(findings: dict, output_dir: Path):
    """Viết báo cáo tóm tắt dạng Markdown."""
    md_lines = [
        f"# EDA Report — {findings['dataset']}",
        f"*Run: {findings['run_at']}*",
        "",
        f"**Rows:** {findings['shape']['rows']:,} | **Columns:** {findings['shape']['columns']}",
        f"**Duplicate rows:** {findings.get('duplicate_rows', 'N/A')}",
        "",
        "## Issues Found",
    ]

    issues = findings.get("issues", [])
    if issues:
        critical = [i for i in issues if i["severity"] == "CRITICAL"]
        warnings = [i for i in issues if i["severity"] == "WARNING"]
        md_lines.append(f"🔴 Critical: {len(critical)} | 🟡 Warning: {len(warnings)}")
        md_lines.append("")
        for issue in issues:
            icon = "🔴" if issue["severity"] == "CRITICAL" else "🟡"
            col = issue.get("column", "")
            md_lines.append(f"- {icon} **{col}**: {issue['issue']}")
    else:
        md_lines.append("✅ No issues found")

    md_lines += [
        "",
        "## Column Summary",
        "| Column | Type | Null% | Unique |",
        "|--------|------|-------|--------|",
    ]
    for col, info in findings.get("columns", {}).items():
        md_lines.append(
            f"| {col} | {info['dtype']} | {info['null_pct']}% | {info['unique_count']:,} |"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="EDA Runner")
    parser.add_argument("--file", help="Path to CSV/Excel/Parquet file")
    parser.add_argument("--table", help="DB table (schema.table_name)")
    parser.add_argument("--query", help="Custom SQL query")
    parser.add_argument("--date", help="Date filter (YYYY-MM-DD)", default=None)
    parser.add_argument("--name", help="Dataset name for output folder", default=None)
    args = parser.parse_args()

    # Determine dataset name
    if args.name:
        dataset_name = args.name
    elif args.file:
        dataset_name = Path(args.file).stem
    elif args.table:
        dataset_name = args.table.replace(".", "_")
    else:
        dataset_name = "custom_query"

    # Create output directory
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    output_dir = OUTPUTS_DIR / f"{date_prefix}_eda_{dataset_name}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    if args.file:
        df = load_from_file(args.file)
    elif args.table or args.query:
        df = load_from_db(table=args.table, query=args.query, date=args.date)
    else:
        parser.print_help()
        sys.exit(1)

    # Run EDA
    findings = run_eda(df, dataset_name, output_dir)

    print(f"\n✅ EDA complete. Output: {output_dir}")
    print(f"   Issues: {len(findings['issues'])}")
    print(f"   Report: {output_dir}/report.html")


if __name__ == "__main__":
    main()
