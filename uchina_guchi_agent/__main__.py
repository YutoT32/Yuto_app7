import click
import os

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import uvicorn

from uchina_guchi_agent import create_agent
from adk_agent_executor import ADKAgentExecutor


from dotenv import load_dotenv
load_dotenv()

from logging import getLogger
logger = getLogger(__name__)


@click.command()
@click.option("--host", "host", default="0.0.0.0")
@click.option("--port", "port", default=10001)
def main(host: str, port: int):
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE" and not os.getenv(
        "GOOGLE_API_KEY"
    ):
        raise ValueError(
            "GOOGLE_API_KEY environment variable not set and "
            "GOOGLE_GENAI_USE_VERTEXAI is not TRUE."
        )
    
    skill = AgentSkill(
        id="uchina_guchi",
        name="Uchina-guchi",
        description="ユーザーから受け取った日本語を沖縄方言に変換します。",
        tags=["sample", "沖縄方言", "方言", "ウチナーグチ",],
        examples=["こんにちは、は、沖縄方言でなんていうの？"],
    )

    agent_card = AgentCard(
        name="uchina_guchi_agent",
        description="ユーザーから受け取った日本語を沖縄方言に変換するエージェントです。",
        url=f"http://{host}:{port}/",
        version="0.0.1",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    agent = create_agent()

    runner = Runner(
        app_name=agent_card.name,
        agent=agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
    )

    # リクエストを受けてエージェント固有のロジックを実行するインターフェース
    # プロトコルとロジックの橋渡しや、タスク管理を実施する
    agent_executor = ADKAgentExecutor(runner, agent_card)

    # リクエストハンドラ
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor, task_store=InMemoryTaskStore()
    )

    # A2Aサーバー
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )

    # サーバーの実行
    uvicorn.run(a2a_app.build(), host=host, port=port)


if __name__ == "__main__":
    main()