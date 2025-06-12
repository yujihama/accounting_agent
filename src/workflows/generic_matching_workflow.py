from __future__ import annotations

import os
import pathlib
from typing import Callable, Dict, List, Any

from ..tools.csv_reader import csv_reader
from ..tools.excel_reader import excel_reader
from ..tools.key_based_matcher import key_based_matcher
from ..tools.csv_writer import csv_writer
from ..tools.numeric_field_validator import numeric_field_validator


# --------------------------------------------------------------------------------------
# Generic Matching Workflow
# --------------------------------------------------------------------------------------


def _default_reader(path: str) -> List[Dict[str, Any]]:
    """拡張子に応じて CSV または Excel 読み込みを自動判定するデフォルトリーダ。"""
    ext = pathlib.Path(path).suffix.lower()
    if ext == ".csv":
        return csv_reader(path)
    elif ext in {".xlsx", ".xls"}:
        return excel_reader(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


def generic_matching_workflow(
    *,
    source_file: str,
    target_file: str,
    source_key: str,
    target_key: str,
    output_dir: str = "output",
    numeric_field: str = "amount",
    tolerance_pct: float = 0.0,
    # Dependency injection hooks -------------------------------------------------
    source_reader: Callable[[str], List[Dict[str, Any]]] = _default_reader,
    target_reader: Callable[[str], List[Dict[str, Any]]] = _default_reader,
    matcher: Callable[..., Dict[str, Any]] = key_based_matcher,
    validator: Callable[[float, float, float], bool] = numeric_field_validator,
) -> Dict[str, str]:
    """汎用的な二つのデータソース突合ワークフローを実行する。

    Args:
        source_file: 左側(基準)となるデータのファイルパス。
        target_file: 右側(突合対象)となるデータのファイルパス。
        source_key: source のマッチングに使用するキー名。
        target_key: target のマッチングに使用するキー名。
        output_dir: CSV 出力先ディレクトリ。
        numeric_field: 照合対象の数値フィールド名。
        tolerance_pct: 許容誤差(%)。
        source_reader: 依存性注入用リーダ関数(デフォルトは拡張子自動判定)。
        target_reader: 依存性注入用リーダ関数。
        matcher: マッチング関数。
        validator: 検証関数。

    Returns:
        Dict[str, str]: {
            "reconciled": "path/to/reconciled.csv",
            "unreconciled": "path/to/unreconciled.csv"
        }
    """

    # ------------------------------------------------------------------
    # 1. 入力読み込み
    # ------------------------------------------------------------------
    source_records = source_reader(source_file)
    target_records = target_reader(target_file)

    # ------------------------------------------------------------------
    # 2. キー突合
    # ------------------------------------------------------------------
    match_results = matcher(
        source_records,
        target_records,
        deposit_key=source_key,
        billing_key=target_key,
    )

    matched_pairs: List[Dict[str, Any]] = match_results.get("matched_pairs", [])

    reconciled: List[Dict[str, Any]] = []
    unreconciled: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 3. 各ペアの数値バリデーション
    # ------------------------------------------------------------------
    for pair in matched_pairs:
        src = pair["deposit"]  # key_based_matcher の命名を流用
        tgt = pair["billing"]

        try:
            v1 = float(src.get(numeric_field, 0))
            v2 = float(tgt.get(numeric_field, 0))
        except (ValueError, TypeError):
            # 数値変換できなければ未突合扱い
            pair["validation_error"] = "invalid_numeric"
            unreconciled.append({**src, **tgt, **pair})
            continue

        if validator(v1, v2, tolerance_pct):
            reconciled.append({**src, **tgt})
        else:
            diff = v1 - v2
            unreconciled.append({**src, **tgt, "difference": diff})

    # unmatched データも未突合に追加
    unreconciled.extend(match_results.get("unmatched_deposit", []))
    unreconciled.extend(match_results.get("unmatched_billing", []))

    # ------------------------------------------------------------------
    # 4. CSV 出力
    # ------------------------------------------------------------------
    os.makedirs(output_dir, exist_ok=True)
    reconciled_path = str(pathlib.Path(output_dir) / "reconciled.csv")
    unreconciled_path = str(pathlib.Path(output_dir) / "unreconciled.csv")

    csv_writer(reconciled, reconciled_path)
    csv_writer(unreconciled, unreconciled_path)

    return {
        "reconciled": reconciled_path,
        "unreconciled": unreconciled_path,
    } 