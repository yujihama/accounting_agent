# 人事データ検証手順

- 突合キー: `employee_id` と `emp_id`
- 検証項目:
    1. `department_code` (所属部署)
    2. `title_code` (役職)
- 報告ルール:
    - `title_code`の不一致は **Error** として報告。
    - `department_code`の不一致は、異動直後の可能性があるため **Warning** として報告。
