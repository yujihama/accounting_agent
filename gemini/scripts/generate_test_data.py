import os
import pandas as pd


def main():
    os.makedirs("sample", exist_ok=True)

    deposit_data = [
        {"invoice_number": "INV-001", "amount": 1000.0, "deposit_date": "2024-06-11"},
        {"invoice_number": "INV-002", "amount": 1500.0, "deposit_date": "2024-06-11"},
        {"invoice_number": "INV-003", "amount": 500.0, "deposit_date": "2024-06-11"},
    ]

    billing_data = [
        {"invoice_number": "INV-001", "amount": 1000.0, "billing_date": "2024-06-01"},
        # 故意に1円差額を入れて未消込判定させる
        {"invoice_number": "INV-002", "amount": 1501.0, "billing_date": "2024-06-02"},
        # 未突合用
        {"invoice_number": "INV-004", "amount": 800.0, "billing_date": "2024-06-03"},
    ]

    pd.DataFrame(deposit_data).to_csv("sample/deposit.csv", index=False, encoding="utf-8")
    pd.DataFrame(billing_data).to_excel("sample/billing.xlsx", index=False, engine="openpyxl")

    print("[generate_test_data] サンプルファイルを sample ディレクトリに生成しました。")


if __name__ == "__main__":
    main() 