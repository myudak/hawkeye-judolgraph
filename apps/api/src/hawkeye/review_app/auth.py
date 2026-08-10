"""Optional single-operator HTTP Basic access gate for the local console."""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import secrets
from dataclasses import dataclass

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_AUTH_USERNAME_ENV = "HAWKEYE_AUTH_USERNAME"
_AUTH_PASSWORD_ENV = "HAWKEYE_AUTH_PASSWORD"
_PUBLIC_PATHS = frozenset({"/health"})


@dataclass(frozen=True)
class BasicAuthSettings:
    """Validated credentials kept only in process memory."""

    credential_digest: bytes

    @classmethod
    def from_environment(cls) -> BasicAuthSettings | None:
        """Load an optional all-or-nothing credential pair from the environment."""

        username = os.environ.get(_AUTH_USERNAME_ENV, "")
        password = os.environ.get(_AUTH_PASSWORD_ENV, "")
        if not username and not password:
            return None
        if not username or not password:
            raise ValueError(
                "HAWKEYE_AUTH_USERNAME and HAWKEYE_AUTH_PASSWORD must both be configured"
            )
        _validate_credential(username, name=_AUTH_USERNAME_ENV, maximum_bytes=128, colon=False)
        _validate_credential(password, name=_AUTH_PASSWORD_ENV, maximum_bytes=256, colon=True)
        return cls(
            credential_digest=_credential_digest(username.encode("utf-8"), password.encode("utf-8"))
        )


class BasicAuthMiddleware:
    """Require one timing-safe Basic credential pair for every non-health HTTP route."""

    def __init__(self, app: ASGIApp, *, settings: BasicAuthSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in _PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        supplied = _decode_basic_credentials(scope)
        candidate = supplied if supplied is not None else (b"", b"")
        authenticated = secrets.compare_digest(
            _credential_digest(*candidate), self.settings.credential_digest
        )
        if not authenticated:
            response = JSONResponse(
                status_code=401,
                content={"error": "authentication_required"},
                headers={"WWW-Authenticate": 'Basic realm="HAWKEYE", charset="UTF-8"'},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _validate_credential(value: str, *, name: str, maximum_bytes: int, colon: bool) -> None:
    encoded = value.encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise ValueError(f"{name} is too long")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{name} cannot contain control characters")
    if not colon and ":" in value:
        raise ValueError(f"{name} cannot contain a colon")


def _decode_basic_credentials(scope: Scope) -> tuple[bytes, bytes] | None:
    values = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
    if len(values) != 1:
        return None
    try:
        scheme, encoded = values[0].split(b" ", 1)
        if scheme.lower() != b"basic" or not encoded or len(encoded) > 1024 or b" " in encoded:
            return None
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None
    username, separator, password = decoded.partition(b":")
    if not separator:
        return None
    return username, password


def _credential_digest(username: bytes, password: bytes) -> bytes:
    framed = len(username).to_bytes(4, "big") + username + password
    return hashlib.sha256(framed).digest()
