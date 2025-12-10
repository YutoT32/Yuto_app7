# 見どころエージェント

Google検索を利用して沖縄の見どころや観光スポットを紹介するエージェントです。
最新の観光情報、アクセス方法、営業時間などをリアルタイムで検索して提供します。

## 必要環境

- uv (Pythonのパッケージマネージャー)

uv環境がない場合は、必要に応じて以下の通りインストールしてください。
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

## 環境構築

```bash
# (必要に応じて) Python 3.13のインストール
uv python install 3.13

# プロジェクトのPythonバージョンを3.13に固定
uv python pin 3.13

# 必要なパッケージのインストール
uv sync
```

## 実行方法

```bash
uv run python __main__.py --host=0.0.0.0 --port 10002
```

## テスト方法

エージェントが起動した状態で、別のターミナルから以下のコマンドでテストできます:

```bash
uv run python test_client.py
```
