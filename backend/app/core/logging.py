"""Structured logs: one line per event, `event key=value ...`, with the request id on every line.

Rule for every caller: log metadata only (ids, counts, statuses, timings, exception type names),
never document text, extracted values, questions, answers, file names or secrets. log_event() takes
keyword fields so a line is easy to grep and to parse, and so a value is never formatted into prose.
"""

import contextvars
import logging
import uuid
from collections.abc import Callable
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

ROOT = "veil"  # every app logger is veil.<area>
REQUEST_ID_HEADER = "X-Request-ID"

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Give the veil loggers one handler (once per process). Records still propagate, so pytest's
    caplog and uvicorn's root configuration see them too."""
    log = logging.getLogger(ROOT)
    if log.handlers:
        return
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s request_id=%(request_id)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(level)


def _value(value: Any) -> str:
    text = str(value)
    return f'"{text}"' if not text or any(c.isspace() or c in '"=' for c in text) else text


def log_event(log: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log `event key=value ...`. Fields must be metadata: see the module docstring."""
    if log.isEnabledFor(level):
        log.log(level, " ".join([event, *(f"{key}={_value(value)}" for key, value in fields.items())]))


class RequestIdMiddleware:
    """Pure ASGI: a request id for every HTTP request (the caller's X-Request-ID if it is short and
    printable, else a new one), bound to the log context and sent back in the response headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.lower().encode(), b"").decode("latin-1")
        rid = incoming if incoming.isprintable() and 0 < len(incoming) <= 64 else uuid.uuid4().hex
        token = request_id.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append((REQUEST_ID_HEADER.lower().encode(), rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id.reset(token)


def in_current_context(fn: Callable[[], None]) -> Callable[[], None]:
    """Wrap a thread target so its log lines keep this request's id."""
    context = contextvars.copy_context()
    return lambda: context.run(fn)
