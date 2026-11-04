"""
Works out which Toolstore user made the current MCP request.

The Toolstore Tool Router adds the user's JWT and user id as headers to every tool call. The id
inside the JWT wins, and a different X-Toolstore-User-Id header is refused, so a caller cannot point
a valid token at another user's saved logins. The JWT signature is not checked here: the tool must
only be reachable through the Tool Router (see PLAN.md). Locally, TOOLSTORE_USER_ID names the user.
"""

import base64
import binascii
import json
import os
from typing import Mapping

from constants import (
    AUTHORIZATION_HEADER,
    JWT_HEADER,
    JWT_USER_ID_CLAIMS,
    LOCAL_USER_ID_ENV,
    USER_ID_HEADER,
)
from errors import CallerError


def current_user_id() -> str:
    """Return the user id for the MCP request being handled; call it on the request's own task."""
    return user_id_from_headers(_request_headers())


def user_id_from_headers(headers: Mapping[str, str]) -> str:
    lowered = {key.lower(): str(value).strip() for key, value in headers.items()}
    token = lowered.get(JWT_HEADER.lower()) or _bearer_token(lowered.get(AUTHORIZATION_HEADER.lower(), ""))
    token_user_id = _user_id_from_jwt(token) if token else ""
    header_user_id = lowered.get(USER_ID_HEADER.lower(), "")
    if token_user_id and header_user_id and token_user_id != header_user_id:
        raise CallerError(f"{USER_ID_HEADER} does not match the user in the request token; request refused.")
    user_id = token_user_id or header_user_id or os.getenv(LOCAL_USER_ID_ENV, "").strip()
    if not user_id:
        raise CallerError(
            "No Toolstore user on this request. Call the tool through Toolstore, "
            f"or set {LOCAL_USER_ID_ENV} when running it locally."
        )
    return user_id


def _request_headers() -> Mapping[str, str]:
    from mcp.server.lowlevel.server import request_ctx

    context = request_ctx.get(None)
    if context is None or context.request is None:
        return {}
    return context.request.headers


def _bearer_token(value: str) -> str:
    scheme, _, token = value.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def _user_id_from_jwt(token: str) -> str:
    parts = token.split(".")
    if len(parts) != 3:
        return ""
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (binascii.Error, ValueError):
        return ""
    if not isinstance(claims, dict):
        return ""
    for claim in JWT_USER_ID_CLAIMS:
        value = str(claims.get(claim) or "").strip()
        if value:
            return value
    return ""
