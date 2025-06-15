from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.workflows.generic_matching_workflow import generic_matching_workflow  # noqa: E402


def test_hybrid_key_specification_model():
    # ケース1: キー指定あり
    result1 = generic_matching_workflow(
        source_file=str(PROJECT_ROOT / "sample" / "deposit_mismatch.csv"),
        target_file=str(PROJECT_ROOT / "sample" / "billing.xlsx"),
        match_keys={"source": "receipt_no", "target": "invoice_number"},
    )
    assert "reconciled" in result1

    # ケース2: キー指定なし（自動推定）。LLM が利用できない環境では RuntimeError を許容
    try:
        result2 = generic_matching_workflow(
            source_file=str(PROJECT_ROOT / "sample" / "deposit_mismatch.csv"),
            target_file=str(PROJECT_ROOT / "sample" / "billing.xlsx"),
            match_keys=None,
        )
        assert "reconciled" in result2
    except RuntimeError:
        pass
