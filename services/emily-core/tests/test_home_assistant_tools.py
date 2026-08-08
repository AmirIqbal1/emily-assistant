import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.entities import EntityRegistry, EntityResolver
from app.home_assistant import HomeAssistantClient, HomeAssistantError
from app.main import create_app
from app.tools import ToolExecutor


STATES = [
    {"entity_id": "light.kitchen_light", "state": "on", "attributes": {"friendly_name": "Kitchen Light", "brightness": 127}},
    {"entity_id": "light.kitchen_lamp", "state": "off", "attributes": {"friendly_name": "Kitchen Lamp"}},
    {"entity_id": "fan.bedroom_fan", "state": "on", "attributes": {"friendly_name": "Bedroom Fan"}},
    {"entity_id": "switch.office_switch", "state": "off", "attributes": {"friendly_name": "Office Switch"}},
    {"entity_id": "media_player.living_room_tv", "state": "paused", "attributes": {"friendly_name": "Living Room TV", "volume_level": 0.4}},
    {"entity_id": "sensor.temperature_sensor", "state": "21.4", "attributes": {"friendly_name": "Temperature Sensor", "unit_of_measurement": "°C", "secret": "not-exposed"}},
    {"entity_id": "lock.front_door", "state": "locked", "attributes": {"friendly_name": "Front Door Lock"}},
]


def make_transport(calls: list[httpx.Request], failure: int | None = None) -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if failure and request.method == "POST":
            return httpx.Response(failure)
        if request.url.path == "/api/":
            return httpx.Response(200, json={"message": "API running."})
        if request.url.path == "/api/states":
            return httpx.Response(200, json=STATES)
        if request.url.path.startswith("/api/states/"):
            entity_id = request.url.path.rsplit("/", 1)[-1]
            state = next((item for item in STATES if item["entity_id"] == entity_id), None)
            return httpx.Response(200, json=state) if state else httpx.Response(404)
        if request.url.path.startswith("/api/services/"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def make_chat_client(calls: list[httpx.Request], **settings: object) -> TestClient:
    app_settings = Settings(home_assistant_token="test-token", **settings)
    home_assistant = HomeAssistantClient(
        "http://homeassistant.test", "test-token", transport=make_transport(calls)
    )
    return TestClient(create_app(app_settings, home_assistant))


@pytest.mark.asyncio
async def test_successful_connection_and_discovery_are_safe() -> None:
    calls: list[httpx.Request] = []
    client = HomeAssistantClient("http://homeassistant.test", "test-token", make_transport(calls))
    assert (await client.check_connection()).connected is True
    entities = await EntityRegistry(client).discover()
    assert len(entities) == 7
    assert next(entity for entity in entities if entity.entity_id == "sensor.temperature_sensor").attributes == {
        "unit_of_measurement": "°C"
    }


@pytest.mark.asyncio
async def test_missing_token_and_malformed_response_are_safe() -> None:
    client = HomeAssistantClient("http://homeassistant.test")
    assert (await client.check_connection()).message == "Home Assistant token is not configured."
    with pytest.raises(HomeAssistantError, match="token is not configured"):
        await client.get_states()

    async def malformed(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not": "a state list"})
    malformed_client = HomeAssistantClient(
        "http://homeassistant.test", "test-token", httpx.MockTransport(malformed)
    )
    with pytest.raises(HomeAssistantError, match="malformed"):
        await malformed_client.get_states()


@pytest.mark.asyncio
async def test_entity_resolution_is_exact_normalized_and_ambiguous() -> None:
    calls: list[httpx.Request] = []
    client = HomeAssistantClient("http://homeassistant.test", "test-token", make_transport(calls))

    entities = await EntityRegistry(client).discover()
    resolver = EntityResolver()
    assert resolver.resolve("Kitchen Light", entities).entity.entity_id == "light.kitchen_light"
    assert resolver.resolve("kitchen_light", entities).entity.entity_id == "light.kitchen_light"
    assert resolver.resolve("the kitchen-light", entities).entity.entity_id == "light.kitchen_light"
    assert resolver.resolve("kitchen", entities, {"light"}).ambiguous


@pytest.mark.parametrize(
    ("message", "service", "expected"),
    [
        ("turn on the kitchen light", "light/turn_on", "Kitchen Light turned on."),
        ("switch the kitchen light on", "light/turn_on", "Kitchen Light turned on."),
        ("turn off the bedroom fan", "fan/turn_off", "Bedroom Fan turned off."),
        ("toggle the kitchen light", "light/toggle", "Kitchen Light toggled."),
        ("play the living room TV", "media_player/media_play", "Living Room TV playing."),
        ("pause the living room TV", "media_player/media_pause", "Living Room TV paused."),
    ],
)
def test_device_commands_use_allowlisted_services(message: str, service: str, expected: str) -> None:
    calls: list[httpx.Request] = []
    with make_chat_client(calls) as client:
        response = client.post("/api/chat", json={"message": message})
    assert response.json()["success"] is True
    assert response.json()["reply"] == expected
    assert any(request.url.path.endswith(service) for request in calls)


@pytest.mark.parametrize(
    ("message", "expected_value"),
    [
        ("set kitchen light brightness to 0", 0),
        ("set kitchen light to 50 percent", 128),
        ("dim kitchen light to 100 percent", 255),
        ("dim kitchen light to 200 percent", 255),
    ],
)
def test_brightness_is_clamped_and_converted(message: str, expected_value: int) -> None:
    calls: list[httpx.Request] = []
    with make_chat_client(calls) as client:
        response = client.post("/api/chat", json={"message": message})
    assert response.json()["success"] is True
    service_request = next(request for request in calls if request.url.path.endswith("light/turn_on"))
    assert f'"brightness":{expected_value}'.encode() in service_request.content


@pytest.mark.parametrize(
    ("message", "expected_value"),
    [
        ("set living room TV volume to 0", "0.0"),
        ("set living room TV volume to 50 percent", "0.5"),
        ("set living room TV volume to 100", "1.0"),
        ("set living room TV volume to 150", "1.0"),
    ],
)
def test_volume_is_clamped_and_converted(message: str, expected_value: str) -> None:
    calls: list[httpx.Request] = []
    with make_chat_client(calls) as client:
        response = client.post("/api/chat", json={"message": message})
    assert response.json()["success"] is True
    service_request = next(request for request in calls if request.url.path.endswith("media_player/volume_set"))
    assert expected_value.encode() in service_request.content


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("is the kitchen light on?", "Kitchen Light is on."),
        ("is the bedroom fan running?", "Bedroom Fan is running."),
        ("what is the temperature sensor reading?", "Temperature Sensor is 21.4°C."),
        ("what state is the office switch?", "Office Switch is off."),
        ("what is the front door lock?", "Front Door Lock is locked."),
    ],
)
def test_state_queries_are_friendly(message: str, expected: str) -> None:
    calls: list[httpx.Request] = []
    with make_chat_client(calls) as client:
        response = client.post("/api/chat", json={"message": message})
    assert response.json()["reply"] == expected


