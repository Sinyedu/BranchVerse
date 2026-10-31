"""Best-effort pull request metadata from GitHub's public REST API.

Only one URL shape is ever requested, built from an already-validated owner,
repository name and integer. The response is untrusted: it is size-limited,
parsed as JSON, and every field is type-checked and truncated before use.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

API_HOST = "api.github.com"
MAX_RESPONSE = 1_000_000
_SHA = re.compile(r"^[0-9a-f]{40}$")


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname != API_HOST:
            return None  # never follow a redirect off api.github.com
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SameHostRedirects)


def _str(value: Any, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) else None


def clean_pull(data: Any) -> dict[str, Any] | None:
    """Reduce an API response to the few typed fields BranchVerse displays."""
    if not isinstance(data, dict):
        return None
    base = data.get("base") if isinstance(data.get("base"), dict) else {}
    head = data.get("head") if isinstance(data.get("head"), dict) else {}
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    base_sha = _str(base.get("sha"), 40)
    merged = data.get("merged") is True or isinstance(data.get("merged_at"), str)
    state = data.get("state")
    return {
        "title": _str(data.get("title"), 300) or "",
        "state": "merged" if merged else (state if state in ("open", "closed") else "unknown"),
        "draft": data.get("draft") is True,
        "author": _str(user.get("login"), 60),
        "body": _str(data.get("body"), 4000) or "",
        "base_ref": _str(base.get("ref"), 200),
        "base_sha": base_sha if base_sha and _SHA.fullmatch(base_sha) else None,
        "head_label": _str(head.get("label"), 200),
        "created_at": _str(data.get("created_at"), 40),
    }


def fetch_pull_meta(owner: str, repo: str, number: int, timeout: float = 8.0) -> dict[str, Any] | None:
    """Return cleaned PR metadata, or None if unavailable (offline, rate-limited, ...)."""
    url = f"https://{API_HOST}/repos/{owner}/{repo}/pulls/{int(number)}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "BranchVerse",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with _opener.open(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            raw = resp.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            return None
        return clean_pull(json.loads(raw))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
