"""
Checks what the AI asked for before any command runs.

For example: is the site supported, is the username valid, is the limit in range.
Bad input is rejected here, so it never reaches the user's browser session.
"""

import os
from typing import List, Optional, Sequence
from urllib.parse import urlsplit

from constants import (
    COMPANY_NAME_PATTERN,
    LINKEDIN_COMPANY_PATH_PATTERN,
    LINKEDIN_DOMAIN,
    LINKEDIN_JOB_PATH_PATTERN,
    LINKEDIN_ORIGIN,
    LINKEDIN_PROFILE_PATH_PATTERN,
    MAX_QUERY_CHARS,
    MAX_RESULT_LIMIT,
    MAX_SEARCH_PAGES,
    TWEET_ID_PATTERN,
    TWEET_PATH_PATTERN,
    USERNAME_PATTERN,
    X_DOMAINS,
    X_HANDLE_PATTERN,
)


def validate_site(site: str, supported_sites: Sequence[str]) -> str:
    key = (site or "").strip().lower()
    if key not in supported_sites:
        raise ValueError(f"Unsupported site '{site}'. Choose one of: {', '.join(supported_sites)}")
    return key


def validate_query(query: str) -> str:
    return _clean_text(query, "query", "python developer")


def validate_location(location: str) -> str:
    return _clean_text(location, "location", "Ahmedabad")


def validate_username(username: str) -> str:
    candidate = (username or "").strip().lstrip("@")
    if not USERNAME_PATTERN.match(candidate):
        raise ValueError(
            f"Invalid username '{username}': expected a username such as 'natgeo' "
            "(no URL; letters, digits, '.', '_', '-')."
        )
    return candidate


def validate_x_handle(username: str) -> str:
    candidate = (username or "").strip().lstrip("@")
    if not X_HANDLE_PATTERN.match(candidate):
        raise ValueError(
            f"Invalid X username '{username}': expected a handle such as 'NASA' "
            "(no URL; 1-15 letters, digits or '_')."
        )
    return candidate


def validate_limit(limit: int, maximum: int = MAX_RESULT_LIMIT) -> int:
    if not 1 <= limit <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}, got {limit}")
    return limit


def validate_linkedin_job_url(url: str) -> str:
    candidate = (url or "").strip()
    parts = urlsplit(candidate)
    if not (
        parts.scheme == "https"
        and _host_matches(parts.hostname, (LINKEDIN_DOMAIN,))
        and LINKEDIN_JOB_PATH_PATTERN.match(parts.path)
    ):
        raise ValueError(
            f"Invalid LinkedIn job URL '{url}': expected a link such as https://www.linkedin.com/jobs/view/1234567890"
        )
    return candidate


def validate_linkedin_profile_url(url: str) -> str:
    """Return the profile link on www.linkedin.com, e.g. https://www.linkedin.com/in/jane-doe/."""
    parts = urlsplit((url or "").strip())
    match = LINKEDIN_PROFILE_PATH_PATTERN.match(parts.path)
    if not (
        parts.scheme == "https"
        and _host_matches(parts.hostname, (LINKEDIN_DOMAIN,))
        and not (parts.username or parts.password or parts.port)
        and match
    ):
        raise ValueError(
            f"Invalid LinkedIn profile URL '{url}': expected a link such as https://www.linkedin.com/in/jane-doe/"
        )
    return f"{LINKEDIN_ORIGIN}/in/{match.group(1)}/"


def validate_company(company: str) -> str:
    """Return a company's page name from the name itself or its link, e.g. 'microsoft'."""
    candidate = (company or "").strip()
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        match = LINKEDIN_COMPANY_PATH_PATTERN.match(parts.path)
        valid_link = parts.scheme == "https" and _host_matches(parts.hostname, (LINKEDIN_DOMAIN,)) and match
        candidate = match.group(1) if valid_link else ""
    if not COMPANY_NAME_PATTERN.match(candidate):
        raise ValueError(
            f"Invalid LinkedIn company '{company}': expected its page name such as 'microsoft' "
            "or a link such as https://www.linkedin.com/company/microsoft/"
        )
    return candidate


def validate_choices(values: Optional[Sequence[str]], allowed: Sequence[str], field: str, max_count: int) -> List[str]:
    """Clean a list of names that must come from `allowed`; duplicates are dropped, order is kept."""
    chosen = list(dict.fromkeys((value or "").strip().lower() for value in values or []))
    unknown = [value for value in chosen if value not in allowed]
    if unknown:
        raise ValueError(f"Unknown {field} '{', '.join(unknown)}'. Choose from: {', '.join(allowed)}")
    if len(chosen) > max_count:
        raise ValueError(f"At most {max_count} {field} per call, got {len(chosen)}. Split the request.")
    return chosen


def validate_choice(value: Optional[str], allowed: Sequence[str], field: str) -> Optional[str]:
    if value is None:
        return None
    [chosen] = validate_choices([value], allowed, field, 1)
    return chosen


def validate_pages(pages: int) -> int:
    if not 1 <= pages <= MAX_SEARCH_PAGES:
        raise ValueError(f"pages must be between 1 and {MAX_SEARCH_PAGES}, got {pages}")
    return pages


def validate_tweet(tweet: str) -> str:
    """Return the tweet id, from the id itself or the tweet's link."""
    candidate = (tweet or "").strip()
    if TWEET_ID_PATTERN.match(candidate):
        return candidate
    parts = urlsplit(candidate)
    match = TWEET_PATH_PATTERN.match(parts.path)
    if parts.scheme == "https" and _host_matches(parts.hostname, X_DOMAINS) and match:
        return match.group(1)
    raise ValueError(
        f"Invalid tweet '{tweet}': expected a tweet id such as '1234567890' "
        "or a link such as https://x.com/user/status/1234567890"
    )


def positive_int_setting(name: str, default: int) -> int:
    """Read a whole-number setting of at least 1 from the environment."""
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"{name} must be a whole number of at least 1, got '{raw}'")
    return value


def _clean_text(value: str, field: str, example: str) -> str:
    text = " ".join((value or "").split())
    if not text:
        raise ValueError(f"{field} is required, e.g. '{example}'")
    if len(text) > MAX_QUERY_CHARS:
        raise ValueError(f"{field} must be at most {MAX_QUERY_CHARS} characters, got {len(text)}")
    # A leading '-' would be read as a command option instead of text.
    if text.startswith("-"):
        raise ValueError(f"{field} must not start with '-': '{value}'")
    return text


def _host_matches(host: str | None, domains: Sequence[str]) -> bool:
    host = (host or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in domains)
