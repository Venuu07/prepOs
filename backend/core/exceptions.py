# backend/core/exceptions.py


class PrepOSError(Exception):
    """
    Base exception for all PrepOS errors.
    All custom exceptions inherit from this, so you can catch
    any PrepOS-specific error with: except PrepOSError.
    """
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)  


class NotFoundError(PrepOSError):
    """
    Raised when a requested resource doesn't exist in the database.
    Maps to HTTP 404 Not Found.
    Example: User requests problem with id=999 but it doesn't exist.
    """
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(PrepOSError):
    """
    Raised when input data fails business-level validation
    (beyond basic type/format validation, which Pydantic handles).
    Maps to HTTP 422 Unprocessable Entity.
    Example: Setting a problem's confidence to "HIGH" when it's not solved.
    """
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)


class ConflictError(PrepOSError):
    """
    Raised when an operation conflicts with existing data.
    Maps to HTTP 409 Conflict.
    Example: Trying to create a subject that already exists.
    """
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status_code=409)


class AIServiceError(PrepOSError):
    """
    Raised when the AI/LLM service fails or returns unexpected output.
    Maps to HTTP 503 Service Unavailable.
    Example: Gemini API is down, or returns malformed JSON.
    """
    def __init__(self, message: str = "AI service error"):
        super().__init__(message, status_code=503)
