from __future__ import annotations

"""specialist_agent.py

各専門エージェント向けに LangGraph グラフを簡単に構築するヘルパ。
node_map = {node_name: callable} を渡すと、
  * generic_planner.make_planner で生成した planner ノード
  * node_map で渡された各ノード
を含む StateGraph を返す。

ノード終了後には自動で _executed_tools に記録されるため、Planner が進捗を判断できる。
"""

from typing import Callable, Dict, Any

from langgraph.graph import StateGraph, END  # type: ignore

from src.state import AppState
from src.planners.generic_planner import make_planner

# ------------------------------------------------------------
# 公開関数
# ------------------------------------------------------------

def build_specialist_graph(node_map: Dict[str, Callable[[AppState], AppState]]):  # noqa: D401
    """node_map を基に StateGraph を生成して返却する。"""

    tool_names = list(node_map.keys())
    planner = make_planner(tool_names)

    # 実行済みフラグを付与するラッパ
    def _wrap(name: str, fn: Callable[[AppState], AppState]):  # noqa: D401
        def _inner(state: AppState) -> AppState:  # type: ignore[override]
            state.setdefault("_executed_tools", []).append(name)
            return fn(state)
        return _inner

    sg: StateGraph = StateGraph(AppState)
    sg.add_node("planner", planner)

    for n, f in node_map.items():
        sg.add_node(n, _wrap(n, f))
        sg.add_edge(n, "planner")  # 各ノード完了後は planner へ戻す

    sg.set_entry_point("planner")

    sg.add_conditional_edges(
        "planner",
        lambda s: s.get("plan_next", "__end__"),
        {**{name: name for name in tool_names}, "__end__": END},
    )

    return sg.compile() 