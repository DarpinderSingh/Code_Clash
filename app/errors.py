from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    def __init__(self, message: str, code: str = "BAD_REQUEST", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ValidationError(AppException):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message=message, code=code, status_code=400)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(message=message, code=code, status_code=401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Permission denied", code: str = "FORBIDDEN"):
        super().__init__(message=message, code=code, status_code=403)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message=message, code=code, status_code=404)


class ConflictError(AppException):
    def __init__(self, message: str = "Operation conflict", code: str = "CONFLICT"):
        super().__init__(message=message, code=code, status_code=409)


class InsufficientStockError(ConflictError):
    def __init__(self, message: str = "Insufficient product stock", code: str = "INSUFFICIENT_STOCK"):
        super().__init__(message=message, code=code)


def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Formulate a clear error message from pydantic errors
    errors = exc.errors()
    msg = errors[0].get("msg", "Validation error") if errors else "Malformed request body"
    loc = errors[0].get("loc", []) if errors else []
    field_name = str(loc[-1]) if loc else "field"
    detailed_msg = f"{field_name}: {msg}"
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "VALIDATION_ERROR", "message": detailed_msg}},
    )


def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
    }
    code = code_map.get(exc.status_code, "ERROR")
    message = str(exc.detail) if exc.detail else "An error occurred"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
    )
