# 在庫棚卸照合

- 突合キー: 理論在庫の「sku_code」と実在庫の「sku」
- 検証項目: 「system_quantity」と「actual_quantity」
- 許容範囲: 数量の差異が±2%以内の場合は、許容範囲内とみなし、差異なしとして扱うこと。
- 出力: 許容範囲を超える差異があったデータのみを`discrepancy_report.csv`に出力すること。
