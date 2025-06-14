import os
from pathlib import Path
import pytest  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PROJECT_ROOT))

import src.workflow as workflow  # noqa: E402


# ------------------------------------------------------------
# フェーズ3 3ユースケース共通テスト
# ------------------------------------------------------------

def _ensure_test_data():
    """サンプルデータが存在しなければ生成スクリプトを実行"""
    sample_files = [
        PROJECT_ROOT / "sample" / fname
        for fname in [
            "deposit_202506.csv",
            "billing_202505.xlsx",
            "system_inventory.csv",
            "physical_inventory.xlsx",
            "hr_master.csv",
            "dev_dept_list.xlsx",
        ]
    ]

    if not all(p.exists() for p in sample_files):
        from subprocess import run, PIPE

        gen_script = PROJECT_ROOT / "scripts" / "generate_phase3_test_data.py"
        run([sys.executable, str(gen_script)], check=True, stdout=PIPE, stderr=PIPE)


# テストパラメータ: (deposit_path, billing_path, instruction_path, expected_output_keys)
SCENARIOS = [
    (
        "deposit_202506.csv",
        "billing_202505.xlsx",
        "instruction_reconciliation.md",
        ("reconciled", "unreconciled"),
    ),
    (
        "system_inventory.csv",
        "physical_inventory.xlsx",
        "instruction_inventory.md",
        ("discrepancy_report",),
    ),
    (
        "hr_master.csv",
        "dev_dept_list.xlsx",
        "instruction_hr_validation.md",
        None,  # 期待アウトプット未確定: final_output_paths が空でないことのみを確認
    ),
]


@pytest.mark.skipif(
    "OPENAI_API_KEY" not in os.environ,
    reason="OPENAI_API_KEY が設定されていないため、LLM を利用した統合テストをスキップします。",
)
@pytest.mark.parametrize("deposit_fname, billing_fname, instruction_fname, expected_keys", SCENARIOS)
def test_phase3_scenarios(tmp_path, deposit_fname, billing_fname, instruction_fname, expected_keys):
    """フェーズ3 3ユースケースが最後まで完了することを検証"""
    _ensure_test_data()

    deposit_path = PROJECT_ROOT / "sample" / deposit_fname
    billing_path = PROJECT_ROOT / "sample" / billing_fname
    instruction_path = PROJECT_ROOT / "sample" / instruction_fname

    # 実行
    final_state = workflow.run_workflow(
        str(deposit_path), str(billing_path), str(instruction_path)
    )

    # ワークフローが正常終了しているかを確認
    assert final_state.get("plan_next") == "__end__"

    # 出力ファイルの存在を確認
    outputs = final_state.get("final_output_paths", {})
    assert outputs, "final_output_paths が空です"

    if expected_keys is None:
        # キー未定義シナリオ: 1 つ以上のファイルが存在することのみ確認
        for out_path in outputs.values():
            assert Path(out_path).exists(), f"出力ファイル {out_path} が存在しません"
    else:
        for key in expected_keys:
            assert (
                key in outputs
            ), f"{key} が final_output_paths に含まれていません: {outputs.keys()}"
            out_path = PROJECT_ROOT / outputs[key]
            assert out_path.exists(), f"出力ファイル {out_path} が存在しません" 