def test_entities_endpoints_support_filter_search_refresh_and_safe_detail() -> None:
    calls: list[httpx.Request] = []
    with make_chat_client(calls) as client:
        response = client.get("/api/entities?domain=light&search=kitchen")
        detail = client.get("/api/entities/sensor.temperature_sensor")
        refreshed = client.post("/api/entities/refresh")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert detail.json()["attributes"] == {"unit_of_measurement": "°C"}
    assert refreshed.json()["count"] == 7


def test_lock_is_not_controllable_and_control_can_be_disabled() -> None:
    calls: list[httpx.Request] = []
    with make_chat_client(calls) as client:
        lock_response = client.post("/api/chat", json={"message": "turn on front door lock"})
    assert lock_response.json()["success"] is False
    assert not any("/api/services/lock/" in request.url.path for request in calls)

    disabled_calls: list[httpx.Request] = []
    with make_chat_client(disabled_calls, home_assistant_control_enabled=False) as client:
        disabled_response = client.post("/api/chat", json={"message": "turn on kitchen light"})
    assert disabled_response.json()["reply"] == "Home Assistant device control is disabled."
    assert not any("/api/services/" in request.url.path for request in disabled_calls)


def test_home_assistant_failure_never_reports_success_or_token() -> None:
    token = "very-secret-token"
    calls: list[httpx.Request] = []
    client = HomeAssistantClient(
        "http://homeassistant.test", token, make_transport(calls, failure=500)
    )
    registry = EntityRegistry(client)
    executor = ToolExecutor(registry, EntityResolver(), True)

    async def run() -> None:
        result = await executor.execute("turn_on", "kitchen light")
        assert result.success is False
        assert token not in result.reply
    import asyncio
    asyncio.run(run())
