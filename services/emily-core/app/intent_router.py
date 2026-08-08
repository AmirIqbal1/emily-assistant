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

        if normalized in {"what music players are available", "what speakers are available", "list music players", "list speakers"}:
            return IntentResult(intent="music.list_players")
        match = re.fullmatch(r"(?:what song is playing|whats playing|what is playing|what song is this)(?: (?:in|on) (?:the )?(.+?))?", normalized)
        if match:
            return IntentResult(intent="music.now_playing", target_name=match.group(1))
        match = re.fullmatch(r"is (?:the )?(.+?) (?:playing music|paused)", normalized)
        if match:
            return IntentResult(intent="music.get_state", target_name=match.group(1))
        match = re.fullmatch(r"(?:pause|stop|resume|continue)(?: (?:the )?(.+?))?", normalized)
        if match and "tv" not in (match.group(1) or ""):
            command = normalized.split()[0]
            intent = {"pause": "music.pause", "stop": "music.stop", "resume": "music.resume", "continue": "music.resume"}[command]
            target = match.group(1)
            if target:
                target = re.sub(r"\b(?:the )?music\b", "", target).strip() or None
                target = re.sub(r"^(?:in|on)\s+", "", target or "") or None
            return IntentResult(intent=intent, target_name=target)
        if normalized in {"next song", "next track", "skip song", "skip this song"}:
            return IntentResult(intent="music.next")
        if normalized in {"previous song", "previous track", "go back a song"}:
            return IntentResult(intent="music.previous")
        volume_music = re.fullmatch(r"(?:set (?:the )?(?:music|(.+? speaker|.+? music)) volume to|(?:music|(.+? speaker|.+? music)) volume) (-?\d+)(?: percent)?", normalized)
        if volume_music:
            target = volume_music.group(1) or volume_music.group(2)
            target = re.sub(r"\s+music$", "", target).strip() if target else None
            return IntentResult(intent="music.set_volume", target_name=target, value=int(volume_music.group(3)))
        match = re.fullmatch(r"play (?:my )?(?:the )?(?:(song|track|artist|album|playlist) )?(.+?)(?: (?:in|on) (?:the )?(.+))?", normalized)
        if match and "tv" not in normalized:
            media_type = {"song": "track", "track": "track", "artist": "artist", "album": "album", "playlist": "playlist"}.get(match.group(1))
            query = match.group(2)
            if not media_type and query.endswith(" playlist"):
                media_type, query = "playlist", query.removesuffix(" playlist")
            return IntentResult(intent="music.play", target_name=query, player_name=match.group(3), media_type=media_type)

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
