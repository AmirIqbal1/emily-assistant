import httpx
import pytest

from app.home_assistant import HomeAssistantClient
from app.intent_router import LocalIntentRouter


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("Hello", "greeting"),
        ("What time is it?", "time"),
        ("launch the moon", "unknown"),
    ],
)
def test_local_intents(message: str, intent: str) -> None:
    assert LocalIntentRouter().detect(message) == intent


@pytest.mark.asyncio
async def test_home_assistant_unavailable() -> None:
    async def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = HomeAssistantClient(
        "http://homeassistant.invalid:8123",
        "secret-token",
        transport=httpx.MockTransport(unavailable),
    )
    status = await client.check_connection()

    assert status.connected is False
    assert status.configured is True
    assert status.message == "Home Assistant could not be reached."


@pytest.mark.asyncio
async def test_home_assistant_token_is_not_exposed() -> None:
    token = "super-secret-token"

    async def rejected(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"rejected {token}")

    client = HomeAssistantClient(
        "http://homeassistant.invalid:8123",
        token,
        transport=httpx.MockTransport(rejected),
    )
    status = await client.check_connection()

    assert token not in status.message
    assert status.status_code == 401

