# backend/core/exceptions.py
#
# CONCEPT: Custom Exception Hierarchy
#
# Python lets you create custom exception classes by inheriting from Exception.
# Why bother?
#
# 1. PRECISION: You can catch a specific error type, not just "any exception."
#    try: ...
#    except NotFoundError: return 404  ← You know exactly what went wrong
#    except ValidationError: return 422
#
# 2. HTTP MAPPING: Each exception maps to an HTTP status code.
#    This lets FastAPI automatically return the right status when an exception
#    is raised, rather than always returning 500 Internal Server Error.
#
# 3. READABILITY: raise NotFoundError("Problem not found") is 10x clearer
#    than raise Exception("Error: the thing you wanted was not found somewhere")


class PrepOSError(Exception):
    """
    Base exception for all PrepOS errors.
    All custom exceptions inherit from this, so you can catch
    any PrepOS-specific error with: except PrepOSError.
    """
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)  # Call parent Exception.__init__


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
