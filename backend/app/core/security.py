"""Local web-security helpers: input validation, Host/Origin checks, session token."""

from __future__ import annotations

import re
import secrets
from urllib.parse import urlsplit

from .errors import InvalidInput

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})
DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
TOKEN_HEADER = "x-branchverse-token"
MAX_PATH_LEN = 4096


def validate_sha(value: str) -> str:
    """Accept only full lowercase 40-hex object IDs: no revision expressions."""
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise InvalidInput("Expected a full 40-character commit SHA.")
    return value


def validate_repo_path_input(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput("Enter a repository path.")
    if "\x00" in value or len(value) > MAX_PATH_LEN:
        raise InvalidInput("The repository path is not valid.")
    return value.strip()


def host_allowed(host_header: str | None, extra_hosts: frozenset[str] = frozenset()) -> bool:
    """Reject DNS-rebinding: the Host header must name a loopback host."""
    if not host_header:
        return False
    host = host_header.strip().lower()
    if host.startswith("["):
        name = host.split("]")[0] + "]"
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return name in LOCAL_HOSTNAMES or name in extra_hosts


def origin_allowed(origin: str | None, allowed: tuple[str, ...]) -> bool:
    """No Origin (same-origin GET, curl) is fine; otherwise it must be allow-listed."""
    if origin is None:
        return True
    parts = urlsplit(origin)
    normalized = f"{parts.scheme}://{parts.netloc}".lower()
    return normalized in {a.lower() for a in allowed}


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_valid(supplied: str | None, expected: str) -> bool:
    return bool(supplied) and secrets.compare_digest(supplied, expected)
