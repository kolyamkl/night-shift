"""One error type hierarchy and the handlers that turn errors into HTTP responses.

Services and repositories raise AppError subclasses, never HTTPException. Every error response has
the body the frontend reads, {"detail": "<message for the user>"}, the same shape FastAPI uses for
its own errors. Messages never carry document text, values or internal details: storage and
decryption failures get fixed, generic messages.
"""

from http import HTTPStatus
from typing import ClassVar

import psycopg
from cryptography.fernet import InvalidToken
from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

AUTH_PATHS = "/api/auth/"


class AppError(Exception):
    """An error the client should see. Subclasses set the status and may set a default message."""

    status: ClassVar[HTTPStatus] = HTTPStatus.INTERNAL_SERVER_ERROR
    default_detail: ClassVar[str | None] = None

    def __init__(self, detail: str | None = None, *, headers: dict[str, str] | None = None) -> None:
        self.detail = detail or self.default_detail or self.status.phrase
        self.headers = headers
        super().__init__(self.detail)


class BadRequestError(AppError):
    status = HTTPStatus.BAD_REQUEST


class UnauthorizedError(AppError):
    status = HTTPStatus.UNAUTHORIZED


class ForbiddenError(AppError):
    status = HTTPStatus.FORBIDDEN


class NotFoundError(AppError):
    status = HTTPStatus.NOT_FOUND


class ConflictError(AppError):
    status = HTTPStatus.CONFLICT


class PayloadTooLargeError(AppError):
    status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE


class UnsupportedMediaTypeError(AppError):
    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE


class TooManyRequestsError(AppError):
    status = HTTPStatus.TOO_MANY_REQUESTS


class BadGatewayError(AppError):
    status = HTTPStatus.BAD_GATEWAY


class ServiceUnavailableError(AppError):
    status = HTTPStatus.SERVICE_UNAVAILABLE


def error_response(status: int, detail: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=int(status), content={"detail": detail}, headers=headers)


async def _app_error(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)  # noqa: S101 - narrowing for the type checker
    return error_response(exc.status, exc.detail, exc.headers)


async def _invalid_request(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    if request.url.path.startswith(AUTH_PATHS):
        # Never echo submitted passwords in validation responses.
        return error_response(422, "Enter a valid email and a password of 8 to 128 characters.")
    return await request_validation_exception_handler(request, exc)


async def _database_unavailable(_request: Request, _exc: Exception) -> Response:
    return error_response(503, "Document storage is unavailable. Try again shortly.")


async def _unreadable_payload(_request: Request, _exc: Exception) -> Response:
    return error_response(503, "Stored content could not be decrypted.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _invalid_request)
    app.add_exception_handler(psycopg.Error, _database_unavailable)
    app.add_exception_handler(InvalidToken, _unreadable_payload)
