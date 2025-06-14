from __future__ import annotations

from typing import Any, Dict
import pathlib

from ..state import AppState
from ..workflows.generic_matching_workflow import generic_matching_workflow

# --------------------------------------------------------------------------------------
# ReceivablesReconciliationAgent (別名 accounting_reconciliation_agent)
# --------------------------------------------------------------------------------------

def receivables_reconciliation_agent(state: AppState) -> AppState:
    """売掛金消込を行う専門家エージェント。"""

    print("---AGENT: receivables_reconciliation_agent---")

    params: Dict[str, Any] = state.get("agent_parameters", {})  # type: ignore[assignment]

    source_file = params.get("source_file") or state.get("input_files", {}).get("deposit")
    target_file = params.get("target_file") or state.get("input_files", {}).get("billing")

    if not source_file or not target_file:
        raise RuntimeError("receivables_reconciliation_agent: 必要な入出力ファイルが不足しています。")

    source_key = params.get("source_key", "receipt_no")
    target_key = params.get("target_key", "invoice_number")
    numeric_field = params.get("numeric_field", "amount")

    output_dir = params.get("output_dir", "output")
    output_dir_abs = str(pathlib.Path(output_dir).resolve())

    results = generic_matching_workflow(
        source_file=source_file,
        target_file=target_file,
        source_key=source_key,
        target_key=target_key,
        numeric_field=numeric_field,
        tolerance_pct=float(params.get("tolerance_pct", 0.0)),
        output_dir=output_dir_abs,
    )

    state.setdefault("final_output_paths", {}).update(results)

    # -------------------------------------------------------------
    # フロー終了判定は原則 planner に委譲する。
    # params で terminate_after=True が指定された場合のみ即終了
    # -------------------------------------------------------------
    if params.get("terminate_after", False):
        state["plan_next"] = "__end__"

    return state 