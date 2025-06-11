from __future__ import annotations

from typing import Any, Dict

from .state import AppState
from .tools.csv_reader import csv_reader
from .tools.excel_reader import excel_reader
from .tools.key_based_matcher import key_based_matcher
from .tools.key_name_detector import infer_matching_keys
from .tools.difference_validator import difference_validator
from .tools.csv_writer import csv_writer


# -----------------------------
# Node Implementations
# -----------------------------

def read_deposit_file(state: AppState) -> AppState:
    print("---NODE: read_deposit_file---")
    file_path = state["input_files"]["deposit"]
    state["raw_deposit_data"] = csv_reader(file_path)
    return state


def read_billing_file(state: AppState) -> AppState:
    print("---NODE: read_billing_file---")
    file_path = state["input_files"]["billing"]
    state["raw_billing_data"] = excel_reader(file_path)
    return state


def match_data_by_key(state: AppState) -> AppState:
    print("---NODE: match_data_by_key---")
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
    output_path = "output/reconciled.csv"
    csv_writer(state.get("reconciled_list", []), output_path)
    state.setdefault("final_output_paths", {})["reconciled"] = output_path
    return state


def write_unreconciled_csv(state: AppState) -> AppState:
    print("---NODE: write_unreconciled_csv---")
    output_path = "output/unreconciled.csv"
    csv_writer(state.get("unreconciled_list", []), output_path)
    state.setdefault("final_output_paths", {})["unreconciled"] = output_path
    return state 