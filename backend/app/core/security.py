"""Browser request protection and the secrets helpers shared by auth.

- CSRF: every state-changing /api request must carry `X-Veil-Request: 1`. A cross-site form or
  image cannot set a custom header, and a cross-site fetch that sets one needs a CORS preflight,
  which only the configured origins pass. Session cookies are also SameSite=Lax (modules/auth).
- Caching: auth and document responses are `Cache-Control: no-store`, so no shared or browser cache
  keeps a document, a result or a session answer.
"""

import hashlib
import secrets

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.core.errors import error_response

CSRF_HEADER = "X-Veil-Request"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
NO_STORE_PREFIXES = ("/api/auth", "/api/documents")


async def protect_browser_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        return error_response(403, "Missing request protection header.")
    response = await call_next(request)
    if path.startswith(NO_STORE_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
    return response


def new_token() -> str:
    """A session token: 256 bits from the OS's CSPRNG."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """What the database stores instead of a token, so a database leak holds no usable session."""
    return hashlib.sha256(token.encode()).hexdigest()
