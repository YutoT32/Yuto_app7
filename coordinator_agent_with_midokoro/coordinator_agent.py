from typing import Any, List, Dict, Optional
import json
import httpx
import uuid
import asyncio
import re

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.tools import load_memory
from a2a.client import A2ACardResolver

from a2a.types import (
    SendMessageResponse,
    SendMessageRequest,
    MessageSendParams,
    SendMessageSuccessResponse,
    Task,
    Part,
    AgentCard,
)

from remote_agent_connection import RemoteAgentConnections, TaskUpdateCallback

# 各エージェントのURLを環境変数から取得
from config import LLM_MODEL_ID, UCHINA_GUCHI_AGENT_URL, MIDOKORO_AGENT_URL

from dotenv import load_dotenv
load_dotenv()


def convert_part(part: Part, tool_context: ToolContext):
    if part.type == "text":
        return part.text

    return f"Unknown type: {part.type}"


def convert_parts(parts: list[Part], tool_context: ToolContext):
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": text}],
            "messageId": uuid.uuid4().hex,
        },
    }

    if task_id:
        payload["message"]["taskId"] = task_id

    if context_id:
        payload["message"]["contextId"] = context_id

    return payload


class CoordinatorAgent:
    def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ""

    async def _async_init_components(self, remote_agent_addresses: List[str]):
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(client, address)
                try:
                    card = await card_resolver.get_agent_card()

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(f"ERROR: Failed to get agent card from {address}: {e}")
                except Exception as e:
                    print(f"ERROR: Failed to initialize connection for {address}: {e}")

    async def aclose(self):
        """すべてのリモートエージェント接続を安全にクローズする"""
        for name, connection in self.remote_agent_connections.items():
            try:
                await connection.aclose()
                print(f"Closed connection to {name}")
            except Exception as e:
                print(f"Warning: Error closing connection to {name}: {e}")

        # 接続辞書をクリア
        self.remote_agent_connections.clear()
        self.cards.clear()

        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = "\n".join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: List[str],
        task_callback: TaskUpdateCallback | None = None,
    ):
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        return Agent(
            model=LLM_MODEL_ID,
            name="コーディネーターエージェント",
            instruction=self.coordinator_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                "ユーザーからの質問に対して、適切な専門エージェントに問い合わせて回答を提供します。"
            ),
            tools=[
                self.send_message,
                self.send_messages_parallel,
                self.send_message_chain,
                self.analyze_query_intent,
                load_memory
            ],
        )

    def coordinator_instruction(self, context: ReadonlyContext) -> str:
        current_agent = self.check_active_agent(context)
        return f"""
        **Role:**
        * あなたは真面目で有能なサポーターです。ユーザーからの質問に対して、必要に応じて専門エージェントに問い合わせて回答を提供します。

        **Response Strategy:**
        * **一般的な会話（挨拶、雑談など）**: 自分で直接回答してください。エージェントを呼び出す必要はありません。
          - 例: 「こんにちは」「ありがとう」「元気ですか」「どんなことができますか」など
        * **専門的な質問**: 以下の場合のみ、専門エージェントに問い合わせてください。
          - **沖縄方言への変換が必要な場合**: 'uchina_guchi_agent'を使用
          - **沖縄の観光情報・見どころ・アクセス・営業時間などの最新情報が必要な場合**: 'midokoro_agent'を使用（Google検索で最新情報を取得）

        **Task:**
        * ユーザーの質問を分析し、専門エージェントが必要かどうかを判断してください。
        * 専門的な知識や処理が必要な場合のみ、適切なエージェントに問い合わせてください。
        * 利用可能な機能について聞かれた場合は、両エージェントの機能を説明してください。

        **Multi-Agent Capabilities:**
        * **並列問い合わせ:** 複数のエージェントに同時に問い合わせたい場合は `send_messages_parallel` を使用してください。
        * **エージェントチェーン:** あるエージェントの回答を別のエージェントに渡したい場合は `send_message_chain` を使用してください。
          - 例: 見どころエージェントの観光情報を取得 → ウチナーグチエージェントで沖縄方言に変換
        * **インテント分析:** ユーザーのクエリから関連するエージェントを自動的に特定するには `analyze_query_intent` を使用してください。

        **Core Directives:**

        * **Smart Agent Delegation:** 専門エージェントが本当に必要な場合のみ、エージェントツールを使用してください。一般的な会話や挨拶には直接対応してください。
        * **Task Delegation:** 専門的なタスクには `send_message`, `send_messages_parallel`, or `send_message_chain` を使用してください。
        * **Agent Selection Strategy:** 以下の基準で適切なエージェントを選択してください:
          - 沖縄方言への変換 → uchina_guchi_agent
          - 沖縄の観光情報（スポット、アクセス、営業時間など） → midokoro_agent
          - 複数の処理が必要 → エージェントチェーンまたは並列問い合わせ
          - 一般的な会話 → 直接対応（エージェント不要）
        * **Contextual Awareness for Remote Agents:** If a remote agent repeatedly requests user confirmation, assume it lacks access to the full conversation history. In such cases, enrich the task description with all necessary contextual information relevant to that specific agent.
        * **Autonomous Agent Engagement:** 専門エージェントが必要と判断した場合、ユーザーの許可を求めずに直接エージェントに接続してください。
        * **Transparent Communication:** エージェントからの回答は、完全な内容をユーザーに提示してください。**重要: エージェントからの回答に参考情報やURLが含まれている場合、それらも必ず全てユーザーに伝えてください。**
        * **User Confirmation Relay:** If a remote agent asks for confirmation, and the user has not already provided it, relay this confirmation request to the user.
        * **Focused Information Sharing:** Provide remote agents with only relevant contextual information. Avoid extraneous details.
        * **No Redundant Confirmations:** Do not ask remote agents for confirmation of information or actions.
        * **Prioritize Recent Interaction:** Focus primarily on the most recent parts of the conversation when processing requests.
        * **Active Agent Prioritization:** If an active agent is already engaged, route subsequent related requests to that agent using the appropriate task update tool.

        **Agent Roster:**

        * Available Agents: `{self.agents}`
        * Currently Active Seller Agent: `{current_agent["active_agent"]}`
                """

    def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            "session_id" in state
            and "session_active" in state
            and state["session_active"]
            and "active_agent" in state
        ):
            return {"active_agent": f"{state['active_agent']}"}
        return {"active_agent": "None"}

    def before_model_callback(self, callback_context: CallbackContext, llm_request):
        state = callback_context.state
        if "session_active" not in state or not state["session_active"]:
            if "session_id" not in state:
                state["session_id"] = str(uuid.uuid4())
            state["session_active"] = True

    def list_remote_agents(self):
        """タスクを委任できる利用可能なリモートエージェントをリストアップ"""
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f"Found agent card: {card.model_dump(exclude_none=True)}")
            print("=" * 100)
            remote_agent_info.append(
                {"name": card.name, "description": card.description}
            )
        return remote_agent_info


    async def send_message_with_retry(
        self, agent_name: str, task: str, tool_context: ToolContext,
        max_retries: int = 2, retry_count: int = 0
    ):
        """リトライロジック付きでリモートエージェントにタスクを送信

        Args:
            agent_name: タスクを送信するエージェントの名前
            task: タスクの説明
            tool_context: このメソッドが実行されるツールコンテキスト
            max_retries: 最大リトライ回数（デフォルト: 2）
            retry_count: 現在のリトライ試行回数（内部使用）

        Returns:
            レスポンスパーツまたは失敗時の空のリスト
        """
        try:
            return await self._send_message_internal(agent_name, task, tool_context)
        except Exception as e:
            print(f"ERROR: Failed to send message to {agent_name}: {str(e)}")
            if retry_count < max_retries:
                print(f"Retrying... (attempt {retry_count + 1} of {max_retries})")
                await asyncio.sleep(1)  # 1秒待機してからリトライ
                return await self.send_message_with_retry(
                    agent_name, task, tool_context, max_retries, retry_count + 1
                )
            else:
                print(f"ERROR: All retry attempts failed for {agent_name}")
                return []

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """タスクをリモートエージェントに送信（自動リトライ機能付き）

        指定されたエージェント名のリモートエージェントにメッセージを送信します。

        Args:
            agent_name: タスクを送信するエージェントの名前
            task: ユーザーの問い合わせに関する包括的な会話コンテキストの要約と達成すべき目標
            tool_context: このメソッドが実行されるツールコンテキスト

        Yields:
            JSONデータの辞書
        """
        return await self.send_message_with_retry(agent_name, task, tool_context)

    async def _send_message_internal(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """メッセージ送信の内部メソッド（リトライラッパーから呼び出される）"""
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f"Agent {agent_name} not found")
        state = tool_context.state
        state["active_agent"] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f"Client not available for {agent_name}")
        if "task_id" in state:
            taskId = state["task_id"]

        else:
            taskId = str(uuid.uuid4())
        task_id = taskId
        sessionId = state["session_id"]
        if "context_id" in state:
            context_id = state["context_id"]
        else:
            context_id = str(uuid.uuid4())

        messageId = ""
        metadata = {}
        if "input_message_metadata" in state:
            metadata.update(**state["input_message_metadata"])
            if "message_id" in state["input_message_metadata"]:
                messageId = state["input_message_metadata"]["message_id"]
        if not messageId:
            messageId = str(uuid.uuid4())

        payload = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": task}],
                "messageId": messageId,
            },
        }

        if task_id:
            payload["message"]["taskId"] = task_id

        if context_id:
            payload["message"]["contextId"] = context_id

        message_request = SendMessageRequest(
            id=messageId, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message( message_request= message_request)
        print("send_response", send_response)

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print("received non-success response. Aborting get task ")
            raise Exception(f"Non-success response from {agent_name}")

        if not isinstance(send_response.root.result, Task):
            print("received non-task response. Aborting get task ")
            raise Exception(f"Non-task response from {agent_name}")

        response = send_response
        if hasattr(response, "root"):
            content = response.root.model_dump_json(exclude_none=True)
        else:
            content = response.model_dump(mode="json", exclude_none=True)

        resp = []
        json_content = json.loads(content)
        print(f"[DEBUG] Full response from {agent_name}:")
        print(json.dumps(json_content, indent=2, ensure_ascii=False))

        if json_content.get("result"):
            result = json_content["result"]

            # 標準形式: {"result": {"artifacts": [{"parts": [...]}]}}
            if isinstance(result, dict) and result.get("artifacts"):
                for artifact in result["artifacts"]:
                    if artifact.get("parts"):
                        print(f"[DEBUG] Found {len(artifact['parts'])} parts in artifact")
                        resp.extend(artifact["parts"])
            elif isinstance(result, list):
                # リストの各要素をそのまま追加
                resp.extend(result)

        print(f"[DEBUG] Returning {len(resp)} parts to coordinator")
        return resp

    async def send_messages_parallel(
        self,
        agent_tasks: List[Dict[str, str]],
        tool_context: ToolContext
    ) -> Dict[str, Any]:
        """複数のエージェントに並列で問い合わせる

        Args:
            agent_tasks: エージェント名とタスクのリスト
                例: [{"agent_name": "midokoro_agent", "task": "沖縄の人気観光スポットを教えて"}, ...]
            tool_context: ツールコンテキスト

        Returns:
            各エージェントからの回答の辞書
        """
        tasks = []
        agent_names = []

        for agent_task in agent_tasks:
            agent_name = agent_task["agent_name"]
            task = agent_task["task"]

            if agent_name not in self.remote_agent_connections:
                print(f"Warning: Agent {agent_name} not found, skipping")
                continue

            agent_names.append(agent_name)
            tasks.append(self.send_message(agent_name, task, tool_context))

        # 並列実行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果を辞書形式で返す
        response_dict = {}
        for agent_name, result in zip(agent_names, results):
            if isinstance(result, Exception):
                print(f"ERROR: Exception from {agent_name}: {str(result)}")
                response_dict[agent_name] = []  # エラー時は空のリストを返す
            elif not result:
                print(f"WARNING: Empty response from {agent_name}")
                response_dict[agent_name] = []
            else:
                response_dict[agent_name] = result

        return response_dict

    async def send_message_chain(
        self,
        chain: List[Dict[str, Any]],
        tool_context: ToolContext
    ) -> Dict[str, Any]:
        """エージェントのチェーンを実行（複数の結果を蓄積しながら進む）

        Args:
            chain: 実行するチェーンの定義
                例: [
                    {"agent_name": "midokoro_agent", "task": "首里城について教えて"},
                    {"agent_name": "uchina_guchi_agent", "task_template": "{result}を沖縄方言に変換してください", "use_agent_result": "midokoro_agent"}
                ]
            tool_context: ツールコンテキスト

        Returns:
            各エージェントからの回答を含む辞書
        """
        results = {}
        accumulated_context = ""

        for step in chain:
            agent_name = step["agent_name"]

            if agent_name not in self.remote_agent_connections:
                print(f"Warning: Agent {agent_name} not found, skipping")
                continue

            # タスクの構築
            if "task_template" in step:
                # 特定のエージェントの結果を参照
                if "use_agent_result" in step:
                    previous_agent = step["use_agent_result"]
                    if previous_agent in results:
                        # 結果を文字列に変換
                        result_text = self._format_agent_result(results[previous_agent])
                        task = step["task_template"].format(result=result_text)
                    else:
                        task = step.get("fallback_task", "前のエージェントの結果が見つかりません")
                # 全ての蓄積された結果を使用
                elif step.get("use_all_results", False):
                    task = step["task_template"].format(all_results=accumulated_context)
                else:
                    task = step.get("task", "")
            else:
                task = step.get("task", "")

            # エージェントに問い合わせ
            try:
                result = await self.send_message(agent_name, task, tool_context)
                results[agent_name] = result

                # 結果を蓄積
                result_text = self._format_agent_result(result)
                accumulated_context += f"\n\n【{agent_name}の回答】:\n{result_text}"
            except Exception as e:
                print(f"Error calling {agent_name}: {e}")
                results[agent_name] = {"error": str(e)}

        return results

    def _format_agent_result(self, result: Any) -> str:
        """エージェントの結果を文字列に変換（参考情報も含む）"""
        if isinstance(result, list):
            # Partオブジェクトのリストの場合
            texts = []
            for part in result:
                if isinstance(part, dict):
                    # textフィールドがある場合
                    if "text" in part:
                        texts.append(part["text"])
                    # 他の情報（kind, type等）もログに記録
                    if "kind" in part and part["kind"] != "text":
                        print(f"Additional part info: {part}")
                elif hasattr(part, "text"):
                    texts.append(part.text)
            return "\n".join(texts)
        elif isinstance(result, dict):
            if "text" in result:
                return result["text"]
            elif "error" in result:
                return f"エラー: {result['error']}"
            else:
                return json.dumps(result, ensure_ascii=False)
        else:
            return str(result)

    def analyze_query_intent(self, query: str) -> List[str]:
        """クエリを分析して関連するエージェントを特定

        Args:
            query: ユーザーのクエリ

        Returns:
            推奨されるエージェント名のリスト
        """
        required_agents = []

        # キーワードベースの分析
        keyword_agent_map = {
            # 沖縄方言関連
            r"方言|うちなーぐち|沖縄.*?言|訳して|ウチナー": ["uchina_guchi_agent"],
            # 観光・見どころ関連
            r"観光|見どころ|スポット|ビーチ|グルメ|アクセス|営業|料金|おすすめ|人気|首里城|美ら海|国際通り": ["midokoro_agent"],
        }

        query_lower = query.lower()
        for pattern, agents in keyword_agent_map.items():
            if re.search(pattern, query_lower):
                required_agents.extend(agents)

        # 重複を削除して返す
        return list(set(required_agents))


# For backward compatibility, if someone imports coordinator_agent directly
def get_coordinator_agent():
    """
    コーディネーターエージェントのインスタンスを作成します。
    注意: これは後方互換性のための同期関数です。
    非同期環境では、CoordinatorAgent.create()を直接使用してください。
    """
    async def _async_main():
        coordinator_agent_instance = await CoordinatorAgent.create(
            remote_agent_addresses=[
                UCHINA_GUCHI_AGENT_URL,
                MIDOKORO_AGENT_URL,
            ]
        )
        return coordinator_agent_instance.create_agent()
    try:
        return asyncio.run(_async_main())
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            print(f"Warning: Could not initialize CoordinatorAgent with asyncio.run(): {e}. "
                  "This can happen if an event loop is already running (e.g., in Jupyter). "
                  "Consider initializing CoordinatorAgent within an async function in your application.")
        raise

# Backward compatibility alias
get_root_agent = get_coordinator_agent
RootAgent = CoordinatorAgent
