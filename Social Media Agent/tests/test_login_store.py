import os

import pytest
from cryptography.fernet import Fernet

import login_store
from constants import LOGIN_ENCRYPTION_KEY_ENV, LOGIN_STORE_DIR_ENV
from errors import LoginStoreError, NotLoggedInError

COOKIES = [{"name": "li_at", "value": "secret-session", "domain": ".linkedin.com", "path": "/"}]


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(LOGIN_STORE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(LOGIN_ENCRYPTION_KEY_ENV, Fernet.generate_key().decode())
    return tmp_path


def test_saved_cookies_load_back(store_dir):
    login_store.save_cookies("user-1", "linkedin", COOKIES)
    assert login_store.load_cookies("user-1", "linkedin") == COOKIES


def test_saved_file_is_encrypted_private_and_not_named_after_the_user(store_dir):
    login_store.save_cookies("user-1", "linkedin", COOKIES)

    files = [path for path in store_dir.rglob("*") if path.is_file()]
    assert len(files) == 1
    assert b"secret-session" not in files[0].read_bytes()
    assert "user-1" not in str(files[0])
    assert os.stat(files[0]).st_mode & 0o777 == 0o600


def test_each_user_only_gets_their_own_cookies(store_dir):
    login_store.save_cookies("user-1", "linkedin", COOKIES)
    with pytest.raises(NotLoggedInError, match="Not logged in to linkedin"):
        login_store.load_cookies("user-2", "linkedin")


def test_saving_again_replaces_the_old_login(store_dir):
    login_store.save_cookies("user-1", "linkedin", COOKIES)
    newer = [{**COOKIES[0], "value": "newer-session"}]
    login_store.save_cookies("user-1", "linkedin", newer)
    assert login_store.load_cookies("user-1", "linkedin") == newer


def test_login_saved_with_another_key_asks_the_user_to_log_in(store_dir, monkeypatch):
    login_store.save_cookies("user-1", "linkedin", COOKIES)
    monkeypatch.setenv(LOGIN_ENCRYPTION_KEY_ENV, Fernet.generate_key().decode())
    with pytest.raises(NotLoggedInError, match="The saved login cannot be read for linkedin"):
        login_store.load_cookies("user-1", "linkedin")


@pytest.mark.parametrize("key", ["", "too-short"])
def test_missing_or_invalid_key_is_a_setup_error(store_dir, monkeypatch, key):
    monkeypatch.setenv(LOGIN_ENCRYPTION_KEY_ENV, key)
    with pytest.raises(LoginStoreError, match=LOGIN_ENCRYPTION_KEY_ENV):
        login_store.save_cookies("user-1", "linkedin", COOKIES)


def test_empty_cookie_list_is_not_saved(store_dir):
    with pytest.raises(ValueError, match="No cookies"):
        login_store.save_cookies("user-1", "linkedin", [])
