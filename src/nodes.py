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
from langchain_openai import ChatOpenAI  # type: ignore


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


def planner(state: AppState) -> AppState:
    """LLM（もしくはフォールバックロジック）で次に実行するノード名を決定する。決定結果は
    state["plan_next"] に文字列で格納する。
    """
    print("---NODE: planner---")

    # 既に決定済みの場合（前回 human_validator などで戻ってきたケース）はスキップ
    if state.get("plan_next") == "__end__":
        return state

    # OPENAI_API_KEY が設定されていなければ例外
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY が設定されていません。LLM を利用できないためプランナーを実行できません。")

    try:
        llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=32)
        # -------------------------------------------------------------
        # LLM へのプロンプト
        # -------------------------------------------------------------
        # 1) 前提条件を満たさないツールや、必須アウトプットが揃わない段階での `__end__` 選択は禁止と明示
        # 2) 出力はツール名のみ（日本語不可）という指示を強化
        # 3) 進捗状況をアイコン付きで簡潔に示して判断材料を明確化
        system_prompt = (
            "あなたは優秀な経理担当アシスタントです。以下のルールを厳守し、最適な次のツールを 1 つだけ選択してください。\n"
            "- 前提条件を満たしていないツールは絶対に選ばないこと。\n"
            "- 全ての必須アウトプットファイル（reconciled.csv と unreconciled.csv）が出力されるまでは __end__ を選ばないこと。\n"
            "- 回答はツール名 1 語のみ。日本語や説明を付けないこと。"
        )
        tool_list = [
            "read_deposit_file",
            "read_billing_file",
            "match_data_by_key",
            "validate_and_sort_matches",
            "write_reconciled_csv",
            "write_unreconciled_csv",
            "human_validator",
            "__end__",
        ]
        # 進捗状況を分かりやすく表示
        def _flag(cond: bool) -> str:
            return "done" if cond else "not done"

        progress_lines = [
            f"deposit_file 読込: {_flag('raw_deposit_data' in state)}",
            f"billing_file 読込: {_flag('raw_billing_data' in state)}",
            f"マッチング: {_flag('matching_results' in state)}",
            f"検証: {_flag('reconciled_list' in state and 'unreconciled_list' in state)}",
            f"reconciled.csv 出力: {_flag('final_output_paths' in state and 'reconciled' in state.get('final_output_paths', {}))}",
            f"unreconciled.csv 出力: {_flag('final_output_paths' in state and 'unreconciled' in state.get('final_output_paths', {}))}",
        ]

        user_prompt = (
            "利用可能なツール一覧:\n" + "\n".join(tool_list) + "\n\n"
            "現在の進捗状況:\n" + "\n".join(progress_lines)
        )
        messages: List[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = llm.invoke(messages)
        if isinstance(response, str):
            next_node = response.strip()
        else:
            next_node = str(response.content).strip()
    except Exception as e:
        # LLM 呼び出し失敗時は例外をそのまま上位へ
        raise RuntimeError(f"planner ノードでの LLM 呼び出しに失敗しました: {e}")

    # ------------------------------------------------------------------
    # 前提条件チェック（不適切なツール選択 & 早期終了の対策）
    # ------------------------------------------------------------------

    def _needs_deposit() -> bool:
        return "raw_deposit_data" not in state

    def _needs_billing() -> bool:
        return "raw_billing_data" not in state

    def _needs_match() -> bool:
        return "matching_results" not in state

    def _needs_validate() -> bool:
        return "reconciled_list" not in state or "unreconciled_list" not in state

    def _needs_write_reconciled() -> bool:
        return "reconciled_list" in state and (
            "final_output_paths" not in state or "reconciled" not in state.get("final_output_paths", {})
        )

    def _needs_write_unreconciled() -> bool:
        return "unreconciled_list" in state and (
            "final_output_paths" not in state or "unreconciled" not in state.get("final_output_paths", {})
        )

    valid_next = {
        "read_deposit_file": _needs_deposit,
        "read_billing_file": _needs_billing,
        "match_data_by_key": _needs_match,
        "validate_and_sort_matches": _needs_validate,
        "write_reconciled_csv": _needs_write_reconciled,
        "write_unreconciled_csv": _needs_write_unreconciled,
        "human_validator": lambda: True,
        "__end__": lambda: not (
            _needs_deposit()
            or _needs_billing()
            or _needs_match()
            or _needs_validate()
            or _needs_write_reconciled()
            or _needs_write_unreconciled()
        ),
    }

    # 1) 未知のツール名
    if next_node not in valid_next:
        raise RuntimeError(f"未知のツール名が返されました: {next_node}")

    # 2) 前提条件を満たさないツール
    if not valid_next[next_node]():
        raise RuntimeError(
            f"LLM が前提条件を満たしていないツールを選択しました: {next_node}. 現在の state では実行できません。"
        )

    # 決定結果を state に保存
    state["plan_next"] = next_node

    # ------------------------------------------------------------------
    # ループガード: 同じノードを連続 50 回以上提案したら異常とみなす
    # ------------------------------------------------------------------
    tick = state.setdefault("_planner_tick", 0)
    state["_planner_tick"] = tick + 1
    if state["_planner_tick"] > 500:
        raise RuntimeError("planner が 500 ステップを超えました。無限ループの可能性があります。")

    print(f"[planner] next_node = {next_node}")

    return state


# -----------------------------
# human_validator 用ノード
# -----------------------------

def ask_human_validation(state: AppState) -> AppState:
    print("---NODE: human_validator---")
    question = state.get("human_validation_question", "この処理を続行しますか？")
    answer = human_validator(question)
    state["human_validation_answer"] = answer
    # human_validator の結果をどう使うかは将来的にプランナー側で判断する
    return state 