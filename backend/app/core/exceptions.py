from typing import Any, Optional


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details
        super().__init__(message)

    def to_dict(self) -> dict:
        """Serializes exception to a standardized API response dictionary."""
        payload = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details is not None:
            payload["error"]["details"] = self.details
        return payload


class NotFoundError(AppException):

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message, status_code=404, code=code, details=details
        )


class ValidationError(AppException):

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message, status_code=422, code=code, details=details
        )


class UnauthorizedError(AppException):

    def __init__(
        self,
        message: str = "Unauthorized",
        code: str = "UNAUTHORIZED",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message, status_code=401, code=code, details=details
        )


class ForbiddenError(AppException):

    def __init__(
        self,
        message: str = "Forbidden",
        code: str = "FORBIDDEN",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message, status_code=403, code=code, details=details
        )


class ConflictError(AppException):

    def __init__(
        self,
        message: str = "Resource already exists",
        code: str = "CONFLICT",
        details: Optional[Any] = None,
    ):
        super().__init__(
            message, status_code=409, code=code, details=details
        )