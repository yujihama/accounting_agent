from __future__ import annotations

from typing import Any, Dict, List
import os
from enum import Enum

from .state import AppState
from .tools.csv_reader import csv_reader
from .tools.excel_reader import excel_reader
from .tools.key_based_matcher import key_based_matcher
from .tools.key_name_detector import infer_matching_keys
from .tools.difference_validator import difference_validator
from .tools.csv_writer import csv_writer
from .tools.human_validator import human_validator
from langchain_openai import ChatOpenAI  # type: ignore
from .tools.instruction_tool_suggester import suggest_tools  # 推奨ツール生成
from .tools.instruction_parser import parse_instruction_file  # ローカル import
from .agents.inventory_matching_agent import inventory_matching_agent as _inventory_agent
from langchain.output_parsers import PydanticOutputParser  # NEW
from pydantic import BaseModel, Field  # NEW
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

    # 次ノード選択肢 Enum と PydanticOutputParser を定義（常に必要）
    class NextNodeEnum(str, Enum):
        read_instruction_file = "read_instruction_file"
        read_deposit_file = "read_deposit_file"
        read_billing_file = "read_billing_file"
        match_data_by_key = "match_data_by_key"
        validate_and_sort_matches = "validate_and_sort_matches"
        write_reconciled_csv = "write_reconciled_csv"
        write_unreconciled_csv = "write_unreconciled_csv"
        human_validator = "human_validator"
        inventory_matching_agent = "inventory_matching_agent"
        receivables_reconciliation_agent = "receivables_reconciliation_agent"
        employee_data_validator_agent = "employee_data_validator_agent"
        accounting_reconciliation_agent = "accounting_reconciliation_agent"
        end = "__end__"

    class NextNodeModel(BaseModel):
        next_node: NextNodeEnum = Field(..., description="次に実行するツール名")

    next_parser = PydanticOutputParser(pydantic_object=NextNodeModel)

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

    # -------------------------------------------------------------
    # 1. LLM + PydanticOutputParser によるパラメータ抽出
    # -------------------------------------------------------------
    if "instruction_tasks" in state and not state.get("next_agent"):
        # エージェント名候補を Enum で限定
        class AgentEnum(str, Enum):
            inventory_matching_agent = "inventory_matching_agent"
            receivables_reconciliation_agent = "receivables_reconciliation_agent"
            employee_data_validator_agent = "employee_data_validator_agent"
            accounting_reconciliation_agent = "accounting_reconciliation_agent"

        class PlannerExtraction(BaseModel):
            """LLM から返される構造化パラメータスキーマ"""
            next_agent: AgentEnum = Field(..., description="呼び出すべき専門家エージェント名")
            agent_parameters: Dict[str, Any] = Field(default_factory=dict, description="エージェントへ渡すパラメータ")

        parser = PydanticOutputParser(pydantic_object=PlannerExtraction)

        # 指示書の内容を分析してパラメータを抽出
        tasks_text = "\n".join(state["instruction_tasks"])
        
        extraction_prompt = f"""あなたは監督エージェントです。以下のタスク記述を読み取り、呼び出すべき専門家エージェントとそのパラメータを JSON で出力してください。

{parser.get_format_instructions()}

# タスク一覧
{tasks_text}

# エージェント選択ガイド
- 売掛金消込、入金照合、請求照合 → receivables_reconciliation_agent
- 在庫照合、棚卸照合、在庫差異 → inventory_matching_agent  
- 人事データ検証、名簿突合 → employee_data_validator_agent
- その他の会計照合 → accounting_reconciliation_agent

# パラメータ抽出ガイド
- 突合キー: 「突合キー」「マッチングキー」などの記述から抽出
- 検証項目: 「検証項目」「比較項目」などの記述から抽出
- 許容範囲: 「±2%」「誤差」などの記述から数値を抽出
- 出力ファイル: 「出力」「レポート」などの記述から抽出

例:
- 在庫照合の場合: {{"source_key": "sku_code", "target_key": "sku", "source_numeric_field": "system_quantity", "target_numeric_field": "actual_quantity", "tolerance_pct": 2.0}}
- 売掛金消込の場合: {{"source_key": "receipt_no", "target_key": "invoice_number", "numeric_field": "amount", "tolerance_pct": 0.0}}
"""

        try:
            llm_extract = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=512)
            extraction_resp = llm_extract.invoke([
                {"role": "system", "content": "You are an expert accounting planner."},
                {"role": "user", "content": extraction_prompt},
            ])

            raw_content = extraction_resp.content if hasattr(extraction_resp, "content") else extraction_resp
            parsed: PlannerExtraction = parser.parse(raw_content)
            state["next_agent"] = parsed.next_agent.value
            state["agent_parameters"] = parsed.agent_parameters
            print(f"[planner] Extracted agent: {state['next_agent']}")
            print(f"[planner] Extracted parameters: {state['agent_parameters']}")
        except Exception as e:
            # LLM 抽出に失敗した場合はワークフローを停止
            print(f"[planner] parameter extraction failed: {e}")
            state.setdefault("errors", []).append(f"planner parameter extraction failed: {e}")
            state["plan_next"] = "__end__"
            return state

    # -------------------------------------------------------------
    # 2. next_agent が設定されていればそれを優先
    # -------------------------------------------------------------
    if state.get("next_agent") and state.get("plan_next") not in ["__end__", state.get("next_agent")]:
        state["plan_next"] = state["next_agent"]
        return state

    try:
        llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=32)
        # -------------------------------------------------------------
        # LLM へのプロンプト
        # -------------------------------------------------------------
        # 1) 前提条件を満たさないツールや、必須アウトプットが揃わない段階での `__end__` 選択は禁止と明示
        # 2) 出力はツール名のみ（日本語不可）という指示を強化
        # 3) 進捗状況をアイコン付きで簡潔に示して判断材料を明確化
        base_prompt = (
            "あなたは優秀な経理担当アシスタントです。以下のルールを厳守し、最適な次のツールを 1 つだけ選択してください。\n"
            "- 前提条件を満たしていないツールは絶対に選ばないこと。\n"
            "- 全ての必須アウトプットファイル（reconciled.csv と unreconciled.csv）が出力されるまでは __end__ を選ばないこと。\n"
            "- 回答は JSON 形式のみ。余計な説明を付けないこと。\n"
        )

        system_prompt = base_prompt + "\n" + next_parser.get_format_instructions()

        # 進捗状況を分かりやすく表示
        def _flag(cond: bool) -> str:
            return "done" if cond else "not done"

        progress_lines = [
            f"instruction 読込: {_flag('instruction_tasks' in state or 'instruction' not in state.get('input_files', {}))}",
            f"deposit_file 読込: {_flag('raw_deposit_data' in state)}",
            f"billing_file 読込: {_flag('raw_billing_data' in state)}",
            f"マッチング: {_flag('matching_results' in state)}",
            f"検証: {_flag('reconciled_list' in state and 'unreconciled_list' in state)}",
            f"reconciled.csv 出力: {_flag('final_output_paths' in state and 'reconciled' in state.get('final_output_paths', {}))}",
            f"unreconciled.csv 出力: {_flag('final_output_paths' in state and 'unreconciled' in state.get('final_output_paths', {}))}",
        ]

        # suggested_queue の未実行分を準備
        executed = state.get("_executed_tools", [])
        suggested_remaining = [t for t in state.get("suggested_queue", []) if t not in executed]

        suggested_block = ", ".join(suggested_remaining) if suggested_remaining else "(none)"

        # instruction_tasks は冗長にならないよう最大 10 行まで
        tasks_excerpt = state.get("instruction_tasks", [])[:10]

        user_prompt = (
            "利用可能なツール一覧:\n" + "\n".join(tool_list) + "\n\n"
            "現在の進捗状況:\n" + "\n".join(progress_lines) + "\n\n"
            "推奨ツール (未実行, 順序どおり): " + suggested_block + "\n\n"
            "指示書タスク抜粋:\n" + "\n".join(tasks_excerpt)
        )
        messages: List[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = llm.invoke(messages)
        raw_resp = response.content if hasattr(response, "content") else response
        parsed_resp: NextNodeModel = next_parser.parse(raw_resp)
        next_node = parsed_resp.next_node.value
    except Exception as e:
        # LLM 呼び出し失敗時は例外をそのまま上位へ
        raise RuntimeError(f"planner ノードでの LLM 呼び出しに失敗しました: {e}")

    # ------------------------------------------------------------------
    # 前提条件チェック（不適切なツール選択 & 早期終了の対策）
    # ------------------------------------------------------------------

    def _needs_instruction() -> bool:
        return (
            'instruction' in state.get('input_files', {})
            and 'instruction_tasks' not in state
        )

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

    # 有効な次ノード一覧と前提条件
    valid_next = {
        "read_instruction_file": _needs_instruction,
        "read_deposit_file": _needs_deposit,
        "read_billing_file": _needs_billing,
        "match_data_by_key": _needs_match,
        "validate_and_sort_matches": _needs_validate,
        "write_reconciled_csv": _needs_write_reconciled,
        "write_unreconciled_csv": _needs_write_unreconciled,
        "human_validator": lambda: True,
        "inventory_matching_agent": lambda: True,
        "receivables_reconciliation_agent": lambda: True,
        "employee_data_validator_agent": lambda: True,
        "accounting_reconciliation_agent": lambda: True,
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

    # 2) 前提条件を満たしていないツール選択
    if not valid_next[next_node]():
        # 必須アウトプットが揃っていないのに __end__ を選んだ場合もここに来る
        raise RuntimeError(f"前提条件を満たさないツールが選択されました: {next_node}")

    # ------------------------------------------------------------------
    # 最終的な決定
    # ------------------------------------------------------------------
    print(f"[planner] next_node = {next_node}")
    state["plan_next"] = next_node
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