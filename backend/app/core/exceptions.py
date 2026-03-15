"""
Custom application exceptions.

Provides a hierarchy of exceptions for consistent error handling across the application.
All exceptions inherit from BaseAppException for centralized handling in main.py.
"""

from typing import Optional, Any


class BaseAppException(Exception):
    """
    Base class for all custom application exceptions.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code for API responses
        detail: Optional additional context (dict or string)
    """

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        detail: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message}, status_code={self.status_code})"


# ==================== Client Errors (4xx) ====================


class BadRequestException(BaseAppException):
    """Raised when request validation fails (400)."""

    def __init__(self, message: str = "Bad request", detail: Optional[Any] = None):
        super().__init__(message=message, status_code=400, detail=detail)


class UnauthorizedException(BaseAppException):
    """Raised when authentication is required but missing/invalid (401)."""

    def __init__(
        self, message: str = "Authentication required", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=401, detail=detail)


class ForbiddenException(BaseAppException):
    """Raised when user lacks permission for requested resource (403)."""

    def __init__(self, message: str = "Access forbidden", detail: Optional[Any] = None):
        super().__init__(message=message, status_code=403, detail=detail)


class NotFoundException(BaseAppException):
    """Raised when requested resource does not exist (404)."""

    def __init__(
        self, message: str = "Resource not found", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=404, detail=detail)


class ConflictException(BaseAppException):
    """Raised when request conflicts with current state (409)."""

    def __init__(
        self, message: str = "Resource conflict", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=409, detail=detail)


class ValidationException(BaseAppException):
    """Raised when data validation fails (422)."""

    def __init__(
        self, message: str = "Validation failed", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=422, detail=detail)


# ==================== Server Errors (5xx) ====================


class InternalServerException(BaseAppException):
    """Raised for unexpected internal errors (500)."""

    def __init__(
        self, message: str = "Internal server error", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=500, detail=detail)


class ServiceUnavailableException(BaseAppException):
    """Raised when external service is unavailable (503)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        detail: Optional[Any] = None,
    ):
        super().__init__(message=message, status_code=503, detail=detail)


# ==================== Domain-Specific Exceptions ====================


class SecurityPolicyException(BaseAppException):
    """
    Raised when a security-related operation fails.

    Examples:
        - Invalid encryption keys
        - Failed token verification
        - Unauthorized data access
    """

    def __init__(
        self, message: str = "Security policy violation", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=403, detail=detail)


class AIServiceException(BaseAppException):
    """
    Raised when AI service (Anthropic, OpenAI) fails.

    Examples:
        - API rate limit exceeded
        - Model unavailable
        - Invalid API key
    """

    def __init__(self, message: str = "AI service error", detail: Optional[Any] = None):
        super().__init__(message=message, status_code=503, detail=detail)


class DocumentProcessingException(BaseAppException):
    """
    Raised when document processing fails.

    Examples:
        - Unsupported file format
        - Corrupted file
        - Vectorization failure
    """

    def __init__(
        self, message: str = "Document processing failed", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=400, detail=detail)


class DebateException(BaseAppException):
    """
    Raised when multi-agent debate fails.

    Examples:
        - Consensus timeout
        - Agent response error
        - Invalid debate state
    """

    def __init__(
        self, message: str = "Debate orchestration failed", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=500, detail=detail)


class IntegrationException(BaseAppException):
    """
    Raised when third-party integration fails.

    Examples:
        - Jira API error
        - Confluence authentication failure
        - Slack webhook timeout
    """

    def __init__(
        self, message: str = "Integration error", detail: Optional[Any] = None
    ):
        super().__init__(message=message, status_code=503, detail=detail)


class ExperimentException(BaseAppException):
    """
    Raised when thesis experiment operations fail.

    Examples:
        - Invalid participant state
        - Session timeout
        - Data collection error
    """

    def __init__(self, message: str = "Experiment error", detail: Optional[Any] = None):
        super().__init__(message=message, status_code=400, detail=detail)
