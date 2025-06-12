import os
from pathlib import Path
import pytest  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

import src.workflow as workflow  # noqa: E402


@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY が設定されていないため、LLM を利用した統合テストをスキップします。",
)
def test_phase3_receivables(tmp_path):
    """フェーズ3 売掛金消込シナリオが最後まで完了することを検証"""
    deposit_path = PROJECT_ROOT / "sample" / "deposit_202506.csv"
    billing_path = PROJECT_ROOT / "sample" / "billing_202505.xlsx"
    instruction_path = PROJECT_ROOT / "sample" / "instruction_reconciliation.md"

    # データが事前に存在していなければ生成スクリプトを実行
    if not deposit_path.exists():
        from subprocess import run, PIPE
        gen_script = PROJECT_ROOT / "scripts" / "generate_phase3_test_data.py"
        run([sys.executable, str(gen_script)], check=True, stdout=PIPE, stderr=PIPE)

    final_state = workflow.run_workflow(str(deposit_path), str(billing_path), str(instruction_path))

    assert final_state.get("plan_next") == "__end__"

    outputs = final_state["final_output_paths"]
    for key in ("reconciled", "unreconciled"):
        out_path = PROJECT_ROOT / outputs[key]
        assert out_path.exists(), f"出力ファイル {out_path} が存在しません" 