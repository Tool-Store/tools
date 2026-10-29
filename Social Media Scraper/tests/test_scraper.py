from unittest.mock import Mock

import pytest

import scraper


@pytest.fixture
def get(monkeypatch):
    fake_get = Mock(return_value=Mock(ok=True, status_code=200, text="# Durov's Channel\npost one"))
    monkeypatch.setattr(scraper.requests, "get", fake_get)
    return fake_get


def test_telegram_reads_public_preview_through_jina(get):
    result = scraper.get_telegram_channel_posts(" @durov ", jina_api_key="jina_key")

    assert get.call_args.args[0] == "https://r.jina.ai/https://t.me/s/durov"
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer jina_key"
    assert result["channel"] == "durov"
    assert result["url"] == "https://t.me/s/durov"
    assert result["content"].startswith("# Durov's Channel")


@pytest.mark.parametrize("channel", ["", "abcd", "1durov", "durov/channel", "a" * 33, "https://t.me/durov"])
def test_telegram_rejects_invalid_channel_before_network_call(get, channel):
    with pytest.raises(ValueError, match="Invalid Telegram channel"):
        scraper.get_telegram_channel_posts(channel)
    get.assert_not_called()


def test_telegram_contact_page_raises_instead_of_returning_it(get):
    get.return_value = Mock(ok=True, status_code=200, text="Title: Telegram: Contact @ghost_channel\n\nSend Message")

    with pytest.raises(RuntimeError, match="No public Telegram channel 'ghost_channel'"):
        scraper.get_telegram_channel_posts("ghost_channel")


def test_jina_timeout_returns_clear_error(get):
    get.side_effect = scraper.requests.ReadTimeout("pool details")

    with pytest.raises(RuntimeError, match="Could not reach Jina Reader: timed out after 30s") as exc_info:
        scraper.get_telegram_channel_posts("durov")
    assert "pool details" not in str(exc_info.value)


def test_telegram_surfaces_jina_rate_limit(get):
    get.return_value = Mock(ok=False, status_code=429, text="")

    with pytest.raises(RuntimeError, match="rate limit"):
        scraper.get_telegram_channel_posts("durov")
