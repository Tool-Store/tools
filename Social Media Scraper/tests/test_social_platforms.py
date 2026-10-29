import json
from unittest.mock import Mock

import pytest

import social_platforms as sp

TOKEN = "apify_test_token"


def _response(status_code=201, payload=None, text=""):
    return Mock(ok=200 <= status_code < 300, status_code=status_code, json=Mock(return_value=payload), text=text)


@pytest.fixture
def post(monkeypatch):
    fake_post = Mock(return_value=_response(payload=[{"username": "natgeo"}]))
    monkeypatch.setattr(sp.requests, "post", fake_post)
    return fake_post


@pytest.mark.parametrize(
    "call, message",
    [
        (lambda: sp.get_social_profile("tiktok", "natgeo", apify_api_token=TOKEN), "Unsupported platform"),
        (lambda: sp.get_social_profile("instagram", "", apify_api_token=TOKEN), "Invalid handle"),
        (lambda: sp.get_social_profile("instagram", "https://x.com/a", apify_api_token=TOKEN), "Invalid handle"),
        (lambda: sp.get_social_posts("x", "nasa", limit=0, apify_api_token=TOKEN), "limit must be between"),
        (lambda: sp.get_social_posts("x", "nasa", limit=51, apify_api_token=TOKEN), "limit must be between"),
        (lambda: sp.get_social_profile("x", "nasa", max_chars=0, apify_api_token=TOKEN), "max_chars must be"),
        (lambda: sp.get_social_profile("x", "nasa", apify_api_token=None), "APIFY_API_TOKEN is missing"),
    ],
    ids=["bad-platform", "empty-handle", "url-as-handle", "limit-0", "limit-51", "max-chars-0", "no-token"],
)
def test_invalid_input_fails_before_any_network_call(post, call, message):
    with pytest.raises((ValueError, RuntimeError), match=message):
        call()
    post.assert_not_called()


def test_profile_calls_actor_with_spending_cap_and_returns_json(post):
    result = sp.get_social_profile(" Instagram ", "@natgeo", apify_api_token=TOKEN)

    url = post.call_args.args[0]
    kwargs = post.call_args.kwargs
    assert url == "https://api.apify.com/v2/acts/apify~instagram-profile-scraper/run-sync-get-dataset-items"
    assert kwargs["headers"] == {"Authorization": f"Bearer {TOKEN}"}
    assert kwargs["params"]["maxTotalChargeUsd"] == sp.MAX_CHARGE_PER_RUN_USD
    assert kwargs["json"] == {"usernames": ["natgeo"]}
    assert result["platform"] == "instagram"
    assert result["handle"] == "natgeo"
    assert result["url"] == "https://www.instagram.com/natgeo/"
    assert result["count"] == 1
    assert json.loads(result["content"]) == [{"username": "natgeo"}]


@pytest.mark.parametrize(
    "platform, actor, expected_input",
    [
        ("instagram", "apify~instagram-post-scraper", {"username": ["acme"], "resultsLimit": 5}),
        (
            "facebook",
            "apify~facebook-posts-scraper",
            {"startUrls": [{"url": "https://www.facebook.com/acme/"}], "resultsLimit": 5},
        ),
        (
            "linkedin",
            "harvestapi~linkedin-profile-posts",
            {"targetUrls": ["https://www.linkedin.com/in/acme/"], "maxPosts": 5},
        ),
        ("x", "apidojo~twitter-profile-scraper", {"twitterHandles": ["acme"], "maxItems": 5}),
    ],
)
def test_posts_builds_platform_specific_actor_input(post, platform, actor, expected_input):
    sp.get_social_posts(platform, "acme", limit=5, apify_api_token=TOKEN)

    assert f"/acts/{actor}/" in post.call_args.args[0]
    assert post.call_args.kwargs["json"] == expected_input


def test_posts_never_returns_more_than_limit(post):
    post.return_value = _response(payload=[{"caption": f"post {i}"} for i in range(8)])

    result = sp.get_social_posts("instagram", "natgeo", limit=3, apify_api_token=TOKEN)

    assert result["count"] == 3
    assert len(json.loads(result["content"])) == 3


def test_only_listed_fields_are_returned_without_nested_images(post):
    post.return_value = _response(
        payload=[
            {
                "firstName": "Bill",
                "profilePicture": "https://cdn/pic.jpg",
                "currentPosition": [{"companyName": "Gates Foundation", "companyLogo": {"url": "https://cdn/l.png"}}],
            }
        ]
    )

    result = sp.get_social_profile("linkedin", "williamhgates", apify_api_token=TOKEN)

    assert json.loads(result["content"]) == [
        {"firstName": "Bill", "currentPosition": [{"companyName": "Gates Foundation"}]}
    ]


