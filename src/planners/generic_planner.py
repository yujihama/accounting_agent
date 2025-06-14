from __future__ import annotations

"""generic_planner.py

監督／専門エージェント双方で再利用できる汎用 Planner 生成ユーティリティ。
与えられたツール名リストだけを候補として、state["plan_next"] に次ノード名を格納する
callable を返す。

特徴:
* OPENAI_API_KEY があれば LLM (ChatGPT) に選択を任せる。
* API キーが無い場合、未実行ツールを順番に実行し最後に '__end__' を返す単純戦略へフォールバック。
* JSON スキーマ検証には PydanticOutputParser を利用。
"""

from typing import Callable, List, Dict, Any
from enum import Enum
import os

# langchain / output parser
try:
    from langchain.output_parsers import PydanticOutputParser  # type: ignore
except ImportError:  # pragma: no cover
    from langchain_core.output_parsers import PydanticOutputParser  # type: ignore

try:
    from langchain_openai import ChatOpenAI  # type: ignore
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore

from pydantic import BaseModel, Field  # type: ignore

# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def make_planner(tool_names: List[str]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:  # noqa: D401
    """tool_names に限定された遷移先を返す planner を生成して返す。"""

    # Enum 動的生成 --------------------------------------------------
    mapping = {name: name for name in tool_names + ["__end__"]}
    NextEnum = Enum("NextEnum", mapping)  # type: ignore[arg-type]

    class _NextModel(BaseModel):  # pylint: disable=too-few-public-methods
        next_node: NextEnum = Field(..., description="次に実行するツール名")

    parser = PydanticOutputParser(pydantic_object=_NextModel)

    # ---------------------------------------------
    # planner 本体 (クロージャ内で tool_names を参照)
    # ---------------------------------------------
    def _planner(state: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore[override]
        # 既に終了が決定していれば何もしない
        if state.get("plan_next") == "__end__":
            return state

        executed: List[str] = state.get("_executed_tools", [])
        remaining = [t for t in tool_names if t not in executed]
        fallback_next = remaining[0] if remaining else "__end__"

        # API キー未設定 or ChatOpenAI 利用不可ならフォールバック
        if ChatOpenAI is None or not os.getenv("OPENAI_API_KEY"):
            state["plan_next"] = fallback_next
            return state

        # ------ LLM へ問い合わせ ------
        llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=32)
        system_prompt = (
            "You are a workflow planner. Select the next tool strictly from the list and return JSON only.\n"
            + parser.get_format_instructions()
        )
        user_prompt = (
            "Available tools: " + ", ".join(tool_names) + "\n"
            "Already executed: " + ", ".join(executed) + "\n"
            "If nothing left, return __end__."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            resp = llm.invoke(messages)
            raw = resp.content if hasattr(resp, "content") else resp
            parsed: _NextModel = parser.parse(raw)
            next_node = parsed.next_node.value
        except Exception:
            next_node = fallback_next

        # 最終決定
        state["plan_next"] = next_node
        return state

    return _planner 