import os

import pytest
from cryptography.fernet import Fernet

import login_store
from caller import Caller
from constants import LOGIN_ENCRYPTION_KEY_ENV
from errors import LoginStoreError, NotLoggedInError

COOKIES = [{"name": "li_at", "value": "secret-session", "domain": ".linkedin.com", "path": "/"}]
USER = Caller("user-1")


def test_saved_cookies_load_back(local_store):
    login_store.save_cookies(USER, "linkedin", COOKIES)
    assert login_store.load_cookies(USER, "linkedin") == COOKIES


def test_saved_file_is_encrypted_private_and_not_named_after_the_user(local_store):
    login_store.save_cookies(USER, "linkedin", COOKIES)

    files = [path for path in local_store.rglob("*") if path.is_file()]
    assert len(files) == 1
    assert b"secret-session" not in files[0].read_bytes()
    assert "user-1" not in str(files[0])
    assert os.stat(files[0]).st_mode & 0o777 == 0o600


def test_each_user_only_gets_their_own_cookies(local_store):
    login_store.save_cookies(USER, "linkedin", COOKIES)
    with pytest.raises(NotLoggedInError, match="Not logged in to linkedin"):
        login_store.load_cookies(Caller("user-2"), "linkedin")


def test_saving_again_replaces_the_old_login(local_store):
    login_store.save_cookies(USER, "linkedin", COOKIES)
    newer = [{**COOKIES[0], "value": "newer-session"}]
    login_store.save_cookies(USER, "linkedin", newer)
    assert login_store.load_cookies(USER, "linkedin") == newer


def test_login_saved_with_another_key_asks_the_user_to_log_in(local_store, monkeypatch):
    login_store.save_cookies(USER, "linkedin", COOKIES)
    monkeypatch.setenv(LOGIN_ENCRYPTION_KEY_ENV, Fernet.generate_key().decode())
    with pytest.raises(NotLoggedInError, match="The saved login cannot be read for linkedin"):
        login_store.load_cookies(USER, "linkedin")


@pytest.mark.parametrize("key", ["", "too-short"])
def test_missing_or_invalid_key_is_a_setup_error(local_store, monkeypatch, key):
    monkeypatch.setenv(LOGIN_ENCRYPTION_KEY_ENV, key)
    with pytest.raises(LoginStoreError, match=LOGIN_ENCRYPTION_KEY_ENV):
        login_store.save_cookies(USER, "linkedin", COOKIES)


def test_empty_cookie_list_is_not_saved(local_store):
    with pytest.raises(ValueError, match="No cookies"):
        login_store.save_cookies(USER, "linkedin", [])
