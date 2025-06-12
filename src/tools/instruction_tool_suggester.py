from __future__ import annotations
"""instruction_tool_suggester.py

指示書のタスク行 (List[str]) と、利用可能ツール一覧 (List[str]) を入力として、
タスクを実行する推奨ツールの順序リストを返すヘルパー。

Phase-2 では次の簡易戦略を採用する。

1. OPENAI_API_KEY が存在し、langchain_openai が import 可能であれば LLM で推論。
2. そうでなければヒューリスティック (キーワードマッチ) で推論。
3. 推論結果から "none" や未知ツール、重複を除外し順序を保持して返却。
"""

from typing import List, Dict
import os
import re

# LLM オプション
try:
    from langchain_openai import ChatOpenAI  # type: ignore
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_tools(task_lines: List[str], tool_list: List[str]) -> List[str]:
    """タスク行とツール一覧から推奨ツール順序リストを生成する。"""

    if not task_lines:
        return []

    # 1) LLM が利用できる場合は一括推論
    if ChatOpenAI is not None and os.getenv("OPENAI_API_KEY"):
        try:
            return _suggest_via_llm(task_lines, tool_list)
        except Exception:
            # LLM 失敗時はフォールバック
            pass

    # 2) ヒューリスティックフォールバック
    return _suggest_via_heuristic(task_lines, tool_list)


# ---------------------------------------------------------------------------
# LLM ベースの推論
# ---------------------------------------------------------------------------

def _suggest_via_llm(task_lines: List[str], tool_list: List[str]) -> List[str]:
    """LLM を用いたツール候補推定。一括 JSON 出力を期待する。"""

    llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=256)

    system_prompt = (
        "You are an assistant that maps user tasks into tool names. "
        "Return a JSON array, each element contains 'tool' chosen from the provided list. "
        "If no suitable tool, use 'none'."
    )

    tasks_block = "\n".join([f"- {t}" for t in task_lines])
    tools_block = ", ".join(tool_list)

    user_prompt = (
        f"Tool list: {tools_block}\n\nTasks to map:\n{tasks_block}\n\n"
        "Return JSON array like: [\"read_deposit_file\", ...]."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # 粗めの JSON 抽出
    try:
        import json

        start = content.find("[")
        end = content.rfind("]") + 1
        json_str = content[start:end]
        arr = json.loads(json_str)
        if isinstance(arr, list):
            suggestions = [str(t) for t in arr]
        else:
            suggestions = []
    except Exception:
        suggestions = []

    return _dedup_and_filter(suggestions, tool_list)


# ---------------------------------------------------------------------------
# ヒューリスティックフォールバック
# ---------------------------------------------------------------------------

_KEYWORD_RULES: Dict[str, str] = {
    r"入金|CSV": "read_deposit_file",
    r"請求|Excel": "read_billing_file",
    r"突合|キー": "match_data_by_key",
    r"金額|差額": "validate_and_sort_matches",
    r"reconciled": "write_reconciled_csv",
    r"unreconciled": "write_unreconciled_csv",
    r"人間|確認": "human_validator",
}

def _suggest_via_heuristic(task_lines: List[str], tool_list: List[str]) -> List[str]:
    suggestions: List[str] = []
    for line in task_lines:
        tool = "none"
        for pattern, candidate in _KEYWORD_RULES.items():
            if re.search(pattern, line, flags=re.I):
                tool = candidate
                break
        suggestions.append(tool)
    return _dedup_and_filter(suggestions, tool_list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dedup_and_filter(seq: List[str], tool_list: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for t in seq:
        if t == "none":
            continue
        if t not in tool_list:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out 