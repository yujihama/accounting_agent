import random


def human_validator(question_text: str) -> bool:
    """ユーザーに Yes/No を確認するヒューマンバリデータツール。

    現時点ではユーザー入力は行わず、ランダムに True/False を返す。
    LangGraph interrupt などによる human-in-the-loop は将来的に置き換える予定。

    Args:
        question_text (str): 確認メッセージ。

    Returns:
        bool: True (はい) もしくは False (いいえ) をランダムに返す。
    """

    print(f"[human_validator] QUESTION: {question_text}")
    answer: bool = random.choice([True, False])
    print(f"[human_validator] ANSWER  : {'はい' if answer else 'いいえ'} (自動生成)")
    return answer 