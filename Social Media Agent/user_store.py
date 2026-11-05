"""
Keeps this tool's small per-user records (saved logins, daily usage) for the calling user.

On Toolstore (it sets TOOLSTORE_API_BASE, TOOLSTORE_DEV_SLUG and TOOLSTORE_TOOL_SLUG at publish time) each
record is a document in this tool's own sub-collection of the user's Toolstore data. The Dev API is called
with the request's own user token and Toolstore's internal token, so Toolstore checks who is asking, and the
user's activation secrets and OAuth data in the main document are never touched. Without Toolstore, each
record is a JSON file, in a folder named by a hash of the user id.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from caller import Caller
from constants import (
    DEFAULT_USER_DATA_DIR,
    INTERNAL_TOKEN_HEADER,
    TOOLSTORE_API_BASE_ENV,
    TOOLSTORE_DEV_SLUG_ENV,
    TOOLSTORE_REQUEST_TIMEOUT_SECONDS,
    TOOLSTORE_TOOL_SLUG_ENV,
    USER_DATA_DIR_ENV,
    USER_RECORDS_SUB_COLLECTION,
)
from errors import UserStoreError
from file_store import write_atomically


def load(caller: Caller, name: str) -> Optional[Any]:
    """Return the caller's record `name`, or None when it was never saved."""
    toolstore = _toolstore_settings()
    if toolstore is None:
        path = _local_file(caller, name)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    status, body = _call(caller, "GET", _record_url(toolstore, caller, name))
    if status == 404:
        return None
    _require_success(status, f"read '{name}'")
    return ((body or {}).get("data") or {}).get("value")


def save(caller: Caller, name: str, value: Any) -> None:
    toolstore = _toolstore_settings()
    if toolstore is None:
        write_atomically(_local_file(caller, name), json.dumps(value).encode("utf-8"))
        return
    record = {"value": value}
    status, _ = _call(caller, "PUT", _record_url(toolstore, caller, name), record)
    if status == 404:
        status, _ = _call(caller, "POST", _create_url(toolstore, caller, name), record)
    _require_success(status, f"save '{name}'")


def _toolstore_settings() -> Optional[Tuple[str, str, str]]:
    names = (TOOLSTORE_API_BASE_ENV, TOOLSTORE_DEV_SLUG_ENV, TOOLSTORE_TOOL_SLUG_ENV)
    settings = tuple(os.getenv(name, "").strip() for name in names)
    return settings if all(settings) else None


def _record_url(toolstore: Tuple[str, str, str], caller: Caller, name: str) -> str:
    api_base, dev_slug, tool_slug = toolstore
    segments = (dev_slug, tool_slug, caller.user_id, USER_RECORDS_SUB_COLLECTION, name)
    return f"{api_base.rstrip('/')}/tool-user-data/sub-collection/" + "/".join(quote(part, safe="") for part in segments)


def _create_url(toolstore: Tuple[str, str, str], caller: Caller, name: str) -> str:
    api_base, dev_slug, tool_slug = toolstore
    query = urlencode(
        {
            "dev_slug": dev_slug,
            "tool_slug": tool_slug,
            "user_id": caller.user_id,
            "sub_collection": USER_RECORDS_SUB_COLLECTION,
            "document_id": name,
        }
    )
    return f"{api_base.rstrip('/')}/tool-user-data/sub-collection?{query}"


def _call(caller: Caller, method: str, url: str, body: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
    if not caller.token:
        raise UserStoreError("This request carries no user's Toolstore token, so the user's saved data cannot be used.")
    if not url.startswith(("http://", "https://")):
        raise UserStoreError(f"{TOOLSTORE_API_BASE_ENV} must be an http(s) address, got '{url}'.")
    headers = {"Authorization": f"Bearer {caller.token}", "Accept": "application/json", "Content-Type": "application/json"}
    if caller.internal_token:
        headers[INTERNAL_TOKEN_HEADER] = caller.internal_token
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=TOOLSTORE_REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310 - scheme checked above
            return response.status, json.loads(response.read() or b"null")
    except HTTPError as error:
        return error.code, None
    except (URLError, TimeoutError) as error:
        raise UserStoreError(f"Toolstore user storage could not be reached: {getattr(error, 'reason', error)}") from None


def _require_success(status: int, action: str) -> None:
    if not 200 <= status < 300:
        raise UserStoreError(f"Toolstore user storage could not {action} (HTTP {status}). Retry later.")


def _local_file(caller: Caller, name: str) -> Path:
    folder = hashlib.sha256(caller.user_id.encode("utf-8")).hexdigest()
    root = Path(os.getenv(USER_DATA_DIR_ENV, DEFAULT_USER_DATA_DIR)).expanduser()
    return root / folder / f"{name}.json"
