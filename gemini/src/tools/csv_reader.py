import pandas as pd
from typing import List, Dict


def csv_reader(file_path: str) -> List[Dict]:
    """CSVファイルを読み込み、各行を辞書として返すユーティリティ関数。"""
    df = pd.read_csv(file_path)
    return df.to_dict(orient="records") 