from __future__ import annotations

from typing import Any, Dict
import pathlib

from src.state import AppState
from src.workflows.generic_matching_workflow import generic_matching_workflow
from src.agent_framework.specialist_agent import build_specialist_graph


# ---------------------------------------------------------------------------
# ノード定義
# ---------------------------------------------------------------------------

def _ensure_files(state: AppState) -> AppState:
    """入力ファイルを確定して state に保持"""
    params: Dict[str, Any] = state.get("agent_parameters", {})
    files = state.get("input_files", {})

    state["_src_file"] = params.get("source_file") or files.get("deposit")
    state["_tgt_file"] = params.get("target_file") or files.get("billing")
    if not state["_src_file"] or not state["_tgt_file"]:
        raise RuntimeError("employee_data_validator_agent: source/target file missing")
    return state


def _run_validation(state: AppState) -> AppState:
    """汎用ワークフローを利用して人事データ検証を実行"""
    params: Dict[str, Any] = state.get("agent_parameters", {})
    if "_src_file" not in state or "_tgt_file" not in state:
        state = _ensure_files(state)

    validation_rules = params.get("validation_rules") or [
        {"field": "department_code", "target_field": "dept", "severity": "Warning"},
        {"field": "title_code", "severity": "Error"},
    ]

    results = generic_matching_workflow(
        source_file=state["_src_file"],
        target_file=state["_tgt_file"],
        source_key=params.get("source_key", "employee_id"),
        target_key=params.get("target_key", "emp_id"),
        validation_rules=validation_rules,
        output_dir=str(pathlib.Path(params.get("output_dir", "output")).resolve()),
        report_filename="inconsistent_hr_data.csv",
    )

    report_path = results.get("report")
    if report_path:
        state.setdefault("final_output_paths", {})["inconsistent_hr_data"] = report_path
    return state


# ---------------------------------------------------------------------------
# LangGraph 構築
# ---------------------------------------------------------------------------

_NODE_MAP = {
    "ensure_files": _ensure_files,
    "run_validation": _run_validation,
}

_GRAPH = build_specialist_graph(_NODE_MAP)


# ---------------------------------------------------------------------------
# エージェント関数
# ---------------------------------------------------------------------------

def employee_data_validator_agent(state: AppState) -> AppState:  # noqa: D401
    """人事データ検証エージェント (planner 付き LangGraph 版)"""
    final_state = _GRAPH.invoke(state)
    final_state["plan_next"] = "__end__"
    return final_state
