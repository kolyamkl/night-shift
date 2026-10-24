"""Browser request protection and error responses for the whole API."""

import psycopg
from cryptography.fernet import InvalidToken
from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..core.errors import AppError

CSRF_HEADER = "X-Veil-Request"


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def protect_browser_requests(request: Request, call_next):
        # A cross-site form or fetch cannot set this header without a CORS preflight, which CORS refuses.
        if request.url.path.startswith("/api/"):
            if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(CSRF_HEADER) != "1":
                return JSONResponse(status_code=403, content={"detail": "Missing request protection header."})
            response = await call_next(request)
            if request.url.path.startswith(("/api/auth", "/api/documents")):
                response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error(_request, exc: AppError):
        headers = {"Retry-After": "60"} if exc.status == 429 else None
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path.startswith("/api/auth/"):
            # Never echo submitted passwords in validation responses.
            return JSONResponse(status_code=422, content={"detail": "Enter a valid email and a password of 8 to 128 characters."})
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(psycopg.Error)
    async def database_unavailable(_request, _exc):
        return JSONResponse(status_code=503, content={"detail": "Document storage is unavailable. Try again shortly."})

    @app.exception_handler(InvalidToken)
    async def unreadable_document(_request, _exc):
        return JSONResponse(status_code=503, content={"detail": "Stored content could not be decrypted."})
