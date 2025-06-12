from __future__ import annotations

from typing import Any, Dict
import pathlib

from ..state import AppState
from ..workflows.generic_matching_workflow import generic_matching_workflow

# 他ツール再利用
from ..tools.csv_reader import csv_reader  # noqa: F401  （依存性注入用として公開）
from ..tools.excel_reader import excel_reader  # noqa: F401
from ..tools.key_based_matcher import key_based_matcher  # noqa: F401
from ..tools.numeric_field_validator import numeric_field_validator  # noqa: F401
from ..tools.csv_writer import csv_writer  # noqa: F401


# --------------------------------------------------------------------------------------
# InventoryMatchingAgent
# --------------------------------------------------------------------------------------

def inventory_matching_agent(state: AppState) -> AppState:  # noqa: D401
    """在庫照合を行う専門家エージェント。

    `state['agent_parameters']` に格納されたパラメータを解釈し、
    `generic_matching_workflow` を実行して差異レポートを生成する。

    最終的な出力ファイルパスは `state['final_output_paths']` に格納し、
    ワークフロー終了後は `state['plan_next']` を `'__end__'` に設定する。
    """

    print("---AGENT: inventory_matching_agent---")

    params: Dict[str, Any] = state.get("agent_parameters", {})  # type: ignore[assignment]

    # 必須パラメータ: source_file と target_file
    source_file = params.get("source_file") or state.get("input_files", {}).get("inventory_count")
    target_file = params.get("target_file") or state.get("input_files", {}).get("inventory_master")

    if not source_file or not target_file:
        raise RuntimeError("inventory_matching_agent: source_file と target_file が指定されていません。")

    # キーとフィールド設定
    source_key = params.get("source_key", "item_id")
    target_key = params.get("target_key", "item_id")
    numeric_field = params.get("numeric_field", "quantity")
    tolerance_pct = float(params.get("tolerance_pct", 0.0))

    output_dir = params.get("output_dir", "output")
    output_dir_abs = str(pathlib.Path(output_dir).resolve())

    results = generic_matching_workflow(
        source_file=source_file,
        target_file=target_file,
        source_key=source_key,
        target_key=target_key,
        numeric_field=numeric_field,
        tolerance_pct=tolerance_pct,
        output_dir=output_dir_abs,
    )

    state.setdefault("final_output_paths", {}).update(results)

    # エージェント処理完了。プランナーに戻さず終了させたい場合、plan_next='__end__'
    state["plan_next"] = "__end__"

    return state 