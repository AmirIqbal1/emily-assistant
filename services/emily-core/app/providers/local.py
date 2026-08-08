from datetime import datetime

from app.home_assistant import HomeAssistantClient
from app.intent_router import IntentDetector
from app.models import ChatResponse, ProviderContext
from app.providers.base import AssistantProvider
from app.tools import ToolExecutor


class LocalProvider(AssistantProvider):
    def __init__(
        self,
        assistant_name: str,
        router: IntentDetector,
        home_assistant: HomeAssistantClient,
        tools: ToolExecutor,
    ) -> None:
        self.assistant_name = assistant_name
        self.router = router
        self.home_assistant = home_assistant
        self.tools = tools

    @property
    def name(self) -> str:
        return "local"

    async def is_available(self) -> bool:
        return True

    async def process(self, message: str, context: ProviderContext) -> ChatResponse:
        del context
        route = self.router.route(message)
        intent = route.intent

        tool_for_intent = {
            "device.turn_on": "turn_on",
            "device.turn_off": "turn_off",
            "device.toggle": "toggle",
            "device.get_state": "get_state",
            "light.set_brightness": "set_brightness",
            "media.play": "media_play",
            "media.pause": "media_pause",
            "media.set_volume": "set_volume",
        }.get(intent)
        if tool_for_intent:
            result = await self.tools.execute(tool_for_intent, route.target_name, route.value)
            return ChatResponse(
                reply=result.reply,
                intent=intent,
                provider=self.name,
                success=result.success,
                tool=result.tool,
                target=result.target,
            )

        if intent == "greeting":
            reply = f"Hello. I’m {self.assistant_name}."
        elif intent == "name":
            reply = f"My name is {self.assistant_name}."
        elif intent == "identity":
            reply = f"I’m {self.assistant_name}, an open-source assistant running on your own server."
        elif intent == "online":
            reply = f"Yes. {self.assistant_name} Core is online."
        elif intent == "time":
            reply = f"The current server time is {datetime.now().astimezone():%H:%M}."
        elif intent == "capabilities":
            reply = (
                "I can answer local questions, check Home Assistant, and control supported devices."
            )
        elif intent == "home_assistant_status":
            status = await self.home_assistant.check_connection()
            reply = status.message
        else:
            reply = "I don’t know how to handle that yet. More capabilities can be added through Emily tools."

        return ChatResponse(reply=reply, intent=intent, provider=self.name, success=True)

# A future OllamaProvider can implement AssistantProvider without changing the API.
