import pytest

from caller import Caller
from x import reads

USER = Caller("user-1")


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    async def fake_read(caller, command, args, target):
        recorded.append((caller, command, args, target))
        return [{"id": "101"}]

    monkeypatch.setattr(reads.page, "read", fake_read)
    return recorded


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda: reads.profile(USER, "NASA"), ("profile", {"username": "NASA"}, "account '@NASA'")),
        (lambda: reads.tweets(USER, "NASA", 5), ("tweets", {"username": "NASA", "limit": 5}, "account '@NASA'")),
        (lambda: reads.search(USER, "from:nasa moon", 3),
         ("search", {"query": "from:nasa moon", "limit": 3}, "results for 'from:nasa moon'")),
        (lambda: reads.thread(USER, "20", 4), ("thread", {"tweet_id": "20", "limit": 4}, "tweet 20")),
    ],
    ids=["profile", "tweets", "search", "thread"],
)
async def test_each_read_asks_for_its_command_and_names_its_target(calls, call, expected):
    rows = await call()

    assert rows == [{"id": "101"}]
    assert calls == [(USER, *expected)]
