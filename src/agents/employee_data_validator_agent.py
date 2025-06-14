from __future__ import annotations

from typing import Any, Dict, List
import pathlib

from src.state import AppState
from src.tools.csv_reader import csv_reader  # type: ignore
from src.tools.excel_reader import excel_reader  # type: ignore
from src.tools.csv_writer import csv_writer  # type: ignore
from src.agent_framework.specialist_agent import build_specialist_graph


# ---------------------------------------------------------------------------
# 補助関数
# ---------------------------------------------------------------------------

def _read(path: str) -> List[Dict[str, Any]]:
    """拡張子で CSV / Excel を自動判定して読み込む"""
    ext = pathlib.Path(path).suffix.lower()
    if ext == ".csv":
        return csv_reader(path)
    elif ext in {".xlsx", ".xls"}:
        return excel_reader(path)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


# ---------------------------------------------------------------------------
# ノード定義
# ---------------------------------------------------------------------------

def _validate_hr(state: AppState) -> AppState:
    """人事マスタと部門リストの不整合を検出し CSV 出力"""
    master_file = state.get("input_files", {}).get("deposit")  # type: ignore[assignment]
    dept_file = state.get("input_files", {}).get("billing")  # type: ignore[assignment]

    if not master_file or not dept_file:
        raise RuntimeError("employee_data_validator_agent: 必要な input_files が不足しています。")

    master_rows = _read(master_file)
    dept_rows = _read(dept_file)

    master_index = {str(r.get("employee_id")): r for r in master_rows}

    report_rows: List[Dict[str, Any]] = []
    for d in dept_rows:
        emp_id = str(d.get("emp_id"))
        m = master_index.get(emp_id)
        if not m:
            continue

        if m.get("department_code") != d.get("dept"):
            report_rows.append(
                {
                    "employee_id": emp_id,
                    "field": "department_code",
                    "master_value": m.get("department_code"),
                    "list_value": d.get("dept"),
                    "severity": "Warning",
                }
            )

        if m.get("title_code") != d.get("title_code"):
            report_rows.append(
                {
                    "employee_id": emp_id,
                    "field": "title_code",
                    "master_value": m.get("title_code"),
                    "list_value": d.get("title_code"),
                    "severity": "Error",
                }
            )

    output_dir = pathlib.Path("output").resolve()
    output_dir.mkdir(exist_ok=True)
    report_path = str(output_dir / "inconsistent_hr_data.csv")
    csv_writer(report_rows, report_path)

    state.setdefault("final_output_paths", {})["inconsistent_hr_data"] = report_path
    return state


# ---------------------------------------------------------------------------
# LangGraph 構築
# ---------------------------------------------------------------------------

_NODE_MAP = {
    "validate_hr_data": _validate_hr,
}

_GRAPH = build_specialist_graph(_NODE_MAP)


# ---------------------------------------------------------------------------
# エージェント関数
# ---------------------------------------------------------------------------

def employee_data_validator_agent(state: AppState) -> AppState:  # noqa: D401
    """人事データ検証エージェント (planner 付き LangGraph 版)"""
    final_state = _GRAPH.invoke(state)
    final_state["plan_next"] = "__end__"
    return final_state 