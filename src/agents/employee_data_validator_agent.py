from __future__ import annotations

from typing import Dict, Any

from src.state import AppState
from src.workflows.generic_matching_workflow import generic_matching_workflow


def employee_data_validator_agent(state: AppState) -> AppState:
    """人事データ検証エージェント（薄いアダプター層）

    監督エージェントから受け取ったパラメータをそのまま
    汎用照合ワークフローに渡すシンプルなアダプター。
    Hybrid Key-Specification Modelに完全対応。
    """
    params: Dict[str, Any] = state.get("agent_parameters", {})
    input_files = state.get("input_files", {})

    source_file = params.get("source_file") or input_files.get("master") or input_files.get("deposit")
    target_file = params.get("target_file") or input_files.get("list") or input_files.get("billing")

    if not source_file or not target_file:
        raise RuntimeError("employee_data_validator_agent: 入力ファイルが不足しています")

    match_keys = None
    if params.get("match_keys"):
        match_keys = {
            "source": params["match_keys"]["source"],
            "target": params["match_keys"]["target"],
        }
        print(f"監督エージェントから指定されたキー: {match_keys}")
    else:
        print("キー未指定 - 汎用ワークフローで自動推定を実行")

    default_validation_rules = [
        {"field": "department_code", "target_field": "dept", "severity": "Warning"},
        {"field": "title_code", "severity": "Error"},
    ]
    validation_rules = params.get("validation_rules", default_validation_rules)

    try:
        results = generic_matching_workflow(
            source_file=source_file,
            target_file=target_file,
            match_keys=match_keys,
            output_dir=params.get("output_dir", "output"),
            validation_rules=validation_rules,
            report_filename="inconsistent_hr_data.csv",
        )
        report_path = results.get("report")
        if report_path:
            state.setdefault("final_output_paths", {})["inconsistent_hr_data"] = report_path
        state["plan_next"] = "__end__"
        print(f"人事データ検証完了: {results}")
    except Exception as e:  # pragma: no cover - runtime errors handled
        state.setdefault("errors", []).append(f"人事データ検証エラー: {str(e)}")
        state["plan_next"] = "__end__"
        print(f"エラー: {e}")

    return state
