from abc import ABC, abstractmethod
from typing import ClassVar

from app.entities import EntityRegistry, EntityResolver
from app.home_assistant import HomeAssistantBackend, HomeAssistantError
from app.models import HomeAssistantEntity, ToolResult


class EmilyTool(ABC):
    """Fixed-purpose tool contract; chat never supplies an arbitrary HA service."""

    name: ClassVar[str]
    description: ClassVar[str]
    domains: ClassVar[frozenset[str]] = frozenset()
    changes_device: ClassVar[bool] = True

    @abstractmethod
    def can_handle(self, entity: HomeAssistantEntity) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        raise NotImplementedError


class HomeAssistantTool(EmilyTool):
    def __init__(self, backend: HomeAssistantBackend) -> None:
        self.backend = backend

    def can_handle(self, entity: HomeAssistantEntity) -> bool:
        return entity.domain in self.domains

    async def _service(
        self, entity: HomeAssistantEntity, service: str, data: dict[str, int | float] | None = None
    ) -> ToolResult:
        payload: dict[str, str | int | float] = {"entity_id": entity.entity_id}
        if data:
            payload.update(data)
        await self.backend.call_service(entity.domain, service, payload)
        return ToolResult(reply="", success=True, tool=self.name, target=entity.entity_id)


class TurnOnTool(HomeAssistantTool):
    name = "turn_on"
    description = "Turn on supported lights, switches, fans, and media players."
    domains = frozenset({"light", "switch", "fan"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        result = await self._service(entity, "turn_on")
        return result.model_copy(update={"reply": f"{entity.friendly_name} turned on."})


class TurnOffTool(HomeAssistantTool):
    name = "turn_off"
    description = "Turn off supported lights, switches, fans, and media players."
    domains = frozenset({"light", "switch", "fan"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        result = await self._service(entity, "turn_off")
        return result.model_copy(update={"reply": f"{entity.friendly_name} turned off."})


class ToggleTool(HomeAssistantTool):
    name = "toggle"
    description = "Toggle supported lights, switches, fans, and media players."
    domains = frozenset({"light", "switch", "fan"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        result = await self._service(entity, "toggle")
        return result.model_copy(update={"reply": f"{entity.friendly_name} toggled."})


class SetBrightnessTool(HomeAssistantTool):
    name = "set_brightness"
    description = "Set a light brightness as a percentage."
    domains = frozenset({"light"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        percent = max(0, min(100, value if value is not None else 0))
        brightness = round(percent * 255 / 100)
        result = await self._service(entity, "turn_on", {"brightness": brightness})
        return result.model_copy(
            update={"reply": f"{entity.friendly_name} brightness set to {percent}%."}
        )


class SetVolumeTool(HomeAssistantTool):
    name = "set_volume"
    description = "Set a media player volume as a percentage."
    domains = frozenset({"media_player"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        percent = max(0, min(100, value if value is not None else 0))
        result = await self._service(entity, "volume_set", {"volume_level": percent / 100})
        return result.model_copy(update={"reply": f"{entity.friendly_name} volume set to {percent}%."})


class MediaPlayTool(HomeAssistantTool):
    name = "media_play"
    description = "Resume playback on a media player."
    domains = frozenset({"media_player"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        result = await self._service(entity, "media_play")
        return result.model_copy(update={"reply": f"{entity.friendly_name} playing."})


class MediaPauseTool(HomeAssistantTool):
    name = "media_pause"
    description = "Pause a media player."
    domains = frozenset({"media_player"})

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        result = await self._service(entity, "media_pause")
        return result.model_copy(update={"reply": f"{entity.friendly_name} paused."})


class GetStateTool(HomeAssistantTool):
    name = "get_state"
    description = "Read the state of a discovered supported entity."
    domains = frozenset({
        "light", "switch", "fan", "media_player", "climate", "cover", "lock", "sensor", "binary_sensor"
    })
    changes_device = False

    async def execute(self, entity: HomeAssistantEntity, value: int | None = None) -> ToolResult:
        return ToolResult(
            reply=self._describe(entity), success=True, tool=self.name, target=entity.entity_id
        )

    @staticmethod
    def _describe(entity: HomeAssistantEntity) -> str:
        unit = entity.attributes.get("unit_of_measurement")
        if entity.domain == "climate" and entity.attributes.get("temperature") is not None:
            temperature_unit = entity.attributes.get("temperature_unit") or "°C"
            return f"{entity.friendly_name} is set to {entity.attributes['temperature']}{temperature_unit}."
        if entity.domain in {"sensor", "binary_sensor"} and unit and entity.state not in {"unknown", "unavailable"}:
            return f"{entity.friendly_name} is {entity.state}{unit}."
        if entity.domain == "fan" and entity.state == "on":
            return f"{entity.friendly_name} is running."
        return f"{entity.friendly_name} is {entity.state}."


class ToolExecutor:
    """Resolves a target and executes only a named, fixed-purpose tool."""

    def __init__(
        self, registry: EntityRegistry, resolver: EntityResolver, control_enabled: bool
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.control_enabled = control_enabled
        client = registry.backend
        tool_classes = (
            TurnOnTool, TurnOffTool, ToggleTool, SetBrightnessTool, SetVolumeTool,
            MediaPlayTool, MediaPauseTool, GetStateTool,
        )
        self.tools = {tool.name: tool for tool in (tool_class(client) for tool_class in tool_classes)}

    async def execute(self, tool_name: str, target_name: str | None, value: int | None = None) -> ToolResult:
        tool = self.tools.get(tool_name)
        if not tool or not target_name:
            return ToolResult(reply="I need a device name for that command.", success=False, tool=tool_name)
        if tool.changes_device and not self.control_enabled:
            return ToolResult(
                reply="Home Assistant control is disabled. I can still check device states.", success=False, tool=tool.name
            )
        try:
            resolution = self.resolver.resolve(
                target_name, await self.registry.discover(), tool.domains
            )
        except HomeAssistantError as error:
            return ToolResult(reply=error.message, success=False, tool=tool.name)
        if resolution.ambiguous:
            names = " and ".join(entity.friendly_name for entity in resolution.matches[:3])
            return ToolResult(
                reply=f"I found more than one matching device: {names}. Which one did you mean?",
                success=False,
                tool=tool.name,
            )
        if not resolution.found:
            return ToolResult(
                reply=f"I couldn't find a supported device named {target_name}.",
                success=False,
                tool=tool.name,
            )
        try:
            result = await tool.execute(resolution.entity, value)
            if result.success and tool.changes_device:
                self.registry.invalidate()
            return result
        except HomeAssistantError as error:
            return ToolResult(
                reply=error.message, success=False, tool=tool.name, target=resolution.entity.entity_id
            )


# Locks are deliberately discoverable and queryable only.  High-risk actions
# (locks, garages, alarms, scripts and shell commands) require a future
# confirmation/authorization framework and have no tool in Emily Core v0.2.
