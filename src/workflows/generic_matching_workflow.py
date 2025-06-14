from __future__ import annotations

import os
import pathlib
from typing import Callable, Dict, List, Any

from ..tools.csv_reader import csv_reader
from ..tools.excel_reader import excel_reader
from ..tools.key_based_matcher import key_based_matcher
from ..tools.csv_writer import csv_writer
from ..tools.numeric_field_validator import numeric_field_validator
from ..tools.string_field_validator import string_field_validator


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
    target_numeric_field: str | None = None,
    tolerance_pct: float = 0.0,
    validation_rules: List[Dict[str, Any]] | None = None,
    report_filename: str = "validation_report.csv",
    # Dependency injection hooks -----------------------------------------------
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
        numeric_field: 照合対象の数値フィールド名（source側）。
        target_numeric_field: 照合対象の数値フィールド名（target側）。Noneの場合はnumeric_fieldと同じ。
        tolerance_pct: 許容誤差(%)。
        validation_rules: 検証ルールのリスト。指定がある場合はそちらを優先。
        report_filename: validation_rules 利用時の出力ファイル名。
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

    # target_numeric_field が指定されていない場合は numeric_field と同じにする
    if target_numeric_field is None:
        target_numeric_field = numeric_field

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

    if validation_rules is None:
        reconciled: List[Dict[str, Any]] = []
        unreconciled: List[Dict[str, Any]] = []

        # --------------------------------------------------------------
        # 3. 単一数値フィールドのバリデーション
        # --------------------------------------------------------------
        for pair in matched_pairs:
            src = pair["deposit"]  # key_based_matcher の命名を流用
            tgt = pair["billing"]

            try:
                v1 = float(src.get(numeric_field, 0))
                v2 = float(tgt.get(target_numeric_field, 0))
            except (ValueError, TypeError):
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

        # --------------------------------------------------------------
        # 4. CSV 出力
        # --------------------------------------------------------------
        os.makedirs(output_dir, exist_ok=True)
        reconciled_path = str(pathlib.Path(output_dir) / "reconciled.csv")
        unreconciled_path = str(pathlib.Path(output_dir) / "unreconciled.csv")

        csv_writer(reconciled, reconciled_path)
        csv_writer(unreconciled, unreconciled_path)

        return {
            "reconciled": reconciled_path,
            "unreconciled": unreconciled_path,
        }

    # --------------------------------------------------------------
    # validation_rules を利用した汎用検証
    # --------------------------------------------------------------
    report_rows: List[Dict[str, Any]] = []
    for pair in matched_pairs:
        src = pair["deposit"]
        tgt = pair["billing"]
        key_value = src.get(source_key)

        for rule in validation_rules:
            src_field = rule.get("source_field") or rule.get("field")
            tgt_field = rule.get("target_field", src_field)
            severity = rule.get("severity", "Error")
            v1 = src.get(src_field)
            v2 = tgt.get(tgt_field)
            if rule.get("validator") == "numeric":
                tol = float(rule.get("tolerance_pct", 0.0))
                try:
                    n1 = float(v1)
                    n2 = float(v2)
                except (ValueError, TypeError):
                    mismatch = True
                else:
                    mismatch = not validator(n1, n2, tol)
            else:
                mismatch = not string_field_validator(v1, v2)

            if mismatch:
                report_rows.append(
                    {
                        source_key: key_value,
                        "field": src_field,
                        "master_value": v1,
                        "list_value": v2,
                        "severity": severity,
                    }
                )

    os.makedirs(output_dir, exist_ok=True)
    report_path = str(pathlib.Path(output_dir) / report_filename)
    csv_writer(report_rows, report_path)
    return {"report": report_path}
