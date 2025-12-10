from typing import Any
from uuid import uuid4
import httpx
import traceback

from a2a.client import A2AClient
from a2a.types import (
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    SendMessageRequest,
    MessageSendParams,
)


AGENT_URL = "http://0.0.0.0:10001"


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'kind': 'text', 'text': text}],
            'messageId': uuid4().hex,
        },
    }
    if task_id:
        payload['message']['taskId'] = task_id
    if context_id:
        payload['message']['contextId'] = context_id

    return payload


def print_json_response(response: Any) -> None:
    if hasattr(response, "root"):
        print(f"{response.root.model_dump_json(exclude_none=True)}\n")
    else:
        print(f'{response.model_dump(mode="json", exclude_none=True)}\n')


async def run_single_turn_test(client: A2AClient) -> None:
    send_payload = create_send_message_payload(
        text='こんにちは、を沖縄方言に翻訳してください。'
    )
    request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(**send_payload))

    send_response: SendMessageResponse = await client.send_message(request)
    print_json_response(send_response)
    if not isinstance(send_response.root, SendMessageSuccessResponse):
        print('received non-success response. Aborting get task ')
        return
    if not isinstance(send_response.root.result, Task):
        print('received non-task response. Aborting get task ')
        return

    
async def main() -> None:
    print(f'Connecting to agent at {AGENT_URL}...')
    try:
        async with httpx.AsyncClient(timeout=30) as httpx_client:
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client, AGENT_URL
            )
            print('Connection successful.')
            await run_single_turn_test(client)

    except Exception as e:
        traceback.print_exc()
        print(f'An error occurred: {e}')
        print('Ensure the agent server is running.')

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())