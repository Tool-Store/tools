import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

import requests

from scraper import DEFAULT_MAX_CHARS, truncated_result, unreachable_error, validate_max_chars

logger = logging.getLogger(__name__)

APIFY_RUN_SYNC_URL = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
# Apify holds a sync request open for at most 300s; leave headroom for the HTTP round trip.
ACTOR_RUN_TIMEOUT_SECONDS = 240
HTTP_TIMEOUT_SECONDS = ACTOR_RUN_TIMEOUT_SECONDS + 30
# Hard spending cap per actor run, so one call can never drain the monthly Apify credit.
MAX_CHARGE_PER_RUN_USD = 0.50
DEFAULT_POSTS_LIMIT = 10
MAX_POSTS_LIMIT = 50
_HANDLE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_IMAGE_KEY = re.compile(r"pic|logo|avatar|photo|image|thumbnail|cover", re.IGNORECASE)
_APIFY_ERROR_HINTS = {
    401: "Apify rejected the API token. Check APIFY_API_TOKEN in the server environment.",
    402: "Apify usage credit is used up for this month. Wait for the monthly reset or upgrade the Apify plan.",
    408: "The Apify scraper did not finish in time. Retry with a lower limit.",
    429: "Apify rate limit reached. Retry in a minute.",
}


class _ActorTarget(NamedTuple):
    handle: str
    url: str
    limit: int


@dataclass(frozen=True)
class _Platform:
    profile_url: str
    profile_actor: str
    posts_actor: str
    profile_input: Callable[[_ActorTarget], Dict[str, Any]]
    posts_input: Callable[[_ActorTarget], Dict[str, Any]]
    profile_fields: Tuple[str, ...]
    post_fields: Tuple[str, ...]


# Actor IDs and input fields follow each actor's input schema on apify.com (all work without login cookies).
# Only the listed output fields are returned: actor items are mostly CDN links and repeated author blobs.
_PLATFORMS: Dict[str, _Platform] = {
    "instagram": _Platform(
        profile_url="https://www.instagram.com/{handle}/",
        profile_actor="apify/instagram-profile-scraper",
        posts_actor="apify/instagram-post-scraper",
        profile_input=lambda target: {"usernames": [target.handle]},
        posts_input=lambda target: {"username": [target.handle], "resultsLimit": target.limit},
        profile_fields=(
            "username",
            "fullName",
            "biography",
            "url",
            "followersCount",
            "followsCount",
            "postsCount",
            "verified",
            "private",
            "isBusinessAccount",
            "businessCategoryName",
            "externalUrl",
        ),
        post_fields=(
            "url",
            "type",
            "caption",
            "hashtags",
            "mentions",
            "likesCount",
            "commentsCount",
            "videoViewCount",
            "timestamp",
        ),
    ),
    "facebook": _Platform(
        profile_url="https://www.facebook.com/{handle}/",
        profile_actor="apify/facebook-pages-scraper",
        posts_actor="apify/facebook-posts-scraper",
        profile_input=lambda target: {"startUrls": [{"url": target.url}]},
        posts_input=lambda target: {"startUrls": [{"url": target.url}], "resultsLimit": target.limit},
        profile_fields=(
            "title",
            "pageName",
            "pageUrl",
            "categories",
            "intro",
            "followers",
            "website",
            "websites",
            "email",
            "phone",
            "address",
            "rating",
            "creation_date",
        ),
        post_fields=("url", "time", "text", "likes", "comments", "shares", "viewsCount"),
    ),
    "linkedin": _Platform(
        profile_url="https://www.linkedin.com/in/{handle}/",
        profile_actor="harvestapi/linkedin-profile-scraper",
        posts_actor="harvestapi/linkedin-profile-posts",
        profile_input=lambda target: {"publicIdentifiers": [target.handle]},
        posts_input=lambda target: {"targetUrls": [target.url], "maxPosts": target.limit},
        profile_fields=(
            "firstName",
            "lastName",
            "headline",
            "about",
            "linkedinUrl",
            "location",
            "followerCount",
            "connectionsCount",
            "verified",
            "premium",
            "influencer",
            "websites",
            "currentPosition",
            "experience",
            "education",
            "skills",
        ),
        post_fields=("linkedinUrl", "type", "content", "postedAt", "engagement"),
    ),
    "x": _Platform(
        profile_url="https://x.com/{handle}",
        profile_actor="apidojo/twitter-user-scraper",
        posts_actor="apidojo/twitter-profile-scraper",
        profile_input=lambda target: {
            "twitterHandles": [target.handle],
            "getFollowers": False,
            "getFollowing": False,
            "maxItems": target.limit,
        },
        posts_input=lambda target: {"twitterHandles": [target.handle], "maxItems": target.limit},
        profile_fields=(
            "userName",
            "name",
            "url",
            "description",
            "location",
            "followers",
            "following",
            "statusesCount",
            "isVerified",
            "isBlueVerified",
            "protected",
            "createdAt",
        ),
        post_fields=(
            "url",
            "text",
            "createdAt",
            "lang",
            "likeCount",
            "retweetCount",
            "replyCount",
            "quoteCount",
            "viewCount",
            "bookmarkCount",
            "isReply",
            "isRetweet",
            "isQuote",
        ),
    ),
}


def _validate_platform(platform: str) -> str:
    key = (platform or "").strip().lower()
    if key not in _PLATFORMS:
        raise ValueError(f"Unsupported platform '{platform}'. Choose one of: {', '.join(_PLATFORMS)}")
    return key


