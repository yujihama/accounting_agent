import pandas as pd
from typing import List, Dict


def excel_reader(file_path: str, sheet_name: str | int | None = 0) -> List[Dict]:
    """Excelファイルを読み込み、各行を辞書として返すユーティリティ関数。デフォルトで最初のシートを読み取る。"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
    return df.to_dict(orient="records") 