from __future__ import annotations

"""scripts/generate_phase3_test_data.py
フェーズ3検証シナリオ用のサンプルデータと指示書ファイルを自動生成するスクリプト。

実行例:
    python scripts/generate_phase3_test_data.py
"""

import pandas as pd  # type: ignore
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "sample"
SAMPLE_DIR.mkdir(exist_ok=True)

# ------------------------------
# 1. 売掛金消込シナリオ
# ------------------------------

def create_receivables_files() -> None:
    # deposit_202506.csv
    deposit_df = pd.DataFrame(
        {
            "receipt_no": ["INV-001", "INV-002"],
            "amount": [10000, 15000],
            "deposit_date": ["2025-06-10", "2025-06-11"],
        }
    )
    deposit_df.to_csv(SAMPLE_DIR / "deposit_202506.csv", index=False)

    # billing_202505.xlsx
    billing_df = pd.DataFrame(
        {
            "invoice_number": ["INV-001", "INV-003"],
            "amount": [10000, 20000],
            "billing_date": ["2025-05-25", "2025-05-26"],
        }
    )
    billing_df.to_excel(SAMPLE_DIR / "billing_202505.xlsx", index=False)

    # instruction_reconciliation.md
    instruction_md = (
        "# 売掛金消込 手順\n\n"
        "1. 入金データと請求データを照合してください。\n"
        "2. 突合キーは、入金データの「receipt_no」と請求データの「invoice_number」です。\n"
        "3. 両データの「amount」が完全に一致した場合を「消込済」とします。\n"
        "4. 消込済のデータは reconciled.csv に出力してください。\n"
        "5. それ以外のデータ（未突合、金額不一致）は unreconciled.csv に出力してください。\n"
    )
    (SAMPLE_DIR / "instruction_reconciliation.md").write_text(instruction_md, encoding="utf-8")


def main() -> None:
    create_receivables_files()
    print(f"フェーズ3検証用データを {SAMPLE_DIR} に生成しました。")


if __name__ == "__main__":
    main() 