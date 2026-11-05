import pytest
from cryptography.fernet import Fernet

from constants import (
    LOGIN_ENCRYPTION_KEY_ENV,
    TOOLSTORE_API_BASE_ENV,
    TOOLSTORE_DEV_SLUG_ENV,
    TOOLSTORE_TOOL_SLUG_ENV,
    USER_DATA_DIR_ENV,
)


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    """User records in a temporary folder (no Toolstore), with a fresh login encryption key."""
    for name in (TOOLSTORE_API_BASE_ENV, TOOLSTORE_DEV_SLUG_ENV, TOOLSTORE_TOOL_SLUG_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(USER_DATA_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(LOGIN_ENCRYPTION_KEY_ENV, Fernet.generate_key().decode())
    return tmp_path
