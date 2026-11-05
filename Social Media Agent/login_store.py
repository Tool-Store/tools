"""
Keeps each user's site logins (browser cookies) encrypted, as one record per site in user_store.

Cookies work like a password, so they are encrypted with LOGIN_ENCRYPTION_KEY before they leave the tool;
whoever can read the stored record (on disk or in Toolstore) still cannot use the login.
"""

import json
import os
from typing import Any, Dict, List

from cryptography.fernet import Fernet, InvalidToken

import user_store
from caller import Caller
from constants import LOGIN_ENCRYPTION_KEY_ENV
from errors import LoginStoreError, NotLoggedInError, login_needed_message


def save_cookies(caller: Caller, site: str, cookies: List[Dict[str, Any]]) -> None:
    if not cookies:
        raise ValueError(f"No cookies to save for {site}; the login did not finish.")
    encrypted = _fernet().encrypt(json.dumps(cookies).encode("utf-8"))
    user_store.save(caller, _record_name(site), encrypted.decode("ascii"))


def load_cookies(caller: Caller, site: str) -> List[Dict[str, Any]]:
    encrypted = user_store.load(caller, _record_name(site))
    if not isinstance(encrypted, str) or not encrypted:
        raise NotLoggedInError(login_needed_message(site, "Not logged in to"))
    try:
        return json.loads(_fernet().decrypt(encrypted.encode("ascii")))
    except InvalidToken:
        # The key changed or the record is damaged; a fresh login replaces it.
        raise NotLoggedInError(login_needed_message(site, "The saved login cannot be read for")) from None


def _record_name(site: str) -> str:
    return f"login_{site}"


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
