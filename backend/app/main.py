"""BranchVerse API. Intended for trusted local use only (binds to 127.0.0.1)."""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .api.repositories import router
from .core.errors import BranchVerseError
from .core.git_runner import prune_cache
from .core.security import (
    DEFAULT_ORIGINS,
    TOKEN_HEADER,
    host_allowed,
    new_session_token,
    origin_allowed,
    token_valid,
)

# Reachable without a session token (the token is handed out by /session).
_PUBLIC_PATHS = frozenset({"/api/health", "/api/session"})


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app(
    allowed_origins: tuple[str, ...] | None = None,
    extra_hosts: frozenset[str] = frozenset(),
    token: str | None = None,
) -> FastAPI:
    if allowed_origins is None:
        env = os.environ.get("BRANCHVERSE_ALLOWED_ORIGINS")
        allowed_origins = tuple(o.strip() for o in env.split(",")) if env else DEFAULT_ORIGINS

    prune_cache()  # drop stale GitHub downloads from earlier sessions
    app = FastAPI(title="BranchVerse", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.repo = None
    app.state.token = token or new_session_token()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # DNS-rebinding defence: only loopback Host headers are served.
        if not host_allowed(request.headers.get("host"), extra_hosts):
            return _error(403, "bad_host", "Host not allowed.")
        # Cross-site requests: reject any Origin that is not allow-listed.
        if not origin_allowed(request.headers.get("origin"), allowed_origins):
            return _error(403, "bad_origin", "Origin not allowed.")
        # Local-session authorization for everything except health/session.
        if request.method != "OPTIONS" and request.url.path not in _PUBLIC_PATHS:
            if not token_valid(request.headers.get(TOKEN_HEADER), app.state.token):
                return _error(401, "unauthorized", "Missing or invalid session token.")
        return await call_next(request)

    @app.exception_handler(BranchVerseError)
    async def _domain_error(_: Request, exc: BranchVerseError):
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, __: RequestValidationError):
        return _error(422, "invalid_request", "The request was not valid.")

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, __: Exception):
        return _error(500, "internal_error", "Unexpected server error.")

    app.add_middleware(GZipMiddleware, minimum_size=1024)  # smaller payloads for big lists
    # Added last so it is outermost and answers CORS preflights first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-BranchVerse-Token"],
        allow_credentials=False,
    )
    app.include_router(router)
    return app


app = create_app()
