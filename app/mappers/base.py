from app.models.schemas.domain import DomainCommand

class BaseEcoSoftPayloadMapper:
    def build(self, command: DomainCommand) -> dict:
        raise NotImplementedError
