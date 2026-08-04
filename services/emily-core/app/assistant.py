from app.models import ChatResponse, ProviderContext
from app.providers.base import AssistantProvider


class Assistant:
    def __init__(self, providers: list[AssistantProvider]) -> None:
        self.providers = providers

    @property
    def enabled_provider_names(self) -> list[str]:
        return [provider.name for provider in self.providers]

    async def process(self, message: str) -> ChatResponse:
        context = ProviderContext()
        for provider in self.providers:
            if await provider.is_available():
                return await provider.process(message, context)
        return ChatResponse(
            reply="No assistant provider is currently available.",
            intent="unavailable",
            provider="none",
            success=False,
        )

