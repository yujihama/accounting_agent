from typing import TypedDict, List, Dict, Any, Optional


class AppState(TypedDict, total=False):
    """YAMLで定義されたstateスキーマをそのままTypedDictで表現"""

    # ユーザー入力
    input_files: Dict[str, str]

    # 読み込み済みデータ
    raw_deposit_data: List[Dict[str, Any]]
    raw_billing_data: List[Dict[str, Any]]

    # 突合結果
    matching_results: Dict[str, Any]

    # 消込結果
    reconciled_list: List[Dict[str, Any]]
    unreconciled_list: List[Dict[str, Any]]

    # 出力ファイルパス
    final_output_paths: Dict[str, str]

    # プランナー決定
    plan_next: str

    # ヒューマンバリデータの結果
    human_validation_answer: bool

    # 作業指示書
    instruction_tasks: List[str]

    # 推奨ツールキュー
    suggested_queue: List[str]

    # 実行済みツール
    _executed_tools: List[str]

    # 専門家エージェント呼び出し
    next_agent: str
    agent_parameters: Dict[str, Any]

    # エラー情報
    errors: List[str]
