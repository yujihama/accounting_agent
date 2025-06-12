import os
from pathlib import Path

import pytest  # type: ignore

# src モジュールのインポートは PYTHONPATH に依存しないように絶対パスを追加
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

import src.workflow as workflow  # noqa: E402


@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY が設定されていないため、LLM を利用した統合テストをスキップします。",
)
def test_workflow_runs_with_real_llm(tmp_path):
    """実際の OpenAI API を用いてワークフローが最後まで完了することを検証する。"""
    deposit_path = PROJECT_ROOT / "sample" / "deposit_mismatch.csv"
    billing_path = PROJECT_ROOT / "sample" / "billing.xlsx"
    instruction_path = PROJECT_ROOT / "doc" / "sample_instruction.md"

    # 実行
    final_state = workflow.run_workflow(str(deposit_path), str(billing_path), str(instruction_path))

    # ワークフローが正常終了しているかを確認
    assert final_state.get("plan_next") == "__end__"

    # 出力ファイルの生成を確認
    outputs = final_state["final_output_paths"]
    for key in ("reconciled", "unreconciled"):
        out_path = PROJECT_ROOT / outputs[key]
        assert out_path.exists(), f"出力ファイル {out_path} が存在しません"

    # 推奨ツールキューが state に含まれるか
    assert "suggested_queue" in final_state and final_state["suggested_queue"], "推奨キューが生成されていません" 