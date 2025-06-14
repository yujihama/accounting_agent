from __future__ import annotations

from typing import Any, Dict
import pathlib

from src.state import AppState
from src.workflows.generic_matching_workflow import generic_matching_workflow
from src.agent_framework.specialist_agent import build_specialist_graph

# 他ツール再利用
from ..tools.csv_reader import csv_reader  # noqa: F401  （依存性注入用として公開）
from ..tools.excel_reader import excel_reader  # noqa: F401
from ..tools.key_based_matcher import key_based_matcher  # noqa: F401
from ..tools.numeric_field_validator import numeric_field_validator  # noqa: F401
from ..tools.csv_writer import csv_writer  # noqa: F401


# --------------------------------------------------------------------------------------
# ノード定義
# --------------------------------------------------------------------------------------


def _ensure_files(state: AppState) -> AppState:
    """入力ファイル（source/target）を確定して state に格納"""
    params: Dict[str, Any] = state.get("agent_parameters", {})  # type: ignore[assignment]
    input_files = state.get("input_files", {})

    state["_src_file"] = (
        params.get("source_file")
        or input_files.get("inventory_count")
        or input_files.get("deposit")
    )
    state["_tgt_file"] = (
        params.get("target_file")
        or input_files.get("inventory_master")
        or input_files.get("billing")
    )
    if not state["_src_file"] or not state["_tgt_file"]:
        raise RuntimeError("inventory_matching_agent: source/target file missing")
    return state


def _run_matching(state: AppState) -> AppState:
    """generic_matching_workflow を実行し差異レポートを出力"""
    params: Dict[str, Any] = state.get("agent_parameters", {})  # type: ignore[assignment]

    # _src_file が無い場合は ensure_files 相当を実行
    if "_src_file" not in state or "_tgt_file" not in state:
        state = _ensure_files(state)

    results = generic_matching_workflow(
        source_file=state["_src_file"],
        target_file=state["_tgt_file"],
        source_key=params.get("source_key", "sku"),
        target_key=params.get("target_key", "sku_code"),
        numeric_field=params.get("numeric_field", "quantity"),
        tolerance_pct=float(params.get("tolerance_pct", 2.0)),
        output_dir=str(pathlib.Path(params.get("output_dir", "output")).resolve()),
    )
    # unreconciled を discrepancy_report に名前変換して格納
    csv_out = results.get("unreconciled")
    if csv_out:
        state.setdefault("final_output_paths", {})["discrepancy_report"] = csv_out
    return state


# --------------------------------------------------------------------------------------
# LangGraph 構築（共通ビルダ利用）
# --------------------------------------------------------------------------------------

_NODE_MAP = {
    "ensure_files": _ensure_files,
    "run_matching": _run_matching,
}

_GRAPH = build_specialist_graph(_NODE_MAP)


# --------------------------------------------------------------------------------------
# エクスポート関数
# --------------------------------------------------------------------------------------

def inventory_matching_agent(state: AppState) -> AppState:  # noqa: D401
    """在庫照合エージェント (planner 付き LangGraph 版)"""
    final_state = _GRAPH.invoke(state)
    # サブエージェント完了を親プランナーへ通知
    final_state["plan_next"] = "__end__"
    return final_state
