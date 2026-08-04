import re
from abc import ABC, abstractmethod


class IntentDetector(ABC):
    """Extension point for deterministic or model-assisted intent detection."""

    @abstractmethod
    def detect(self, message: str) -> str:
        raise NotImplementedError


class LocalIntentRouter(IntentDetector):
    """Small deterministic router used when no language model is configured."""

    def detect(self, message: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s']", "", message.lower()).strip()
        normalized = re.sub(r"\s+", " ", normalized)

        if normalized in {"hi", "hello", "hey", "hello emily", "hey emily", "hi emily"}:
            return "greeting"
        if normalized in {"what is your name", "what's your name", "whats your name"}:
            return "name"
        if normalized == "who are you":
            return "identity"
        if normalized in {"are you online", "are you there"}:
            return "online"
        if normalized in {"what time is it", "what's the time", "whats the time", "tell me the time"}:
            return "time"
        if normalized in {"what can you do", "help", "what are your capabilities"}:
            return "capabilities"
        if normalized in {
            "check home assistant",
            "is home assistant online",
            "home assistant status",
        }:
            return "home_assistant_status"
        return "unknown"

