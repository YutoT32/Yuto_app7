# 技育CAMPアカデミア

A2A (Agent-to-Agent) プロトコルを使用したマルチエージェントデモアプリケーション

## プロジェクト概要

このプロジェクトは、Google ADK (Agent Development Kit) とA2Aプロトコルを使用して、複数のエージェント間で通信を行うデモアプリケーションです。

## エージェント一覧

以下のエージェントをサポートしています

- coordinator_agent: 起点となるエージェント。ユーザーからの質問を受け取り、適切な専門エージェントに問い合わせを行い、他のエージェントと連携してユーザーのリクエストを処理
- uchina_guchi_agnet: 日本語を沖縄方言（ウチナーグチ）に変換する専門エージェント

## 必要環境

- Python 3.13
- uv (Pythonパッケージマネージャー)
- Google API Key または Vertex AI環境

## セットアップ

各エージェントのディレクトリ内で以下を実行:

```bash
# Python 3.13のインストール（必要な場合）
uv python install 3.13
uv python pin 3.13

# パッケージのインストール
uv sync
```

## 環境変数

`.env`ファイルを作成し、以下を設定:

```bash
# Google AI API Key (Vertex AIを使用しない場合)
GOOGLE_API_KEY=your_api_key_here

# Vertex AI を使用する場合は TRUE を設定する
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# 使用するLLMモデル
LLM_MODEL_ID=gemini-2.5-flash
```

## 実行方法

### コーディネーターエージェントの起動

Streamlit UIを使用してコーディネーターエージェントを起動します:

```bash
cd coordinator_agent
uv run streamlit run ui.py --server.address 0.0.0.0
```

ブラウザで `http://localhost:8501` にアクセスしてチャットUIを使用できます。

### 専門エージェントの起動

各専門エージェントは独立したサーバーとして起動します:

```bash
# uchina_guchi_agentの起動
cd uchina_guchi_agent
uv run python __main__.py --host=0.0.0.0 --port=10001
```