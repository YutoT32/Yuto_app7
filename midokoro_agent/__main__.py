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

from midokoro_agent import create_agent
from adk_agent_executor import ADKAgentExecutor


from dotenv import load_dotenv
load_dotenv()

from logging import getLogger
logger = getLogger(__name__)


@click.command()
@click.option("--host", "host", default="0.0.0.0")
@click.option("--port", "port", default=10002)
def main(host: str, port: int):
    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE" and not os.getenv(
        "GOOGLE_API_KEY"
    ):
        raise ValueError(
            "GOOGLE_API_KEY environment variable not set and "
            "GOOGLE_GENAI_USE_VERTEXAI is not TRUE."
        )
    
    skill = AgentSkill(
        id="okinawa_midokoro",
        name="Okinawa-Midokoro",
        description="Google検索を利用して沖縄の見どころや観光スポットを紹介します。",
        tags=["sample", "沖縄", "観光", "見どころ", "travel"],
        examples=["沖縄の人気観光スポットを教えて", "首里城について知りたい", "沖縄のおすすめビーチはどこ?"],
    )

    agent_card = AgentCard(
        name="midokoro_agent",
        description="Google検索を利用して沖縄の見どころや観光スポットを紹介するエージェントです。",
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