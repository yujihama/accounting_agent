from __future__ import annotations

from src.state import AppState
from typing import Dict, Any
import pathlib

from src.agent_framework.specialist_agent import build_specialist_graph
from src.workflows.generic_matching_workflow import generic_matching_workflow

# --------------------------------------------------------------------------------------
# 独自ノード (追加集約が必要な場合のみ)
# --------------------------------------------------------------------------------------

# 今回は既存 nodes.py の共通ノードをそのまま利用するので追加ノードは不要。

# --------------------------------------------------------------------------------------
# ノード定義
# --------------------------------------------------------------------------------------

def _ensure_files(state: AppState) -> AppState:
    params: Dict[str, Any] = state.get("agent_parameters", {})  # type: ignore[assignment]
    inp = state.get("input_files", {})
    state["_src_file"] = params.get("source_file") or inp.get("deposit")
    state["_tgt_file"] = params.get("target_file") or inp.get("billing")
    if not state["_src_file"] or not state["_tgt_file"]:
        raise RuntimeError("receivables_reconciliation_agent: deposit/billing file missing")
    state["_output_dir"] = params.get("output_dir", "output")
    return state

def _run_matching(state: AppState) -> AppState:
    params: Dict[str, Any] = state.get("agent_parameters", {})  # type: ignore[assignment]
    # ensure _src_file/_tgt_file が存在
    if "_src_file" not in state or "_tgt_file" not in state:
        state = _ensure_files(state)

    results = generic_matching_workflow(
        source_file=state["_src_file"],
        target_file=state["_tgt_file"],
        source_key=params.get("source_key", "receipt_no"),
        target_key=params.get("target_key", "invoice_number"),
        numeric_field=params.get("numeric_field", "amount"),
        tolerance_pct=float(params.get("tolerance_pct", 0.0)),
        output_dir=str(pathlib.Path(state["_output_dir"]).resolve()),
    )
    state.setdefault("final_output_paths", {}).update(results)
    return state

# --------------------------------------------------------------------------------------
# LangGraph 構築
# --------------------------------------------------------------------------------------

_NODE_MAP = {
    "ensure_files": _ensure_files,
    "run_matching": _run_matching,
}

_GRAPH = build_specialist_graph(_NODE_MAP)


# --------------------------------------------------------------------------------------
# エージェント関数
# --------------------------------------------------------------------------------------

def receivables_reconciliation_agent(state: AppState) -> AppState:  # noqa: D401
    """売掛金消込エージェント (planner 付き LangGraph 版)"""
    final_state = _GRAPH.invoke(state)
    final_state["plan_next"] = "__end__"
    return final_state 