from __future__ import annotations

"""numeric_field_validator.py
数値フィールド同士の差分を許容誤差（パーセンテージ）で判定するユーティリティ。

Usage:
    >>> numeric_field_validator(100, 101, tolerance=1.0)
    True  # 1% 以内の差分
"""


def numeric_field_validator(value1: float, value2: float, tolerance: float) -> bool:  # noqa: D401
    """差分が許容範囲内かどうかを返す。

    Args:
        value1 (float): 1つ目の数値。
        value2 (float): 2つ目の数値。
        tolerance (float): 許容誤差をパーセンテージ(%)で指定する。

    Returns:
        bool: 許容範囲内なら ``True`` 、それ以外は ``False``。
    """

    try:
        value1_f = float(value1)
        value2_f = float(value2)
    except (ValueError, TypeError):
        # 数値に変換できなければ無条件に False
        return False

    # tolerance パーセンテージを閾値へ変換
    max_diff = abs(value1_f) * (tolerance / 100.0)
    return abs(value1_f - value2_f) <= max_diff 