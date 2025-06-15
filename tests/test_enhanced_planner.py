import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.planners.generic_planner import make_enhanced_planner  # noqa: E402


def test_enhanced_planner_with_explicit_keys():
    state = {
        "input_files": {
            "instruction": str(PROJECT_ROOT / "sample" / "instruction_reconciliation.md"),
            "deposit": str(PROJECT_ROOT / "sample" / "deposit_mismatch.csv"),
            "billing": str(PROJECT_ROOT / "sample" / "billing.xlsx"),
        }
    }
    planner = make_enhanced_planner()
    result = planner(state)
    assert "next_agent" in result
    assert "agent_parameters" in result
    # match_keys may be None when LLM is unavailable
    if result["agent_parameters"].get("match_keys"):
        assert "source" in result["agent_parameters"]["match_keys"]
        assert "target" in result["agent_parameters"]["match_keys"]
