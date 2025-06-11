from typing import List, Dict, Any


def key_based_matcher(
    deposit_data: List[Dict[str, Any]],
    billing_data: List[Dict[str, Any]],
    deposit_key: str = "invoice_number",
    billing_key: str = "invoice_number",
) -> Dict[str, Any]:
    """入金データと請求データをキー指定で突合する。

    Args:
        deposit_data: 入金側データのリスト。
        billing_data: 請求側データのリスト。
        deposit_key: 入金データにおけるキー名。
        billing_key: 請求データにおけるキー名。

    Returns:
        dict: 以下の形式で突合結果を返す。
            {
                "matched_pairs": List[Dict],
                "unmatched_deposit": List[Dict],
                "unmatched_billing": List[Dict],
            }
    """

    # 請求データのインデックスを構築
    billing_index = {
        row.get(billing_key): row for row in billing_data if row.get(billing_key) is not None
    }

    matched_pairs: List[Dict[str, Any]] = []
    unmatched_deposit: List[Dict[str, Any]] = []

    # billing側の残りを保持するためにコピー
    remaining_billing = billing_data.copy()

    for dep_row in deposit_data:
        k = dep_row.get(deposit_key)
        bill_row = billing_index.get(k)
        if bill_row is not None:
            matched_pairs.append({"deposit": dep_row, "billing": bill_row})
            if bill_row in remaining_billing:
                remaining_billing.remove(bill_row)
        else:
            unmatched_deposit.append(dep_row)

    return {
        "matched_pairs": matched_pairs,
        "unmatched_deposit": unmatched_deposit,
        "unmatched_billing": remaining_billing,
    }


# 後方互換用ラッパー --------------------------------------------------------

def key_based_matcher_legacy(
    deposit_data: List[Dict[str, Any]],
    billing_data: List[Dict[str, Any]],
    key: str = "invoice_number",
) -> Dict[str, Any]:
    """旧インターフェース（単一キー）互換のラッパー関数。"""

    return key_based_matcher(
        deposit_data=deposit_data,
        billing_data=billing_data,
        deposit_key=key,
        billing_key=key,
    ) 