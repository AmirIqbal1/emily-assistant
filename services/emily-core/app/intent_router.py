import re
from abc import ABC, abstractmethod

from app.models import IntentResult


class IntentDetector(ABC):
    """Extension point for deterministic or model-assisted intent detection."""

    @abstractmethod
    def detect(self, message: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def route(self, message: str) -> IntentResult:
        raise NotImplementedError


class LocalIntentRouter(IntentDetector):
    """Small deterministic parser. It extracts intent only; tools execute later."""

    def detect(self, message: str) -> str:
        return self.route(message).intent

    def route(self, message: str) -> IntentResult:
        normalized = self._normalize(message)

        # Device commands precede conversational v0.1 messages.
        volume = re.fullmatch(
            r"(?:set (?:the )?(.+?) volume to|volume (?:the )?(.+?) to) (-?\d+)(?: percent)?",
            normalized,
        )
        if volume:
            return IntentResult(
                intent="media.set_volume",
                target_name=volume.group(1) or volume.group(2),
                value=int(volume.group(3)),
            )

        brightness = re.fullmatch(
            r"(?:set|dim) (?:the )?(.+?)(?: brightness)? to (-?\d+)(?: percent)?", normalized
        )
        if brightness and (normalized.startswith("dim ") or " brightness " in normalized or " light" in brightness.group(1)):
            return IntentResult(
                intent="light.set_brightness", target_name=brightness.group(1), value=int(brightness.group(2))
            )

        match = re.fullmatch(r"(?:turn on|switch on|switch) (?:the )?(.+?)(?: on)?", normalized)
        if match:
            return IntentResult(intent="device.turn_on", target_name=match.group(1))
        match = re.fullmatch(r"turn (?:the )?(.+?) on", normalized)
        if match:
            return IntentResult(intent="device.turn_on", target_name=match.group(1))
        match = re.fullmatch(r"(?:turn off|switch off) (?:the )?(.+?)(?: off)?", normalized)
        if match:
            return IntentResult(intent="device.turn_off", target_name=match.group(1))
        match = re.fullmatch(r"turn (?:the )?(.+?) off", normalized)
        if match:
            return IntentResult(intent="device.turn_off", target_name=match.group(1))
        match = re.fullmatch(r"toggle (?:the )?(.+)", normalized)
        if match:
            return IntentResult(intent="device.toggle", target_name=match.group(1))
        match = re.fullmatch(r"(?:play|resume) (?:the )?(.+)", normalized)
        if match:
            return IntentResult(intent="media.play", target_name=match.group(1))
        match = re.fullmatch(r"pause (?:the )?(.+)", normalized)
        if match:
            return IntentResult(intent="media.pause", target_name=match.group(1))
        match = re.fullmatch(r"is (?:the )?(.+?)(?: on| off| running)?", normalized)
        if match:
            return IntentResult(intent="device.get_state", target_name=match.group(1))
        match = re.fullmatch(r"what state is (?:the )?(.+)", normalized)
        if match:
            return IntentResult(intent="device.get_state", target_name=match.group(1))
        match = re.fullmatch(r"what is (?:the )?(.+?)(?: set to| reading)?", normalized)
        if match and match.group(1) not in {"your name", "the time"}:
            return IntentResult(intent="device.get_state", target_name=match.group(1))
        match = re.fullmatch(r"(?:lock|unlock) (?:the )?(.+)", normalized)
        if match:
            return IntentResult(intent="device.lock_control_blocked", target_name=match.group(1))

        if normalized in {"hi", "hello", "hey", "hello emily", "hey emily", "hi emily"}:
            return IntentResult(intent="greeting")
        if normalized in {"what is your name", "whats your name"}:
            return IntentResult(intent="name")
        if normalized == "who are you":
            return IntentResult(intent="identity")
        if normalized in {"are you online", "are you there"}:
            return IntentResult(intent="online")
        if normalized in {"what time is it", "whats the time", "tell me the time"}:
            return IntentResult(intent="time")
        if normalized in {"what can you do", "help", "what are your capabilities"}:
            return IntentResult(intent="capabilities")
        if normalized in {
            "check home assistant", "is home assistant online", "home assistant status",
        }:
            return IntentResult(intent="home_assistant_status")
        return IntentResult(intent="unknown")

    @staticmethod
    def _normalize(message: str) -> str:
        normalized = re.sub(r"[^a-z0-9\s'-]", "", message.casefold()).strip()
        return re.sub(r"\s+", " ", normalized)
