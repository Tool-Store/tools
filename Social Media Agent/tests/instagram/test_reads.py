import pytest

from caller import Caller
from instagram import reads

USER = Caller("user-1")
NASA_PAGE = "https://www.instagram.com/nasa/"


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    async def fake_read(caller, command, args, start_url, target):
        recorded.append((caller, command, args, start_url, target))
        return [{"username": "nasa"}]

    monkeypatch.setattr(reads.page, "read", fake_read)
    return recorded


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda: reads.profile(USER, "nasa"), ("profile", {"username": "nasa"}, NASA_PAGE, "account 'nasa'")),
        (lambda: reads.posts(USER, "nasa", 5), ("posts", {"username": "nasa", "limit": 5}, NASA_PAGE, "account 'nasa'")),
    ],
    ids=["profile", "posts"],
)
async def test_each_read_opens_the_accounts_page_and_asks_for_its_command(calls, call, expected):
    rows = await call()

    assert rows == [{"username": "nasa"}]
    assert calls == [(USER, *expected)]


def test_every_command_has_a_request_cost():
    from constants import INSTAGRAM_READ_COSTS

    assert set(INSTAGRAM_READ_COSTS) == {"profile", "posts"}
