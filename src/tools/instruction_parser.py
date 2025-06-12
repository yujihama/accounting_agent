from __future__ import annotations

"""instruction_parser.py

Markdown / テキスト形式の作業指示書を読み込み、実行すべきタスク文のリストを返すユーティリティ。

Phase-3 以降では LLM を優先的に利用してタスクを抽出し、利用できない場合や失敗時には従来の
ヒューリスティック（箇条書き抽出）へフォールバックする二段構えとする。
"""

from pathlib import Path
from typing import List, Any
import os
import re

# LLM オプション（langchain_openai がインストールされていない環境も考慮）
try:
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain.schema import SystemMessage, HumanMessage  # type: ignore
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


# ------------------------------------------------------------
# ヒューリスティック用正規表現
# ------------------------------------------------------------

_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------


def parse_instruction_file(path: str | Path) -> List[str]:
    """作業指示書を読み込み、タスク行のリストを返す。

    ChatOpenAI と `OPENAI_API_KEY` が利用可能な前提で、LLM でタスク抽出を行います。
    何らかの理由で LLM が利用できない、または抽出に失敗した場合は例外を送出します。
    """

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Instruction file not found: {p}")

    file_content = p.read_text(encoding="utf-8")

    # LLM 利用前提チェック
    if ChatOpenAI is None:
        raise RuntimeError("ChatOpenAI (langchain_openai) が利用できません。モジュールがインストールされているか確認してください。")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY が設定されていません。環境変数に API キーを設定してください。")

    # LLM による抽出（失敗時は例外をそのまま上位へ）
    tasks_llm = _extract_via_llm(file_content)
    if not tasks_llm:
        raise RuntimeError("LLM によるタスク抽出結果が空でした。指示書の内容を確認してください。")

    return tasks_llm


# ------------------------------------------------------------
# LLM ベースの抽出
# ------------------------------------------------------------


def _extract_via_llm(markdown_text: str) -> List[str]:
    """ChatOpenAI を用いてタスク行を抽出する。

    ``markdown_text`` に含まれる手順・指示の箇条書きを出来るだけ漏れなく抽出して
    リスト形式で返す。出力フォーマットは以下のいずれかを許可するが、最終的には
    Python 側で行配列 ``List[str]`` に正規化する。

    - 行区切りテキスト（改行区切り）
    - JSON 配列 (例: ["task1", "task2", ...])
    """

    llm = ChatOpenAI(model_name="gpt-4.1-mini", temperature=0.0, max_tokens=512)

    system_prompt = (
        "あなたはプロジェクトマネージャーです。ユーザーから渡されたMarkdown形式の作業指示書から、" \
        "実行すべきタスクを漏れなく抽出してください。出力は日本語で、番号や記号を付けずにタスク文のみを" \
        "1 行ずつ列挙するか、JSON 配列で返してください。余計な説明や前後のテキストは含めないでください。"
    )

    user_prompt = (
        "####################\n"  # 明示的に境界を示しプロンプト混入を防ぐ
        "以下が作業指示書の全文です:\n\n"
        f"{markdown_text}\n"
        "####################"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    # --------------------------------------------------------
    # Structured output (PydanticOutputParser) による解析
    # --------------------------------------------------------

    # 遅延 import（pydantic / output_parsers が無い環境を考慮）
    try:
        from pydantic import BaseModel, Field  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pydantic がインストールされていません") from e

    class TaskListModel(BaseModel):  # pylint: disable=too-few-public-methods
        """LLM から受け取るタスク一覧のスキーマ"""

        tasks: List[str] = Field(..., description="抽出したタスクを格納する配列")

    # PydanticOutputParser の import 経路差異に対応
    try:
        from langchain.output_parsers import PydanticOutputParser  # type: ignore
    except ImportError:
        try:
            from langchain_core.output_parsers import PydanticOutputParser  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("PydanticOutputParser が import できません") from e

    # ----------------------------
    # PydanticOutputParser インスタンス生成
    # ----------------------------
    parser: Any
    try:
        parser = PydanticOutputParser(pydantic_object=TaskListModel)  # type: ignore[arg-type]
    except Exception:
        try:
            parser = PydanticOutputParser(schema=TaskListModel)  # type: ignore[arg-type]
        except Exception:
            parser = PydanticOutputParser(pydantic_schema=TaskListModel)  # type: ignore[arg-type]

    # PydanticOutputParser で指定されたフォーマット指示を system prompt に組み込む
    format_instructions = parser.get_format_instructions()

    system_prompt_with_format = (
        "あなたはプロジェクトマネージャーです。ユーザーから渡されたMarkdown形式の作業指示書から、"  # noqa: E501
        "実行すべきタスクを漏れなく抽出してください。"  # noqa: E501
        f"\n{format_instructions}"
    )

    # messages を再構築
    messages_struct = [
        SystemMessage(content=system_prompt_with_format),
        HumanMessage(content=user_prompt),
    ]

    response_struct = llm.invoke(messages_struct)
    content_struct = response_struct.content if hasattr(response_struct, "content") else str(response_struct)

    try:
        parsed: TaskListModel = parser.parse(content_struct)
    except Exception as e:
        # 解析失敗時は例外を伝播してフォールバックさせる
        raise RuntimeError("LLM 出力の構造化解析に失敗しました") from e

    # tasks をクリーニングして返却
    return [t.strip() for t in parsed.tasks if str(t).strip()] 