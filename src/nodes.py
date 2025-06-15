from __future__ import annotations

from typing import Any, Dict, List
import os

from .state import AppState
from .tools.csv_reader import csv_reader
from .tools.excel_reader import excel_reader
from .tools.key_based_matcher import key_based_matcher
from .tools.key_name_detector import infer_matching_keys
from .tools.difference_validator import difference_validator
from .tools.csv_writer import csv_writer
from .tools.human_validator import human_validator
from .tools.instruction_tool_suggester import suggest_tools  # 推奨ツール生成
from .tools.instruction_parser import parse_instruction_file  # ローカル import
from .agents.inventory_matching_agent import inventory_matching_agent as _inventory_agent
from .agents.receivables_reconciliation_agent import receivables_reconciliation_agent as _receivables_agent
from .agents.employee_data_validator_agent import employee_data_validator_agent as _employee_agent


# -----------------------------
# Node Implementations
# -----------------------------

def read_deposit_file(state: AppState) -> AppState:
    print("---NODE: read_deposit_file---")
    _mark_executed(state, "read_deposit_file")
    file_path = state["input_files"]["deposit"]
    state["raw_deposit_data"] = csv_reader(file_path)
    return state


def read_billing_file(state: AppState) -> AppState:
    print("---NODE: read_billing_file---")
    _mark_executed(state, "read_billing_file")
    file_path = state["input_files"]["billing"]
    state["raw_billing_data"] = excel_reader(file_path)
    return state


def match_data_by_key(state: AppState) -> AppState:
    print("---NODE: match_data_by_key---")
    _mark_executed(state, "match_data_by_key")
    # 自動でキー名を推定
    deposit_key, billing_key = infer_matching_keys(
        state["raw_deposit_data"], state["raw_billing_data"]
    )

    results = key_based_matcher(
        state["raw_deposit_data"],
        state["raw_billing_data"],
        deposit_key=deposit_key,
        billing_key=billing_key,
    )

    # 選定したキーを state に保持しておく（後続処理やログ用）
    state["selected_keys"] = {
        "deposit_key": deposit_key,
        "billing_key": billing_key,
    }

    state["matching_results"] = results
    return state


def validate_and_sort_matches(state: AppState) -> AppState:
    print("---NODE: validate_and_sort_matches---")
    _mark_executed(state, "validate_and_sort_matches")
    matched_pairs = state["matching_results"].get("matched_pairs", [])

    reconciled = []
    unreconciled = []

    for pair in matched_pairs:
        dep = pair["deposit"]
        bill = pair["billing"]

        try:
            dep_amount = float(dep.get("amount", 0))
            bill_amount = float(bill.get("amount", 0))
        except ValueError:
            # 金額が数値でない場合は未消込扱い
            unreconciled.append({**dep, **bill, "validation_error": "invalid_amount"})
            continue

        if difference_validator(dep_amount, bill_amount):
            # 消込成功
            reconciled.append({**dep, **bill})
        else:
            # 差額あり
            diff = dep_amount - bill_amount
            unreconciled.append({**dep, **bill, "difference": diff})

    # unmatchedデータは全て未消込に追加
    unreconciled.extend(state["matching_results"].get("unmatched_deposit", []))
    unreconciled.extend(state["matching_results"].get("unmatched_billing", []))

    state["reconciled_list"] = reconciled
    state["unreconciled_list"] = unreconciled
    return state


def write_reconciled_csv(state: AppState) -> AppState:
    print("---NODE: write_reconciled_csv---")
    _mark_executed(state, "write_reconciled_csv")
    output_path = "output/reconciled.csv"
    csv_writer(state.get("reconciled_list", []), output_path)
    state.setdefault("final_output_paths", {})["reconciled"] = output_path
    return state


def write_unreconciled_csv(state: AppState) -> AppState:
    print("---NODE: write_unreconciled_csv---")
    _mark_executed(state, "write_unreconciled_csv")
    output_path = "output/unreconciled.csv"
    csv_writer(state.get("unreconciled_list", []), output_path)
    state.setdefault("final_output_paths", {})["unreconciled"] = output_path
    return state


def read_instruction_file(state: AppState) -> AppState:
    """作業指示書 (Markdown / txt) を読み込み、タスク一覧を state に格納する。"""
    print("---NODE: read_instruction_file---")

    instr_path = state.get("input_files", {}).get("instruction")
    if not instr_path:
        # 指示書が渡されていなければそのまま返す
        return state

    try:
        tasks = parse_instruction_file(instr_path)
        state["instruction_tasks"] = tasks
    except Exception as e:
        # パース失敗時は例外を伝播（planner でハンドリング可能）
        raise RuntimeError(f"作業指示書の解析に失敗しました: {e}")

    # 推奨ツールキューを生成して保存
    tool_list = [
        "read_instruction_file",
        "read_deposit_file",
        "read_billing_file",
        "match_data_by_key",
        "validate_and_sort_matches",
        "write_reconciled_csv",
        "write_unreconciled_csv",
        "human_validator",
        "inventory_matching_agent",
        "receivables_reconciliation_agent",
        "employee_data_validator_agent",
        "accounting_reconciliation_agent",
        "__end__",
    ]
    suggested = suggest_tools(tasks, tool_list)
    state["suggested_queue"] = suggested

    # 実行履歴に追加
    _mark_executed(state, "read_instruction_file")

    return state




# -----------------------------
# human_validator 用ノード
# -----------------------------

def ask_human_validation(state: AppState) -> AppState:
    print("---NODE: ask_human_validation---")
    _mark_executed(state, "human_validator")
    human_validator(state)
    return state


# ---------------------------------
# 共通ヘルパー: 実行済みツールの記録
# ---------------------------------

def _mark_executed(state: AppState, node_name: str) -> None:
    if "_executed_tools" not in state:
        state["_executed_tools"] = []
    state["_executed_tools"].append(node_name)


# --------------------------
# 専門家エージェントノード
# --------------------------

def inventory_matching_agent_node(state: AppState) -> AppState:
    print("---NODE: inventory_matching_agent---")
    _mark_executed(state, "inventory_matching_agent")
    return _inventory_agent(state)


def receivables_reconciliation_agent_node(state: AppState) -> AppState:
    print("---NODE: receivables_reconciliation_agent---")
    _mark_executed(state, "receivables_reconciliation_agent")
    return _receivables_agent(state)


def employee_data_validator_agent_node(state: AppState) -> AppState:
    print("---NODE: employee_data_validator_agent---")
    _mark_executed(state, "employee_data_validator_agent")
    return _employee_agent(state)



def accounting_reconciliation_agent_node(state: AppState) -> AppState:
    print("---NODE: accounting_reconciliation_agent---")
    _mark_executed(state, "accounting_reconciliation_agent")
    # TODO: 実装
    return state
