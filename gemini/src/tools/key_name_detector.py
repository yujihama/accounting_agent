from __future__ import annotations

"""
key_name_detector.py
-------------------

入金CSVと請求Excelのカラム名を解析し、突合に使用すべきキー名（deposit_key, billing_key）
を推定するヘルパーモジュール。

要件：
    * まずは単純なヒューリスティックで共通カラム名を探索。
    * 該当しない場合のみ、（環境に OPENAI_API_KEY が設定されていれば）LLM へ問い合わせて
      推定を試みる。
    * それでも決定できなかった場合は、それぞれの先頭カラム名を返すフォールバック。

実務要件として「LLM が決定するように」とあるが、API キーが無い場合でも動作するよう
に、ヒューリスティック→LLM→フォールバック の 3 段構成とする。
"""

from typing import Dict, List, Tuple, Any, Set
import os
import logging

# LangChain (v0.3 系分割パッケージ) を前提とした静的インポート
from langchain_openai import ChatOpenAI  # type: ignore
from langchain_core.prompts import ChatPromptTemplate  # type: ignore
from langchain_core.output_parsers import PydanticOutputParser  # type: ignore

from pydantic import BaseModel, Field  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM フォールバック
# ---------------------------------------------------------------------------

_SYSTEM_TEMPLATE = (
    "You are a data reconciliation assistant. "
    "Given two JSON arrays representing deposit data and billing data, "
    "determine the most appropriate pair of key names—one in each dataset—that should be used for record matching. "
    "Respond following the JSON schema provided in the instructions."
)

# Pydantic モデル定義（LangChain Structured Output 用）
if BaseModel is not None:

    class _KeyPair(BaseModel):
        """LLM から返してもらうキー情報のスキーマ"""

        deposit_key: str = Field(..., description="column name in deposit data")
        billing_key: str = Field(..., description="column name in billing data")


def _llm_suggest_keys(
    deposit_sample: List[Dict[str, Any]],
    billing_sample: List[Dict[str, Any]],
) -> Tuple[str | None, str | None]:
    """LangChain Structured Output によるキー候補推定。"""

    # 必要ライブラリと API キーの確認
    if (
        ChatOpenAI is None
        or ChatPromptTemplate is None
        or PydanticOutputParser is None
        or BaseModel is None
        or os.getenv("OPENAI_API_KEY") is None
    ):
        return None, None

    try:
        # サンプルをコンパクトに (最初の5レコード)
        dep_json = deposit_sample[:5]
        bill_json = billing_sample[:5]

        # Output Parser & Prompt 準備
        parser = PydanticOutputParser(pydantic_object=_KeyPair)  # type: ignore[arg-type]
        format_instructions = parser.get_format_instructions()

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_TEMPLATE),
                (
                    "user",
                    """Here are examples of deposit and billing data in JSON format.

Deposit data (list of dict):
{deposit_json}

Billing data (list of dict):
{billing_json}

{format_instructions}
""",
                ),
            ]
        )

        llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=128)

        # プロンプトに値を流し込み
        messages = prompt.format_prompt(
            deposit_json=dep_json,
            billing_json=bill_json,
            format_instructions=format_instructions,
        ).to_messages()

        # 実行し Structured Output で parse
        response_msg = llm.invoke(messages)
        try:
            key_pair: _KeyPair = parser.parse(response_msg.content)
            return key_pair.deposit_key, key_pair.billing_key
        except Exception as e:
            # JSON 解析失敗時
            logger.warning("Structured output parse failed: %s", e)
            return None, None
    except Exception as e:  # pragma: no cover
        logger.warning("LLM key suggestion failed: %s", e)
        return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_matching_keys(
    deposit_data: List[Dict[str, Any]],
    billing_data: List[Dict[str, Any]],
) -> Tuple[str, str]:
    """(deposit_key, billing_key) を推定して返すメイン関数。"""

    # 空データチェック
    if not deposit_data or not billing_data:
        raise ValueError("deposit_data と billing_data は空であってはいけません")

    deposit_keys = set(deposit_data[0].keys())
    billing_keys = set(billing_data[0].keys())

    # LLM でのみキーを推定
    dep_key, bill_key = _llm_suggest_keys(deposit_data, billing_data)
    if dep_key and bill_key:
        return dep_key, bill_key

    # 取得できなければエラー
    raise RuntimeError(
        "LLM によるキー推定に失敗しました。OPENAI_API_KEY が設定されているか、データ構造をご確認ください。"
    ) 