import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

import user_store
from caller import Caller
from constants import TOOLSTORE_API_BASE_ENV, TOOLSTORE_DEV_SLUG_ENV, TOOLSTORE_TOOL_SLUG_ENV, USER_DATA_DIR_ENV
from errors import UserStoreError

RECORDS = "/v1/tool-user-data/sub-collection"


class _DevApi(BaseHTTPRequestHandler):
    """Behaves like Toolstore's Dev API sub-collection routes, keeping records in memory."""

    records = {}
    requests = []
    fail_with = None

    def do_GET(self):
        self._handle(lambda key: (200, {"data": self.records[key]}) if key in self.records else (404, {"detail": "not found"}))

    def do_PUT(self):
        def update(key):
            if key not in self.records:
                return 404, {"detail": "not found"}
            self.records[key] = self._body()
            return 200, {"data": self.records[key]}

        self._handle(update)

    def do_POST(self):
        query = parse_qs(urlsplit(self.path).query)
        key = "/".join(query[name][0] for name in ("dev_slug", "tool_slug", "user_id", "sub_collection", "document_id"))
        self._record()
        self.records[key] = self._body()
        self._reply(200, {"data": self.records[key]})

    def _handle(self, action):
        self._record()
        if self.fail_with:
            return self._reply(self.fail_with, {"detail": "failure"})
        status, body = action(urlsplit(self.path).path.removeprefix(RECORDS + "/"))
        self._reply(status, body)

    def _record(self):
        type(self).requests.append((self.command, self.path, dict(self.headers)))

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers["Content-Length"])))

    def _reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def toolstore(monkeypatch):
    _DevApi.records, _DevApi.requests, _DevApi.fail_with = {}, [], None
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DevApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv(TOOLSTORE_API_BASE_ENV, f"http://127.0.0.1:{server.server_address[1]}/v1")
    monkeypatch.setenv(TOOLSTORE_DEV_SLUG_ENV, "dev-1")
    monkeypatch.setenv(TOOLSTORE_TOOL_SLUG_ENV, "social-media-agent")
    yield _DevApi
    server.shutdown()


@pytest.fixture
def local(tmp_path, monkeypatch):
    for name in (TOOLSTORE_API_BASE_ENV, TOOLSTORE_DEV_SLUG_ENV, TOOLSTORE_TOOL_SLUG_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(USER_DATA_DIR_ENV, str(tmp_path))
    return tmp_path


USER = Caller("user-1", token="user-jwt", internal_token="signed")


def test_local_record_saves_and_loads_back(local):
    user_store.save(USER, "usage", {"date": "2026-11-05", "counts": {"linkedin": 2}})

    assert user_store.load(USER, "usage") == {"date": "2026-11-05", "counts": {"linkedin": 2}}


def test_local_records_are_private_files_in_a_folder_not_named_after_the_user(local):
    user_store.save(USER, "login_linkedin", "encrypted")

    [path] = [path for path in local.rglob("*") if path.is_file()]
    assert "user-1" not in str(path)
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_missing_local_record_is_none(local):
    assert user_store.load(USER, "usage") is None
    assert user_store.load(Caller("user-2"), "usage") is None


def test_toolstore_record_is_created_then_updated_in_this_tools_own_sub_collection(toolstore):
    user_store.save(USER, "usage", {"counts": {"linkedin": 1}})
    user_store.save(USER, "usage", {"counts": {"linkedin": 2}})

    assert user_store.load(USER, "usage") == {"counts": {"linkedin": 2}}
    assert list(toolstore.records) == ["dev-1/social-media-agent/user-1/social_media_agent/usage"]
    assert [method for method, _, _ in toolstore.requests] == ["PUT", "POST", "PUT", "GET"]


def test_toolstore_calls_carry_the_users_own_token_and_toolstores_internal_token(toolstore):
    user_store.load(USER, "usage")

    [(_, _, headers)] = toolstore.requests
    assert headers["Authorization"] == "Bearer user-jwt"
    assert headers["X-Internal-Token"] == "signed"


def test_missing_toolstore_record_is_none(toolstore):
    assert user_store.load(USER, "login_linkedin") is None


def test_user_ids_are_escaped_in_toolstore_paths(toolstore):
    user_store.load(Caller("a/b", token="t"), "usage")

    [(_, path, _)] = toolstore.requests
    assert path.endswith("/dev-1/social-media-agent/a%2Fb/social_media_agent/usage")


@pytest.mark.parametrize("status", [401, 403, 500])
def test_toolstore_refusal_or_failure_is_an_error_not_a_missing_record(toolstore, status):
    toolstore.fail_with = status

    with pytest.raises(UserStoreError, match=f"HTTP {status}"):
        user_store.load(USER, "usage")
    with pytest.raises(UserStoreError, match=f"HTTP {status}"):
        user_store.save(USER, "usage", {})


def test_request_without_a_user_token_cannot_use_toolstore_storage(toolstore):
    with pytest.raises(UserStoreError, match="user's Toolstore token"):
        user_store.load(Caller("user-1"), "usage")
    assert toolstore.requests == []


def test_unreachable_toolstore_is_an_error(toolstore, monkeypatch):
    monkeypatch.setenv(TOOLSTORE_API_BASE_ENV, "http://127.0.0.1:9/v1")

    with pytest.raises(UserStoreError, match="could not be reached"):
        user_store.load(USER, "usage")
