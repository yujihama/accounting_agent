import os
from typing import List, Dict
import pandas as pd


def csv_writer(data: List[Dict], output_path: str) -> str:
    """リスト形式のデータをCSVとして書き出す。戻り値は生成されたファイルのパス。"""
    if not data:
        # 空データの場合はヘッダーなしで空ファイルを生成
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        open(output_path, "w", encoding="utf-8").close()
        return output_path

    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    return output_path 