"""
Keeps each user's site logins (browser cookies) encrypted on disk.

Cookies work like a password, so they are encrypted with LOGIN_ENCRYPTION_KEY and the files are
readable by the server user only. Folders are named by a hash of the user id, not the id itself.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from cryptography.fernet import Fernet, InvalidToken

from constants import (
    DEFAULT_LOGIN_STORE_DIR,
    LOGIN_ENCRYPTION_KEY_ENV,
    LOGIN_STORE_DIR_ENV,
)
from errors import LoginStoreError, NotLoggedInError, login_needed_message
from file_store import write_atomically


def save_cookies(user_id: str, site: str, cookies: List[Dict[str, Any]]) -> None:
    if not cookies:
        raise ValueError(f"No cookies to save for {site}; the login did not finish.")
    write_atomically(_login_file(user_id, site), _fernet().encrypt(json.dumps(cookies).encode("utf-8")))


def load_cookies(user_id: str, site: str) -> List[Dict[str, Any]]:
    path = _login_file(user_id, site)
    if not path.is_file():
        raise NotLoggedInError(login_needed_message(site, "Not logged in to"))
    try:
        return json.loads(_fernet().decrypt(path.read_bytes()))
    except InvalidToken:
        # The key changed or the file is damaged; a fresh login replaces it.
        raise NotLoggedInError(login_needed_message(site, "The saved login cannot be read for")) from None


def _login_file(user_id: str, site: str) -> Path:
    folder = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    root = Path(os.getenv(LOGIN_STORE_DIR_ENV, DEFAULT_LOGIN_STORE_DIR)).expanduser()
    return root / folder / f"{site}.enc"


def _fernet() -> Fernet:
    key = os.getenv(LOGIN_ENCRYPTION_KEY_ENV, "").strip()
    if not key:
        raise LoginStoreError(f"{LOGIN_ENCRYPTION_KEY_ENV} is not set; logins cannot be saved or read.")
    try:
        return Fernet(key)
    except ValueError:
        raise LoginStoreError(
            f"{LOGIN_ENCRYPTION_KEY_ENV} is not a valid key. Create one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from None
