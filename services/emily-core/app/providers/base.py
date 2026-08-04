from abc import ABC, abstractmethod

from app.models import ChatResponse, ProviderContext


class AssistantProvider(ABC):
    """Provider contract for local rules and future model integrations."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def process(self, message: str, context: ProviderContext) -> ChatResponse:
        raise NotImplementedError

