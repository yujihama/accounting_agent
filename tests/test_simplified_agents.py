import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.receivables_reconciliation_agent import receivables_reconciliation_agent  # noqa: E402
from src.agents.inventory_matching_agent import inventory_matching_agent  # noqa: E402
from src.agents.employee_data_validator_agent import employee_data_validator_agent  # noqa: E402


def test_receivables_agent_adapter(tmp_path):
    state = {
        "input_files": {
            "deposit": str(PROJECT_ROOT / "sample" / "deposit_mismatch.csv"),
            "billing": str(PROJECT_ROOT / "sample" / "billing.xlsx"),
        },
        "agent_parameters": {
            "match_keys": {"source": "receipt_no", "target": "invoice_number"},
            "output_dir": str(tmp_path),
        },
    }
    result = receivables_reconciliation_agent(state)
    assert result["plan_next"] == "__end__"
    assert result.get("final_output_paths")


def test_inventory_agent_adapter(tmp_path):
    state = {
        "input_files": {
            "inventory": str(PROJECT_ROOT / "sample" / "system_inventory.csv"),
            "stock": str(PROJECT_ROOT / "sample" / "physical_inventory.xlsx"),
        },
        "agent_parameters": {"output_dir": str(tmp_path)},
    }
    result = inventory_matching_agent(state)
    assert result["plan_next"] == "__end__"


def test_employee_validator_adapter(tmp_path):
    state = {
        "input_files": {
            "master": str(PROJECT_ROOT / "sample" / "hr_master.csv"),
            "list": str(PROJECT_ROOT / "sample" / "dev_dept_list.xlsx"),
        }
    }
    result = employee_data_validator_agent(state)
    assert result["plan_next"] == "__end__"
