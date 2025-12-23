from typing import List, Optional


class DomainException(Exception):
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code or "DOMAIN_ERROR"


class ValidationError(DomainException):
    def __init__(self, errors: List[str]):
        message = "; ".join(errors)
        super().__init__(message, "VALIDATION_ERROR")
        self.errors = errors


class NotFoundError(DomainException):
    def __init__(self, entity: str, entity_id: int):
        message = f"{entity} with id {entity_id} not found"
        super().__init__(message, "NOT_FOUND")
        self.entity = entity
        self.entity_id = entity_id
