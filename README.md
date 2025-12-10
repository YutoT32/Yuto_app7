# 技育CAMPアカデミア

A2A (Agent-to-Agent) プロトコルを使用したマルチエージェントデモアプリケーション

## プロジェクト概要

このプロジェクトは、Google ADK (Agent Development Kit) とA2Aプロトコルを使用して、複数のエージェント間で通信を行うデモアプリケーションです。

## エージェント一覧

以下のエージェントをサポートしています

- **coordinator_agent**: 起点となるエージェント。ユーザーからの質問を受け取り、ウチナーグチエージェントと連携してユーザーのリクエストを処理
- **coordinator_agent_with_midokoro**: ウチナーグチエージェントと見どころエージェントを統合したコーディネーターエージェント
- **uchina_guchi_agent**: 日本語を沖縄方言（ウチナーグチ）に変換する専門エージェント
- **midokoro_agent**: Google検索を利用して沖縄の観光情報（観光スポット、アクセス方法、営業時間など）を提供する専門エージェント

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

各エージェントのディレクトリ内に `.env` ファイルを作成し、以下を設定:

```bash
# Google AI API Key (Vertex AIを使用しない場合)
GOOGLE_API_KEY=your_api_key_here

# Vertex AI を使用する場合は TRUE を設定する
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# 使用するLLMモデル
LLM_MODEL_ID=gemini-2.0-flash

# 専門エージェントのURL（コーディネーターエージェントで使用）
UCHINA_GUCHI_AGENT_URL=http://0.0.0.0:10001
MIDOKORO_AGENT_URL=http://0.0.0.0:10002
```

## 実行方法

### coordinator_agent の起動

#### 1. 専門エージェントを起動

**ターミナル1: ウチナーグチエージェント**
```bash
cd uchina_guchi_agent
uv run python __main__.py --host=0.0.0.0 --port=10001
```

#### 2. コーディネーターUIを起動

**ターミナル2: コーディネーター**
```bash
cd coordinator_agent
uv run streamlit run ui.py
```

ブラウザで `http://localhost:8501` にアクセスしてチャットUIを使用できます。

---

### coordinator_agent_with_midokoro の起動

#### 1. 各エージェントを起動

まず、各専門エージェントを別々のターミナルで起動してください：

**ターミナル1: ウチナーグチエージェント**
```bash
cd uchina_guchi_agent
uv run python __main__.py --host=0.0.0.0 --port=10001
```

**ターミナル2: 見どころエージェント**
```bash
cd midokoro_agent
uv run python __main__.py --host=0.0.0.0 --port=10002
```

#### 2. コーディネーターUIを起動

**ターミナル3: コーディネーター**
```bash
cd coordinator_agent_with_midokoro
uv run streamlit run ui.py
```

ブラウザで `http://localhost:8501` にアクセスしてチャットUIを使用できます。