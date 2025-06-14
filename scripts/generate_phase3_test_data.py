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


def create_inventory_files() -> None:
    """在庫棚卸照合シナリオ用のファイルを生成"""
    # system_inventory.csv
    system_df = pd.DataFrame(
        {
            "sku_code": ["SKU-A01", "SKU-B02"],
            "product_name": ["商品A", "商品B"],
            "system_quantity": [100, 50],
        }
    )
    system_df.to_csv(SAMPLE_DIR / "system_inventory.csv", index=False)

    # physical_inventory.xlsx
    physical_df = pd.DataFrame(
        {
            "sku": ["SKU-A01", "SKU-B02"],
            "name": ["商品A", "商品B"],
            "actual_quantity": [98, 50],
        }
    )
    physical_df.to_excel(SAMPLE_DIR / "physical_inventory.xlsx", index=False)

    # instruction_inventory.md
    instruction_md = (
        "# 在庫棚卸照合\n\n"
        "- 突合キー: 理論在庫の「sku_code」と実在庫の「sku」\n"
        "- 検証項目: 「system_quantity」と「actual_quantity」\n"
        "- 許容範囲: 数量の差異が±2%以内の場合は、許容範囲内とみなし、差異なしとして扱うこと。\n"
        "- 出力: 許容範囲を超える差異があったデータのみを`discrepancy_report.csv`に出力すること。\n"
    )
    (SAMPLE_DIR / "instruction_inventory.md").write_text(instruction_md, encoding="utf-8")


def create_hr_files() -> None:
    """人事マスタ突合シナリオ用のファイルを生成"""
    # hr_master.csv
    master_df = pd.DataFrame(
        {
            "employee_id": [1001, 1002],
            "full_name": ["鈴木一郎", "田中二郎"],
            "department_code": ["D01", "D02"],
            "title_code": ["T03", "T04"],
        }
    )
    master_df.to_csv(SAMPLE_DIR / "hr_master.csv", index=False)

    # dev_dept_list.xlsx
    dept_df = pd.DataFrame(
        {
            "emp_id": [1001, 1002],
            "name": ["鈴木一郎", "田中二郎"],
            "dept": ["D02", "D02"],
            "title_code": ["T03", "T05"],
        }
    )
    dept_df.to_excel(SAMPLE_DIR / "dev_dept_list.xlsx", index=False)

    # instruction_hr_validation.md
    instruction_md = (
        "# 人事データ検証手順\n\n"
        "- 突合キー: `employee_id` と `emp_id`\n"
        "- 検証項目:\n"
        "    1. `department_code` (所属部署)\n"
        "    2. `title_code` (役職)\n"
        "- 報告ルール:\n"
        "    - `title_code`の不一致は **Error** として報告。\n"
        "    - `department_code`の不一致は、異動直後の可能性があるため **Warning** として報告。\n"
    )
    (SAMPLE_DIR / "instruction_hr_validation.md").write_text(instruction_md, encoding="utf-8")


def main() -> None:
    create_receivables_files()
    create_inventory_files()
    create_hr_files()
    print(f"フェーズ3検証用データを {SAMPLE_DIR} に生成しました。")


if __name__ == "__main__":
    main() 