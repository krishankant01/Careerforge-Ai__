"""
Centralized error handling (spec section 30).

Every error response — validation failures, our own domain errors, and
unhandled exceptions — comes back in the same shape:

    { "success": false, "error": { "code": "...", "message": "..." } }

so the frontend never has to special-case how a given endpoint fails.
Unhandled exceptions are logged with a full traceback server-side but never
expose a stack trace to the client.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for domain errors that carry a stable machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="INVALID_CREDENTIALS",
            message="Incorrect email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class EmailAlreadyRegisteredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="EMAIL_ALREADY_REGISTERED",
            message="An account with this email already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )


class NotAuthenticatedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="NOT_AUTHENTICATED",
            message="You must be logged in to perform this action.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ResumeNotFoundError(AppError):
    def __init__(self) -> None:
        # Deliberately identical whether the resume doesn't exist or belongs
        # to someone else — never lets a client distinguish "not found" from
        # "not yours" (spec section 44: authorization at the service layer).
        super().__init__(
            code="RESUME_NOT_FOUND",
            message="Resume not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnsupportedFileTypeError(AppError):
    def __init__(self, allowed: list[str]) -> None:
        super().__init__(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"Unsupported file type. Allowed: {', '.join(allowed)}.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class FileTooLargeError(AppError):
    def __init__(self, max_mb: int) -> None:
        super().__init__(
            code="FILE_TOO_LARGE",
            message=f"File exceeds the {max_mb}MB size limit.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class CorruptFileError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="CORRUPT_FILE",
            message="The file's contents don't match its extension, or it is corrupted.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AnalysisNotReadyError(AppError):
    def __init__(self, status_value: str) -> None:
        super().__init__(
            code="ANALYSIS_NOT_READY",
            message=f"Analysis is not available yet (resume status: {status_value}).",
            status_code=status.HTTP_409_CONFLICT,
        )


class JobNotFoundError(AppError):
    def __init__(self) -> None:
        # Same "not found == not yours" indistinguishability as ResumeNotFoundError.
        super().__init__(
            code="JOB_NOT_FOUND",
            message="Job not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class JobNotReadyError(AppError):
    def __init__(self, status_value: str) -> None:
        super().__init__(
            code="JOB_NOT_READY",
            message=f"This job description hasn't finished parsing yet (status: {status_value}).",
            status_code=status.HTTP_409_CONFLICT,
        )


class ResumeNotReadyForMatchError(AppError):
    def __init__(self, status_value: str) -> None:
        super().__init__(
            code="RESUME_NOT_READY",
            message=f"This resume hasn't finished analysis yet (status: {status_value}).",
            status_code=status.HTTP_409_CONFLICT,
        )


def _error_body(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        message = first_error.get("msg", "Invalid request data.")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("VALIDATION_ERROR", message),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "Something went wrong. Please try again."),
        )
