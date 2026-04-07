"""
Data Quality Scanner
Scan data quality cho bảng DB hoặc DataFrame và tạo báo cáo.

Usage:
    python dq_scanner.py --table schema.ohlcv_daily
    python dq_scanner.py --table schema.ohlcv_daily --date 2024-03-15 --full
"""

import argparse
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd
import structlog

log = structlog.get_logger()
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


@dataclass
class DQIssue:
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    check_name: str
    column: str
    description: str
    affected_count: int = 0
    affected_pct: float = 0.0
    sample_values: list = field(default_factory=list)


class DQScanner:
    """Data Quality Scanner — chạy các checks theo cấu hình."""

    def __init__(self, df: pd.DataFrame, table_name: str):
        self.df = df
        self.table_name = table_name
        self.issues: list[DQIssue] = []
        self.n_rows = len(df)

    def check_completeness(self, columns: list[str] = None, thresholds: dict = None):
        """
        Check tỷ lệ NULL của từng cột.
        thresholds: {"col_name": max_null_pct} — ví dụ {"close_price": 0.01}
        """
        cols = columns or self.df.columns.tolist()
        thresholds = thresholds or {}

        for col in cols:
            if col not in self.df.columns:
                continue
            null_count = int(self.df[col].isna().sum())
            null_pct = null_count / self.n_rows if self.n_rows > 0 else 0
            max_allowed = thresholds.get(col, 0.05)  # default 5%

            if null_count > 0:
                severity = "CRITICAL" if null_pct > max_allowed else "WARNING"
                self.issues.append(DQIssue(
                    severity=severity,
                    check_name="completeness",
                    column=col,
                    description=f"NULL values: {null_count:,} ({null_pct:.2%})",
                    affected_count=null_count,
                    affected_pct=round(null_pct * 100, 2),
                ))

        return self

    def check_range(self, rules: dict):
        """
        Check giá trị nằm trong range hợp lệ.
        rules: {"col_name": {"min": 0, "max": 1000000}}

        Ví dụ cho securities domain:
        {
            "close_price": {"min": 100, "max": 10_000_000},
            "volume": {"min": 0},
            "match_price": {"min": 0},
        }
        """
        for col, rule in rules.items():
            if col not in self.df.columns:
                continue
            series = self.df[col].dropna()

            if "min" in rule:
                below_min = series[series < rule["min"]]
                if len(below_min) > 0:
                    self.issues.append(DQIssue(
                        severity="CRITICAL",
                        check_name="range_check",
                        column=col,
                        description=f"Values below minimum {rule['min']}: {len(below_min):,} rows",
                        affected_count=len(below_min),
                        affected_pct=round(len(below_min) / self.n_rows * 100, 2),
                        sample_values=below_min.head(5).tolist(),
                    ))

            if "max" in rule:
                above_max = series[series > rule["max"]]
                if len(above_max) > 0:
                    self.issues.append(DQIssue(
                        severity="WARNING",
                        check_name="range_check",
                        column=col,
                        description=f"Values above maximum {rule['max']}: {len(above_max):,} rows",
                        affected_count=len(above_max),
                        affected_pct=round(len(above_max) / self.n_rows * 100, 2),
                        sample_values=above_max.head(5).tolist(),
                    ))

        return self

    def check_enum(self, rules: dict):
        """
        Check giá trị nằm trong allowed values.
        rules: {"side": ["B", "S"], "status": ["ACTIVE", "INACTIVE"]}
        """
        for col, allowed in rules.items():
            if col not in self.df.columns:
                continue
            invalid = self.df[~self.df[col].isin(allowed) & self.df[col].notna()]
            if len(invalid) > 0:
                self.issues.append(DQIssue(
                    severity="CRITICAL",
                    check_name="enum_check",
                    column=col,
                    description=f"Invalid values (expected: {allowed}): {len(invalid):,} rows",
                    affected_count=len(invalid),
                    affected_pct=round(len(invalid) / self.n_rows * 100, 2),
                    sample_values=invalid[col].unique()[:5].tolist(),
                ))

        return self

    def check_duplicates(self, subset: list[str] = None):
        """Check duplicate rows theo subset của columns."""
        dup_mask = self.df.duplicated(subset=subset, keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            severity = "CRITICAL" if dup_count > self.n_rows * 0.001 else "WARNING"
            cols_desc = f"[{', '.join(subset)}]" if subset else "all columns"
            self.issues.append(DQIssue(
                severity=severity,
                check_name="uniqueness",
                column=cols_desc,
                description=f"Duplicate rows: {dup_count:,} ({dup_count/self.n_rows:.2%})",
                affected_count=dup_count,
                affected_pct=round(dup_count / self.n_rows * 100, 2),
            ))

        return self

    def check_ohlcv_logic(self):
        """
        Check logic nghiệp vụ cho bảng OHLCV.
        high >= close >= low (không phải lúc nào cũng đúng do ATO/ATC)
        """
        required = ["high_price", "low_price", "close_price", "open_price"]
        if not all(c in self.df.columns for c in required):
            return self

        # high < low (luôn là lỗi)
        invalid = self.df[self.df["high_price"] < self.df["low_price"]]
        if len(invalid) > 0:
            self.issues.append(DQIssue(
                severity="CRITICAL",
                check_name="ohlcv_logic",
                column="high_price/low_price",
                description=f"high_price < low_price: {len(invalid):,} rows",
                affected_count=len(invalid),
                affected_pct=round(len(invalid) / self.n_rows * 100, 2),
            ))

        return self

    def get_report(self) -> dict:
        """Tổng hợp kết quả."""
        critical = [i for i in self.issues if i.severity == "CRITICAL"]
        warnings = [i for i in self.issues if i.severity == "WARNING"]

        return {
            "table": self.table_name,
            "scanned_at": datetime.now().isoformat(),
            "rows_scanned": self.n_rows,
            "summary": {
                "total_issues": len(self.issues),
                "critical": len(critical),
                "warnings": len(warnings),
            },
            "issues": [asdict(i) for i in self.issues],
            "passed": len(self.issues) == 0,
        }


# ── Preset configs per table ──────────────────────────────────────────────────

OHLCV_CONFIG = {
    "completeness_thresholds": {
        "trade_date": 0.0,
        "ticker": 0.0,
        "close_price": 0.01,
        "volume": 0.01,
    },
    "range_rules": {
        "close_price": {"min": 100},
        "open_price": {"min": 100},
        "high_price": {"min": 100},
        "low_price": {"min": 100},
        "volume": {"min": 0},
    },
}

TRANSACTION_CONFIG = {
    "completeness_thresholds": {
        "order_id": 0.0,
        "trade_date": 0.0,
        "account_id": 0.0,
        "ticker": 0.0,
        "side": 0.0,
    },
    "enum_rules": {
        "side": ["B", "S"],
        "status": ["MATCHED", "PENDING", "CANCELLED", "REJECTED"],
    },
    "range_rules": {
        "order_price": {"min": 0},
        "order_volume": {"min": 1},
        "fee": {"min": 0},
        "tax": {"min": 0},
    },
}


def run_scan(df: pd.DataFrame, table_name: str, config: dict = None) -> dict:
    """Chạy DQ scan với config cho trước."""
    config = config or {}
    scanner = DQScanner(df, table_name)

    scanner.check_completeness(thresholds=config.get("completeness_thresholds", {}))
    if config.get("range_rules"):
        scanner.check_range(config["range_rules"])
    if config.get("enum_rules"):
        scanner.check_enum(config["enum_rules"])
    scanner.check_duplicates(subset=config.get("pk_columns"))

    # Chạy domain-specific checks
    if "ohlcv" in table_name.lower():
        scanner.check_ohlcv_logic()

    return scanner.get_report()


def save_report(report: dict, output_dir: Path):
    """Lưu báo cáo DQ."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    json_path = output_dir / "dq_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Markdown summary
    md_lines = [
        f"# Data Quality Report — {report['table']}",
        f"*Scanned: {report['scanned_at']} | Rows: {report['rows_scanned']:,}*",
        "",
        f"## Summary",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| 🔴 CRITICAL | {report['summary']['critical']} |",
        f"| 🟡 WARNING | {report['summary']['warnings']} |",
        "",
        "## Issues",
    ]

    for issue in report["issues"]:
        icon = "🔴" if issue["severity"] == "CRITICAL" else "🟡"
        md_lines.append(
            f"- {icon} **{issue['column']}** ({issue['check_name']}): {issue['description']}"
        )

    if not report["issues"]:
        md_lines.append("✅ All checks passed")

    (output_dir / "dq_summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    log.info("dq_report_saved", path=str(output_dir), issues=report["summary"]["total_issues"])


def main():
    parser = argparse.ArgumentParser(description="Data Quality Scanner")
    parser.add_argument("--table", required=True, help="Table name (schema.table)")
    parser.add_argument("--date", help="Date filter (YYYY-MM-DD)")
    parser.add_argument("--full", action="store_true", help="Scan toàn bộ bảng (không filter date)")
    args = parser.parse_args()

    # TODO: load data from DB (xem eda_runner.py để copy hàm load_from_db)
    # df = load_from_db(table=args.table, date=args.date)

    # Placeholder — thay bằng load thực tế
    log.info("dq_scan_start", table=args.table, date=args.date)

    # Chọn config theo tên bảng
    if "ohlcv" in args.table:
        config = OHLCV_CONFIG
    elif "transaction" in args.table:
        config = TRANSACTION_CONFIG
    else:
        config = {}

    # Tạo output directory
    date_str = datetime.now().strftime("%Y-%m-%d")
    table_short = args.table.replace(".", "_")
    output_dir = OUTPUTS_DIR / f"{date_str}_dq_{table_short}"

    # run_scan + save (với df thực tế)
    # report = run_scan(df, args.table, config)
    # save_report(report, output_dir)
    print(f"✅ DQ config loaded for {args.table}. Connect to DB and call run_scan() to execute.")
    print(f"   Output will be saved to: {output_dir}")


if __name__ == "__main__":
    main()
