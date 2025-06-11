def difference_validator(amount_deposit: float, amount_billing: float, tolerance: float = 1e-2) -> bool:
    """金額差額が許容範囲内であるかを判定する。

    デフォルト許容誤差は1銭(0.01円)とする。"""
    return abs(amount_deposit - amount_billing) <= tolerance 