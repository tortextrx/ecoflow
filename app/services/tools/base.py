from abc import ABC, abstractmethod
from app.models.schemas.domain import DomainCommand
from app.models.schemas.tools import ToolResult

class BaseTool(ABC):
    @abstractmethod
    async def execute(self, command: DomainCommand) -> ToolResult:
        pass
