from __future__ import annotations

import pathlib
import os
from typing import Dict, Any

# .env から環境変数をロード
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    # python-dotenv が未インストールの場合はそのまま進む。
    # requirements.txt には含めるので通常は通る想定。
    pass

from langgraph.graph import StateGraph, END

from .state import AppState
from .nodes import (
    read_deposit_file,
    read_billing_file,
    match_data_by_key,
    validate_and_sort_matches,
    write_reconciled_csv,
    write_unreconciled_csv,
    planner,
    ask_human_validation,
)


# -----------------------------
# Graph Construction
# -----------------------------

def build_graph() -> Any:
    """LangGraphのStateGraphを構築して返す。"""
    sg: StateGraph = StateGraph(AppState)

    # ノードを登録
    sg.add_node("planner", planner)
    sg.add_node("read_deposit_file", read_deposit_file)
    sg.add_node("read_billing_file", read_billing_file)
    sg.add_node("match_data_by_key", match_data_by_key)
    sg.add_node("validate_and_sort_matches", validate_and_sort_matches)
    sg.add_node("write_reconciled_csv", write_reconciled_csv)
    sg.add_node("write_unreconciled_csv", write_unreconciled_csv)
    sg.add_node("human_validator", ask_human_validation)

    # エントリーポイントをプランナーに設定
    sg.set_entry_point("planner")

    # -------------------------
    # 動的ルーティング設定
    # -------------------------

    # planner -> 各ノード への条件付きエッジ
    def _edge_selector(state: AppState):  # type: ignore[override]
        return state.get("plan_next", "__end__")

    sg.add_conditional_edges(
        "planner",
        _edge_selector,
        {
            "read_deposit_file": "read_deposit_file",
            "read_billing_file": "read_billing_file",
            "match_data_by_key": "match_data_by_key",
            "validate_and_sort_matches": "validate_and_sort_matches",
            "write_reconciled_csv": "write_reconciled_csv",
            "write_unreconciled_csv": "write_unreconciled_csv",
            "human_validator": "human_validator",
            "__end__": END,
        },
    )

    # 各ノード完了後は planner へ戻す
    for node_name in [
        "read_deposit_file",
        "read_billing_file",
        "match_data_by_key",
        "validate_and_sort_matches",
        "write_reconciled_csv",
        "write_unreconciled_csv",
        "human_validator",
    ]:
        sg.add_edge(node_name, "planner")

    return sg.compile()


# -----------------------------
# CLI Entrypoint
# -----------------------------

def run_workflow(deposit_path: str, billing_path: str) -> Dict[str, Any]:
    """ワークフローを実行し、最終stateを返す。"""
    app = build_graph()

    initial_state: AppState = {
        "input_files": {
            "deposit": str(pathlib.Path(deposit_path).resolve()),
            "billing": str(pathlib.Path(billing_path).resolve()),
        }
    }

    final_state: AppState = app.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    import argparse, json, sys

    parser = argparse.ArgumentParser(description="Sales credit reconciliation workflow")
    parser.add_argument("--deposit", required=True, help="Deposit CSV file path")
    parser.add_argument("--billing", required=True, help="Billing Excel file path")
    args = parser.parse_args()

    result_state = run_workflow(args.deposit, args.billing)
    print(json.dumps(result_state.get("final_output_paths", {}), ensure_ascii=False, indent=2)) 