def _validate_handle(handle: str) -> str:
    candidate = (handle or "").strip().lstrip("@")
    if not _HANDLE.match(candidate):
        raise ValueError(
            f"Invalid handle '{handle}': expected a username such as 'natgeo' (no URL, letters, digits, '.', '_', '-')."
        )
    return candidate


def _validate_posts_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_POSTS_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_POSTS_LIMIT}, got {limit}")
    return limit


def _require_token(apify_api_token: Optional[str]) -> str:
    if not apify_api_token:
        raise RuntimeError("Social platforms are not configured: APIFY_API_TOKEN is missing in the server environment.")
    return apify_api_token


def _apify_error_message(resp: requests.Response) -> str:
    """Apify errors are JSON `{"error": {"message": ...}}`; fall back to the raw body if not."""
    try:
        return str(resp.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return resp.text[:300]


def _run_actor(actor_id: str, actor_input: Dict[str, Any], apify_api_token: str) -> List[Dict[str, Any]]:
    try:
        resp = requests.post(
            APIFY_RUN_SYNC_URL.format(actor_id=actor_id.replace("/", "~")),
            json=actor_input,
            headers={"Authorization": f"Bearer {apify_api_token}"},
            params={"timeout": ACTOR_RUN_TIMEOUT_SECONDS, "maxTotalChargeUsd": MAX_CHARGE_PER_RUN_USD},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise unreachable_error("Apify", exc, HTTP_TIMEOUT_SECONDS) from exc
    if not resp.ok:
        logger.error("Apify actor run failed: actor=%s status=%s", actor_id, resp.status_code)
        hint = _APIFY_ERROR_HINTS.get(resp.status_code) or _apify_error_message(resp)
        raise RuntimeError(f"Apify scraper '{actor_id}' failed with HTTP {resp.status_code}: {hint}")
    try:
        items = resp.json()
    except ValueError:
        items = None
    if not isinstance(items, list):
        raise RuntimeError(f"Apify scraper '{actor_id}' returned an unexpected response; expected a list of items.")
    return items


def _public_items(items: List[Dict[str, Any]], platform: str, handle: str, kind: str) -> List[Dict[str, Any]]:
    """Drop Apify error items (e.g. `not_found`); raise when nothing public is left."""
    valid = [item for item in items if "error" not in item]
    if valid:
        return valid
    reasons = sorted({str(item.get("errorDescription") or item["error"]) for item in items})
    detail = f" ({'; '.join(reasons)})" if reasons else ""
    raise RuntimeError(
        f"No public {platform} {kind} found for '{handle}'{detail}. "
        "The account may not exist, may be private, or may have nothing public."
    )


def _without_images(value: Any) -> Any:
    """Drop image keys at any depth; they hold long CDN links an AI reader cannot use."""
    if isinstance(value, dict):
        return {key: _without_images(val) for key, val in value.items() if not _IMAGE_KEY.search(key)}
    if isinstance(value, list):
        return [_without_images(val) for val in value]
    return value


def _keep_fields(items: List[Dict[str, Any]], fields: Tuple[str, ...]) -> List[Dict[str, Any]]:
    return [{field: _without_images(item[field]) for field in fields if field in item} for item in items]


def _platform_result(
    platform: str, handle: str, profile_url: str, items: List[Dict[str, Any]], max_chars: int
) -> Dict[str, Any]:
    result = truncated_result(profile_url, json.dumps(items, ensure_ascii=False), max_chars)
    result.update({"platform": platform, "handle": handle, "count": len(items)})
    return result


def get_social_profile(
    platform: str,
    handle: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    apify_api_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a public Instagram, Facebook page, LinkedIn or X profile through its Apify scraper."""
    platform_key = _validate_platform(platform)
    username = _validate_handle(handle)
    limit = validate_max_chars(max_chars)
    token = _require_token(apify_api_token)

    spec = _PLATFORMS[platform_key]
    profile_url = spec.profile_url.format(handle=username)
    target = _ActorTarget(handle=username, url=profile_url, limit=1)
    items = _run_actor(spec.profile_actor, spec.profile_input(target), token)
    public_items = _public_items(items, platform_key, username, "profile")
    profile = _keep_fields(public_items[:1], spec.profile_fields)
    return _platform_result(platform_key, username, profile_url, profile, limit)


def get_social_posts(
    platform: str,
    handle: str,
    limit: int = DEFAULT_POSTS_LIMIT,
    max_chars: int = DEFAULT_MAX_CHARS,
    apify_api_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Return recent public posts of an Instagram, Facebook page, LinkedIn or X profile through Apify."""
    platform_key = _validate_platform(platform)
    username = _validate_handle(handle)
    posts_limit = _validate_posts_limit(limit)
    char_limit = validate_max_chars(max_chars)
    token = _require_token(apify_api_token)

    spec = _PLATFORMS[platform_key]
    profile_url = spec.profile_url.format(handle=username)
    target = _ActorTarget(handle=username, url=profile_url, limit=posts_limit)
    items = _run_actor(spec.posts_actor, spec.posts_input(target), token)
    public_items = _public_items(items, platform_key, username, "posts")
    posts = _keep_fields(public_items[:posts_limit], spec.post_fields)
    return _platform_result(platform_key, username, profile_url, posts, char_limit)