def test_post_author_blob_is_dropped(post):
    post.return_value = _response(payload=[{"text": "hello", "likeCount": 3, "author": {"name": "NASA"}}])

    result = sp.get_social_posts("x", "nasa", apify_api_token=TOKEN)

    assert json.loads(result["content"]) == [{"text": "hello", "likeCount": 3}]


def test_large_result_is_truncated_to_max_chars(post):
    post.return_value = _response(payload=[{"description": "a" * 500}])

    result = sp.get_social_profile("x", "nasa", max_chars=100, apify_api_token=TOKEN)

    assert result["truncated"] is True
    assert len(result["content"]) == 100


def test_empty_profile_result_raises_clear_error(post):
    post.return_value = _response(payload=[])

    with pytest.raises(RuntimeError, match="No public linkedin profile found for 'ghost'"):
        sp.get_social_profile("linkedin", "ghost", apify_api_token=TOKEN)


def test_apify_error_item_raises_with_its_reason(post):
    post.return_value = _response(
        payload=[{"username": "ghost", "error": "not_found", "errorDescription": "Profile does not exist"}]
    )

    with pytest.raises(RuntimeError, match=r"No public instagram profile found for 'ghost' \(Profile does not exist\)"):
        sp.get_social_profile("instagram", "ghost", apify_api_token=TOKEN)


def test_empty_posts_raise_clear_error(post):
    post.return_value = _response(payload=[])

    with pytest.raises(RuntimeError, match="No public instagram posts found for 'ghost'.*may be private"):
        sp.get_social_posts("instagram", "ghost", apify_api_token=TOKEN)


def test_error_items_are_skipped_when_public_posts_exist(post):
    post.return_value = _response(payload=[{"error": "no_items"}, {"caption": "public post"}])

    result = sp.get_social_posts("instagram", "natgeo", apify_api_token=TOKEN)

    assert result["count"] == 1
    assert json.loads(result["content"]) == [{"caption": "public post"}]


def test_x_profile_keeps_protected_flag(post):
    post.return_value = _response(payload=[{"userName": "locked", "protected": True}])

    result = sp.get_social_profile("x", "locked", apify_api_token=TOKEN)

    assert json.loads(result["content"]) == [{"userName": "locked", "protected": True}]


@pytest.mark.parametrize(
    "status_code, message",
    [(401, "rejected the API token"), (402, "credit is used up"), (408, "did not finish in time"), (429, "rate limit")],
)
def test_known_apify_errors_return_actionable_message_without_token(post, status_code, message):
    post.return_value = _response(status_code=status_code, text=f"error with {TOKEN}")

    with pytest.raises(RuntimeError, match=message) as exc_info:
        sp.get_social_profile("instagram", "natgeo", apify_api_token=TOKEN)
    assert TOKEN not in str(exc_info.value)


def test_unexpected_apify_error_includes_status_and_body(post):
    post.return_value = _response(status_code=500, text="internal failure")

    with pytest.raises(RuntimeError, match="HTTP 500: internal failure"):
        sp.get_social_profile("instagram", "natgeo", apify_api_token=TOKEN)


def test_apify_json_error_shows_only_its_message(post):
    post.return_value = _response(
        status_code=400, payload={"error": {"type": "invalid-input", "message": "Field usernames is required"}}
    )

    with pytest.raises(RuntimeError, match="HTTP 400: Field usernames is required$"):
        sp.get_social_profile("instagram", "natgeo", apify_api_token=TOKEN)


def test_non_list_apify_response_raises(post):
    post.return_value = _response(payload={"error": "unexpected"})

    with pytest.raises(RuntimeError, match="unexpected response"):
        sp.get_social_posts("facebook", "acme", apify_api_token=TOKEN)


def test_non_json_apify_response_raises(post):
    post.return_value = _response()
    post.return_value.json.side_effect = ValueError("not json")

    with pytest.raises(RuntimeError, match="unexpected response"):
        sp.get_social_posts("facebook", "acme", apify_api_token=TOKEN)


@pytest.mark.parametrize(
    "failure, message",
    [
        (sp.requests.ConnectTimeout("pool details"), "Could not reach Apify: timed out after 270s"),
        (sp.requests.ConnectionError("pool details"), "Could not reach Apify: network connection failed"),
    ],
    ids=["timeout", "connection-error"],
)
def test_network_failure_returns_clear_error_without_internals(post, failure, message):
    post.side_effect = failure

    with pytest.raises(RuntimeError, match=message) as exc_info:
        sp.get_social_profile("instagram", "natgeo", apify_api_token=TOKEN)
    assert "pool details" not in str(exc_info.value)
