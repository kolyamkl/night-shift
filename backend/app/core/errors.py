"""Errors the services raise, each carrying the HTTP status and the message the client sees.

Services raise these instead of HTTPException, so they stay independent of the web layer; one handler
in app.api turns any AppError into {"detail": message}. Messages never contain document text."""


class AppError(Exception):
    status = 500
    detail = "Something went wrong."

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail


class BadRequest(AppError):
    status = 400


class Unauthorized(AppError):
    status = 401
    detail = "Please log in to continue."


class NotFound(AppError):
    status = 404


class Conflict(AppError):
    status = 409


class TooLarge(AppError):
    status = 413


class Unsupported(AppError):
    status = 415


class TooManyAttempts(AppError):
    status = 429
    detail = "Too many attempts. Please wait a minute."


class ModelFailed(AppError):
    status = 502
    detail = "The model did not answer. Try again."


class Unavailable(AppError):
    status = 503


class MissingDocument(NotFound):
    detail = "Document not found."


class StaleRevision(Conflict):
    detail = "The document changed. Reload it before trying again."


class Superseded(Conflict):
    """A newer scan or correction replaced this scan's reserved revision."""
    detail = "A newer scan of this document started, so this one stopped."
