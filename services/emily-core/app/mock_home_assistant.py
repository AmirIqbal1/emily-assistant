from copy import deepcopy
from typing import Any

from app.home_assistant import HomeAssistantBackend, HomeAssistantError
from app.models import HomeAssistantStatus


MOCK_STATES: tuple[dict[str, Any], ...] = (
    {"entity_id": "light.kitchen_ceiling", "state": "off", "attributes": {"friendly_name": "Kitchen Ceiling"}},
    {"entity_id": "light.bedroom_lamp", "state": "on", "attributes": {"friendly_name": "Bedroom Lamp", "brightness": 153}},
    {"entity_id": "switch.office_fan", "state": "off", "attributes": {"friendly_name": "Office Fan"}},
    {"entity_id": "media_player.living_room", "state": "idle", "attributes": {"friendly_name": "Living Room TV", "volume_level": 0.3}},
    {"entity_id": "sensor.office_temperature", "state": "21.4", "attributes": {"friendly_name": "Office Temperature", "unit_of_measurement": "°C"}},
    {"entity_id": "lock.front_door", "state": "locked", "attributes": {"friendly_name": "Front Door"}},
)


class MockHomeAssistantBackend(HomeAssistantBackend):
    """In-memory development backend; it never makes HTTP requests or needs a token."""

    is_mock = True

    def __init__(self) -> None:
        self._states = {state["entity_id"]: deepcopy(state) for state in MOCK_STATES}

    @property
    def token_configured(self) -> bool:
        return False

    @property
    def entity_count(self) -> int:
        return len(self._states)

    async def check_connection(self) -> HomeAssistantStatus:
        return HomeAssistantStatus(
            connected=True,
            configured=True,
            status_code=200,
            message="Home Assistant mock mode is active.",
            mode="mock",
        )

    async def get_states(self) -> list[dict[str, Any]]:
        return deepcopy(list(self._states.values()))

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        state = self._states.get(entity_id)
        if state is None:
            raise HomeAssistantError("Home Assistant could not find that entity.", 404)
        return deepcopy(state)

    async def call_service(
        self, domain: str, service: str, service_data: dict[str, Any]
    ) -> None:
        entity_id = service_data.get("entity_id")
        if not isinstance(entity_id, str):
            raise HomeAssistantError("Home Assistant could not complete that request.")
        state = self._states.get(entity_id)
        if state is None or state["entity_id"].split(".", 1)[0] != domain:
            raise HomeAssistantError("Home Assistant could not find that entity.", 404)

        if service == "turn_on":
            state["state"] = "on"
            if "brightness" in service_data:
                state["attributes"]["brightness"] = service_data["brightness"]
        elif service == "turn_off":
            state["state"] = "off"
        elif service == "toggle":
            state["state"] = "off" if state["state"] == "on" else "on"
        elif service == "media_play":
            state["state"] = "playing"
        elif service == "media_pause":
            state["state"] = "paused"
        elif service == "volume_set" and "volume_level" in service_data:
            state["attributes"]["volume_level"] = service_data["volume_level"]
        else:
            raise HomeAssistantError("Home Assistant could not complete that request.")
