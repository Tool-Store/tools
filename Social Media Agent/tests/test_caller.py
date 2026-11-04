import base64
import json

import pytest

import caller
from constants import LOCAL_USER_ID_ENV
from errors import CallerError


def _jwt(claims):
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


@pytest.fixture(autouse=True)
def no_local_user(monkeypatch):
    monkeypatch.delenv(LOCAL_USER_ID_ENV, raising=False)


def test_user_comes_from_the_jwt_header():
    assert caller.user_id_from_headers({"X-Toolstore-JWT": _jwt({"user_id": "user-1"})}) == "user-1"


def test_user_comes_from_a_bearer_token_when_there_is_no_jwt_header():
    assert caller.user_id_from_headers({"Authorization": "Bearer " + _jwt({"sub": "user-2"})}) == "user-2"


def test_header_names_are_case_insensitive():
    assert caller.user_id_from_headers({"x-toolstore-jwt": _jwt({"uid": "user-3"})}) == "user-3"


def test_matching_user_id_header_is_accepted():
    headers = {"X-Toolstore-JWT": _jwt({"user_id": "user-1"}), "X-Toolstore-User-Id": "user-1"}
    assert caller.user_id_from_headers(headers) == "user-1"


def test_user_id_header_alone_is_used_when_there_is_no_token():
    assert caller.user_id_from_headers({"X-Toolstore-User-Id": "user-4"}) == "user-4"


def test_user_id_header_that_differs_from_the_token_is_refused():
    headers = {"X-Toolstore-JWT": _jwt({"user_id": "user-1"}), "X-Toolstore-User-Id": "user-2"}
    with pytest.raises(CallerError, match="does not match"):
        caller.user_id_from_headers(headers)


@pytest.mark.parametrize("token", ["not-a-jwt", "a.%%%.c", _jwt(["not", "an", "object"]), _jwt({"user_id": "  "})])
def test_unreadable_token_gives_no_user(token):
    with pytest.raises(CallerError, match="No Toolstore user"):
        caller.user_id_from_headers({"X-Toolstore-JWT": token})


def test_local_user_is_used_when_the_request_has_no_identity(monkeypatch):
    monkeypatch.setenv(LOCAL_USER_ID_ENV, "local-dev")
    assert caller.user_id_from_headers({}) == "local-dev"


def test_request_identity_wins_over_the_local_user(monkeypatch):
    monkeypatch.setenv(LOCAL_USER_ID_ENV, "local-dev")
    assert caller.user_id_from_headers({"X-Toolstore-User-Id": "user-5"}) == "user-5"


def test_no_identity_and_no_local_user_is_refused():
    with pytest.raises(CallerError, match="No Toolstore user"):
        caller.user_id_from_headers({})


def test_current_user_id_outside_a_request_uses_the_local_user(monkeypatch):
    monkeypatch.setenv(LOCAL_USER_ID_ENV, "local-dev")
    assert caller.current_user_id() == "local-dev"
