"""
API key middleware.

Checks the X-API-Key header against settings.API_KEY_SECRET.
Excluded paths: /health, /docs, /openapi.json, /redoc.
"""
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

log = structlog.get_logger()

_EXCLUDED_PREFIXES = ("/api/v1/health", "/docs", "/openapi.json", "/redoc")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in _EXCLUDED_PREFIXES):
            return await call_next(request)  # type: ignore[operator]

        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != settings.API_KEY_SECRET:
            remote = request.client.host if request.client else "unknown"
            log.warning("auth.rejected", path=path, remote=remote)
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)  # type: ignore[operator]
