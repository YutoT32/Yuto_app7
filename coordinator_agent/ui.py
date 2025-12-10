from pprint import pformat
from pydantic import BaseModel
from typing import AsyncIterator
from ulid import ULID
import asyncio
import streamlit as st
import traceback

from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.genai import types

from coordinator_agent import CoordinatorAgent
from config import UCHINA_GUCHI_AGENT_URL


class ChatMessage(BaseModel):
    role: str
    content: str

APP_NAME = "技育CAMPアカデミア - DEMO"
USER_ID = "default_user"


@st.cache_resource
def create_session_service():
    print("Session service created.")
    return InMemorySessionService()

_session_service = create_session_service()


def create_session_id():
    session_id = str(ULID())
    print(f"Session ID: {session_id}")
    return session_id


def set_session_id():
    st.session_state.session_id = create_session_id()    


@st.cache_resource
def get_memory_service():
    print("Memory service created.")
    return InMemoryMemoryService()

MEMORY_SERVICE = InMemoryMemoryService()


async def get_agent_runner():
    """各リクエストごとに新しいコーディネーターエージェントのインスタンスを作成してイベントループの問題を回避"""
    # イベントループの問題を避けるため、各リクエストごとに新しいコーディネーターエージェントのインスタンスを作成
    coordinator_agent_instance = await CoordinatorAgent.create(
        remote_agent_addresses=[
            UCHINA_GUCHI_AGENT_URL,
        ]
    )
    agent = coordinator_agent_instance.create_agent()
    
    return Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=_session_service,
        memory_service=MEMORY_SERVICE
    )

async def __get_response_from_agent(
    message: str
) -> AsyncIterator[ChatMessage]:
    try:
        # Create a new runner for each request to avoid event loop issues
        runner = await get_agent_runner()
        events_iterator: AsyncIterator[Event] = runner.run_async(
            user_id=USER_ID,
            session_id=st.session_state.session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        )

        async for event in events_iterator:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        formatted_call = f"```python\n{pformat(part.function_call.model_dump(exclude_none=True), indent=2, width=80)}\n```"
                        yield ChatMessage(
                            role="assistant",
                            content=f"🛠️ **Tool Call: {part.function_call.name}**\n{formatted_call}",
                        )
                    elif part.function_response:
                        # function_responseは結果が返ってきたことを示すので、特に表示しない
                        pass
            if event.is_final_response():
                final_response_text = ""
                if event.content and event.content.parts:
                    # 修正：すべての部分を適切に処理
                    text_parts = []
                    for part in event.content.parts:
                        if part.text:
                            text_parts.append(part.text)
                        elif hasattr(part, 'thought_signature') and part.thought_signature:
                            # thought_signatureがある場合の処理（必要に応じて）
                            text_parts.append(f"[思考プロセス: {part.thought_signature}]")
                    final_response_text = "".join(text_parts)
                    # final_response_text = "".join(
                    #     [p.text for p in event.content.parts if p.text]
                    # )
                elif event.actions and event.actions.escalate:
                    final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                if final_response_text:
                    yield ChatMessage(role="assistant", content=final_response_text)
                break
    except Exception as e:
        print(f"Error in get_response_from_agent (Type: {type(e)}): {e}")
        traceback.print_exc()
        yield ChatMessage(
            role="system",
            content="An error occurred while processing your request. Please check the server logs for details.",
        )
    finally:
        try:
            if 'events_iterator' in locals():
                if hasattr(events_iterator, "aclose"):
                    await events_iterator.aclose()
        except Exception as e:
            print(f"Error closing events_iterator: {e}")


def __title():
    st.title(APP_NAME)


async def __initialize():
    if "session_id" not in st.session_state:
        set_session_id()
        await _session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=st.session_state.session_id
        )
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def __prompt_input():
    return st.chat_input("Say something")


async def __chat_field():
    if prompt := __prompt_input():
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        async def __stream_response():
            async for response in __get_response_from_agent(prompt):
                with st.chat_message(response.role):
                    st.markdown(response.content)
                st.session_state.messages.append({"role": response.role, "content": response.content})

        await __stream_response()


async def __main():
    __title()
    await __initialize()
    await __chat_field()


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    async def run_app():
        try:
            await __main()
        finally:
            # クリーンアップ処理（必要に応じて）
            pass

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run_app())
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
