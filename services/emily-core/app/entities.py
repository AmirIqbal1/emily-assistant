import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.home_assistant import HomeAssistantClient, HomeAssistantError
from app.models import HomeAssistantEntity

SUPPORTED_DOMAINS = frozenset(
    {"light", "switch", "fan", "media_player", "climate", "cover", "lock", "sensor", "binary_sensor"}
)
SAFE_ATTRIBUTE_KEYS = frozenset(
    {
        "brightness",
        "color_temp",
        "current_temperature",
        "device_class",
        "humidity",
        "temperature",
        "temperature_unit",
        "unit_of_measurement",
        "volume_level",
    }
)


class EntityRegistry:
    """Caches supported Home Assistant states and strips unsafe attributes."""

    def __init__(self, client: HomeAssistantClient, cache_seconds: int = 30) -> None:
        self.client = client
        self.cache_seconds = cache_seconds
        self._entities: list[HomeAssistantEntity] = []
        self._cached_at = 0.0

    async def discover(self, refresh: bool = False) -> list[HomeAssistantEntity]:
        if not refresh and self._entities and time.monotonic() - self._cached_at < self.cache_seconds:
            return self._entities

        states = await self.client.get_states()
        entities: list[HomeAssistantEntity] = []
        for raw_state in states:
            entity = self._to_entity(raw_state)
            if entity:
                entities.append(entity)
        self._entities = sorted(entities, key=lambda entity: entity.friendly_name.casefold())
        self._cached_at = time.monotonic()
        return self._entities

    async def find_by_id(self, entity_id: str) -> HomeAssistantEntity:
        if not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity_id):
            raise HomeAssistantError("Invalid Home Assistant entity ID.")
        entity = self._to_entity(await self.client.get_state(entity_id))
        if not entity:
            raise HomeAssistantError("That Home Assistant entity is not supported.")
        return entity

    @staticmethod
    def counts(entities: list[HomeAssistantEntity]) -> dict[str, int]:
        return dict(sorted(Counter(entity.domain for entity in entities).items()))

    @staticmethod
    def _to_entity(raw_state: dict[str, Any]) -> HomeAssistantEntity | None:
        entity_id = raw_state.get("entity_id")
        state = raw_state.get("state")
        attributes = raw_state.get("attributes", {})
        if not isinstance(entity_id, str) or "." not in entity_id or not isinstance(state, str):
            return None
        domain = entity_id.split(".", maxsplit=1)[0]
        if domain not in SUPPORTED_DOMAINS or not isinstance(attributes, dict):
            return None
        friendly_name = attributes.get("friendly_name")
        if not isinstance(friendly_name, str) or not friendly_name.strip():
            friendly_name = entity_id.split(".", maxsplit=1)[1].replace("_", " ").title()
        safe_attributes = {
            key: value
            for key, value in attributes.items()
            if key in SAFE_ATTRIBUTE_KEYS and isinstance(value, (str, int, float, bool, type(None)))
        }
        area = attributes.get("area_name")
        device_class = attributes.get("device_class")
        return HomeAssistantEntity(
            entity_id=entity_id,
            domain=domain,
            friendly_name=friendly_name.strip(),
            state=state,
            attributes=safe_attributes,
            area=area if isinstance(area, str) else None,
            device_class=device_class if isinstance(device_class, str) else None,
        )


@dataclass(frozen=True)
class Resolution:
    entity: HomeAssistantEntity | None = None
    matches: tuple[HomeAssistantEntity, ...] = ()

    @property
    def found(self) -> bool:
        return self.entity is not None

    @property
    def ambiguous(self) -> bool:
        return bool(self.matches) and self.entity is None


class EntityResolver:
    """Deterministic, conservative name resolver for conversational tools."""

    def resolve(
        self,
        target_name: str,
        entities: list[HomeAssistantEntity],
        domains: set[str] | frozenset[str] | None = None,
    ) -> Resolution:
        target = self.normalize(target_name)
        candidates = [entity for entity in entities if domains is None or entity.domain in domains]
        if not target:
            return Resolution()

        # The first matching tier wins; ties are intentionally reported as ambiguous.
        tiers = (
            lambda entity: self.normalize(entity.friendly_name) == target,
            lambda entity: self.normalize(entity.entity_id.split(".", 1)[1]) == target,
            lambda entity: self._strong_partial(target, self.normalize(entity.friendly_name)),
        )
        for matches_predicate in tiers:
            matches = [entity for entity in candidates if matches_predicate(entity)]
            if len(matches) == 1:
                return Resolution(entity=matches[0])
            if len(matches) > 1:
                return Resolution(matches=tuple(matches))
        return Resolution()

    @staticmethod
    def normalize(value: str) -> str:
        value = value.casefold().replace("_", " ").replace("-", " ")
        words = re.findall(r"[a-z0-9]+", value)
        return " ".join(word for word in words if word not in {"the", "a", "an"})

    @staticmethod
    def _strong_partial(target: str, candidate: str) -> bool:
        target_words = set(target.split())
        candidate_words = set(candidate.split())
        return bool(target_words) and (target_words <= candidate_words or candidate_words <= target_words)
