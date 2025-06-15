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

from typing import Callable, List, Dict, Any, Optional
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
from ..tools.instruction_parser import parse_instruction_file

# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def make_enhanced_planner() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Hybrid Key-Specification Model対応の監督エージェントを生成"""

    class MatchKeys(BaseModel):  # pylint: disable=too-few-public-methods
        source: str = Field(..., description="ソースデータの突合キー名")
        target: str = Field(..., description="ターゲットデータの突合キー名")

    class ValidationRule(BaseModel):  # pylint: disable=too-few-public-methods
        field: str = Field(..., description="検証する項目名")
        target_field: Optional[str] = Field(None, description="比較対象の項目名")
        severity: str = Field("Error", description="報告レベル")
        validator: Optional[str] = Field(None, description="検証タイプ")
        tolerance_pct: Optional[float] = Field(None, description="許容誤差(%)")

        model_config = {"extra": "allow"}

    class AgentParameters(BaseModel):  # pylint: disable=too-few-public-methods
        match_keys: Optional[MatchKeys] = Field(None, description="突合キー（手順書に明記されている場合のみ）")
        validation_rules: List[ValidationRule] = Field(default_factory=list, description="検証ルール")
        source_file: Optional[str] = Field(None, description="ソースファイルパス")
        target_file: Optional[str] = Field(None, description="ターゲットファイルパス")
        output_dir: str = Field(default="output", description="出力ディレクトリ")
        numeric_field: str = Field(default="amount", description="数値フィールド名")
        target_numeric_field: Optional[str] = Field(None, description="ターゲット側数値フィールド名")
        tolerance_pct: float = Field(default=0.0, description="許容誤差パーセンテージ")

        model_config = {"extra": "allow"}

    class AgentEnum(str, Enum):
        receivables_reconciliation_agent = "receivables_reconciliation_agent"
        inventory_matching_agent = "inventory_matching_agent"
        employee_data_validator_agent = "employee_data_validator_agent"

    class PlannerOutput(BaseModel):  # pylint: disable=too-few-public-methods
        next_agent: AgentEnum = Field(..., description="次に実行する専門家エージェント名")
        agent_parameters: AgentParameters = Field(..., description="専門家エージェントへのパラメータ")

    def _enhanced_planner(state: Dict[str, Any]) -> Dict[str, Any]:
        """手順書解釈とパラメータ抽出を行う監督エージェント"""

        if state.get("plan_next") == "__end__":
            return state

        instruction_file = state.get("input_files", {}).get("instruction")
        instruction_tasks: List[str] = []
        if instruction_file:
            try:
                instruction_tasks = parse_instruction_file(instruction_file)
                state["instruction_tasks"] = instruction_tasks
            except Exception as e:  # pragma: no cover - parser errors not fatal
                print(f"Warning: Failed to parse instruction file: {e}")

        if ChatOpenAI is None or not os.getenv("OPENAI_API_KEY"):
            state["next_agent"] = "receivables_reconciliation_agent"
            state["plan_next"] = "receivables_reconciliation_agent"
            state["agent_parameters"] = {
                "source_file": state.get("input_files", {}).get("deposit"),
                "target_file": state.get("input_files", {}).get("billing"),
                "output_dir": "output",
            }
            return state

        try:
            llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=1024)
            parser = PydanticOutputParser(pydantic_object=PlannerOutput)

            instruction_content = "\n".join(instruction_tasks) if instruction_tasks else "手順書なし"
            input_files = state.get("input_files", {})

            system_prompt = f"""
あなたは経理業務の監督エージェントです。手順書の内容を解釈し、適切な専門家エージェントと
そのエージェントが必要とするパラメータを抽出してください。

利用可能な専門家エージェント:
- receivables_reconciliation_agent: 売掛金消込業務
- inventory_matching_agent: 在庫照合業務  
- employee_data_validator_agent: 人事データ検証業務

重要な指示（Hybrid Key-Specification Modelの核心）:
1. match_keysは手順書に突合キーが明確に記載されている場合のみ抽出してください
2. 記載がない場合はmatch_keysをnullにしてください（後で自動推定されます）
3. 手順書の内容に基づいて適切なvalidation_rulesを設定してください
4. 数値フィールドの許容誤差が指定されている場合はtolerance_pctに設定してください

{parser.get_format_instructions()}
"""

            user_prompt = f"""
手順書の内容:
{instruction_content}

入力ファイル情報:
- deposit: {input_files.get('deposit', 'なし')}
- billing: {input_files.get('billing', 'なし')}

この情報に基づいて、次に実行すべき専門家エージェントとパラメータを決定してください。
特に、突合キーが手順書に明記されているかどうかを慎重に判断してください。
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            resp = llm.invoke(messages)
            raw = resp.content if hasattr(resp, "content") else resp
            parsed: PlannerOutput = parser.parse(raw)

            state["next_agent"] = parsed.next_agent.value
            state["agent_parameters"] = parsed.agent_parameters.model_dump(exclude_none=True)
            state["plan_next"] = parsed.next_agent.value

            print(f"監督エージェント決定: {parsed.next_agent.value}")
            if parsed.agent_parameters.match_keys:
                print(f"突合キー指定: {parsed.agent_parameters.match_keys.model_dump()}")
            else:
                print("突合キー未指定 - 自動推定を実行します")

        except Exception as e:  # pragma: no cover - fallback path
            print(f"Warning: LLM parameter extraction failed: {e}")
            state["next_agent"] = "receivables_reconciliation_agent"
            state["plan_next"] = "receivables_reconciliation_agent"
            state["agent_parameters"] = {
                "source_file": input_files.get("deposit"),
                "target_file": input_files.get("billing"),
                "output_dir": "output",
            }

        return state

    return _enhanced_planner
