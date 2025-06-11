# AI経理エージェント PoC (Phase 1)

このリポジトリは、LangGraph を用いた **売上債権の消込ワークフロー** の PoC 実装です。

## セットアップ手順 (Windows / PowerShell)

```powershell
# 1. 仮想環境の作成 (任意)
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. 依存ライブラリのインストール
pip install -r requirements.txt
```

## 実行方法

```powershell
python -m src.workflow --deposit path\to\deposit.csv --billing path\to\billing.xlsx
```

実行完了後、以下のファイルが `output` フォルダに生成されます。

* `reconciled.csv` — 消込完了データ
* `unreconciled.csv` — 消込不能データ

## フォルダ構成

```
accounting_agent/
├─ doc/                 # 仕様・設計資料
├─ src/                 # Python パッケージ
│  ├─ tools/            # ツール実装
│  ├─ nodes.py          # Node 関数群
│  ├─ state.py          # 共通 State 型
│  └─ workflow.py       # LangGraph 定義 & 実行入口
├─ requirements.txt
└─ README.md            # このファイル
```

## 参考

* `doc/作業指示書.md`
* `doc/グラフ設計.yaml` 