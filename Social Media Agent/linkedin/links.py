"""
Turns the links found in a LinkedIn section into short, typed references the AI can follow up on.

Ported from stickerdaniel/linkedin-mcp-server (linkedin/link_metadata.py, Apache-2.0, see third_party/NOTICE).
Changes: people, companies, schools and outside links whose label (or, unlabelled, address) is not in the
section's own text are dropped (LinkedIn puts "People also viewed" suggestions inside the same page area),
counts are not used as labels, and /posts/ links count as posts.
"""

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit

from constants import DEFAULT_REFERENCE_CAP, LINKEDIN_DOMAIN, REFERENCE_CAPS
from linkedin.page import normalize_whitespace

Reference = Dict[str, str]

# Links whose id is the useful part, so they are kept even without a readable label.
_KEPT_WITHOUT_LABEL = {"feed_post", "external", "job"}
# Kinds whose labelled links LinkedIn also shows outside the section's own text (suggestions, cut-off parts).
_MUST_APPEAR_IN_TEXT = {"person", "company", "school", "external"}
_MAX_REDIRECT_DEPTH = 5

_GENERIC_LABELS = {
    "show all", "follow", "following", "connect", "send", "like", "comment", "repost", "post",
    "play", "pause", "fullscreen", "close", "manage notifications", "view my newsletter", "my newsletter",
}
_CHROME_FIRST_SEGMENTS = {"help", "legal", "about", "accessibility", "mypreferences", "preferences"}
_PERSON_SUBPAGES = {"overlay", "details", "recent-activity"}

_SIMPLE_ROUTES = [
    (re.compile(r"^/company/([^/?#]+)"), "company", "/company/{}/"),
    (re.compile(r"^/school/([^/?#]+)"), "school", "/school/{}/"),
    # LinkedIn serves a job at /jobs/view/<id>/ and /jobs/view/<title>-<id>/; the id is the trailing number.
    (re.compile(r"^/jobs/view/(?:[^/?#]*-)?([0-9]+)(?=[/?#]|$)"), "job", "/jobs/view/{}/"),
    (re.compile(r"^/newsletters/([^/?#]+)"), "newsletter", "/newsletters/{}/"),
    (re.compile(r"^/pulse/([^/?#]+)"), "article", "/pulse/{}/"),
    (re.compile(r"^/feed/update/([^/?#]+)"), "feed_post", "/feed/update/{}/"),
    (re.compile(r"^/posts/([^/?#]+)"), "feed_post", "/posts/{}"),
]
_PERSON_PATH = re.compile(r"^/in/([^/?#]+)")
_LABEL_PREFIX = re.compile(r"^(?:View:\s*|View\b\s+|Open article:\s*)", re.IGNORECASE)
_GRAPHIC_LINK_SUFFIX = re.compile(r"(?:[’']s)?\s+graphic link$", re.IGNORECASE)
_DUPLICATE_HALVES = re.compile(r"^(?P<value>.+?)\s+(?P=value)$")
_URL_LIKE = re.compile(r"^(?:https?://|/)\S+$", re.IGNORECASE)
_CONNECTIONS_FOLLOW = re.compile(r"\bconnections follow this page\b", re.IGNORECASE)
# At least one letter or digit in any script (so non-Latin names are kept).
_HAS_CONTENT = re.compile(r"[^\W_]")
# Counts such as "261" (comments) are not labels.
_ONLY_NUMBERS = re.compile(r"^[\d.,\s]+$")


def build_references(anchors: List[Mapping[str, Any]], section: str, section_text: str) -> List[Reference]:
    """Return the section's useful links, de-duplicated, in page order, at most the section's cap."""
    visible_text = normalize_whitespace(section_text).lower()
    references = [ref for anchor in anchors if (ref := _reference(anchor, section, visible_text))]
    return _deduplicated(references)[: REFERENCE_CAPS.get(section, DEFAULT_REFERENCE_CAP)]


def _reference(anchor: Mapping[str, Any], section: str, visible_text: str) -> Optional[Reference]:
    if anchor.get("in_nav") or anchor.get("in_footer"):
        return None
    target = _target_url(str(anchor.get("href") or ""))
    classified = _classify(target) if target else None
    if classified is None:
        return None
    kind, url = classified
    label = _best_label(anchor, kind)
    if label is None and kind not in _KEPT_WITHOUT_LABEL:
        return None
    if label and kind in _MUST_APPEAR_IN_TEXT and label.lower() not in visible_text:
        return None
    if label is None and kind == "external" and _address(url) not in visible_text:
        return None
    reference = {"kind": kind, "url": url}
    if label:
        reference["text"] = label
    reference["context"] = section.replace("_", " ")
    return reference


def _target_url(href: str, depth: int = 0) -> Optional[str]:
    """Absolute http(s) link with LinkedIn's /redir/redirect/ wrapper removed; None for anything else."""
    href = href.strip()
    if not href or href.startswith("#") or depth > _MAX_REDIRECT_DEPTH:
        return None
    parts = urlsplit(href)
    if parts.scheme.lower() not in {"http", "https"}:
        return None
    if _is_linkedin_host(parts.netloc) and parts.path == "/redir/redirect/":
        wrapped = unquote((parse_qs(parts.query).get("url") or [""])[0])
        return _target_url(wrapped, depth + 1)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _classify(url: str) -> Optional[Tuple[str, str]]:
    parts = urlsplit(url)
    if not _is_linkedin_host(parts.netloc):
        return "external", urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))
    path = parts.path or "/"
    if _is_linkedin_chrome(path):
        return None
    if match := _PERSON_PATH.match(path):
        subpage = path[match.end() :].strip("/").split("/", 1)[0]
        return None if subpage in _PERSON_SUBPAGES else ("person", f"/in/{match.group(1)}/")
    for pattern, kind, template in _SIMPLE_ROUTES:
        if match := pattern.match(path):
            return kind, template.format(match.group(1))
    # Job cards inside a search link to the search with the job selected.
    job_id = (parse_qs(parts.query).get("currentJobId") or [""])[0]
    if path.rstrip("/") in {"/jobs/search", "/jobs/search-results"} and re.fullmatch(r"[0-9]+", job_id):
        return "job", f"/jobs/view/{job_id}/"
    return None


def _best_label(anchor: Mapping[str, Any], kind: str) -> Optional[str]:
    """The shortest clean label among the link text, aria-label and title; very short ones come last."""
    labels = [label for field in ("text", "aria_label", "title") if (label := _clean_label(str(anchor.get(field) or ""), kind))]
    if not labels:
        return None
    return min(labels, key=lambda label: (len(label) < 3, len(label)))


def _clean_label(value: str, kind: str) -> Optional[str]:
    value = _GRAPHIC_LINK_SUFFIX.sub("", _LABEL_PREFIX.sub("", normalize_whitespace(value))).strip(" :-")
    if " by " in value and kind in {"article", "external"}:
        value = value.split(" by ", 1)[0].strip()
    for separator in (" • ", " · ", " | "):
        value = value.split(separator, 1)[0].strip()
    if duplicate := _DUPLICATE_HALVES.match(value):
        value = duplicate.group("value").strip()
    if (
        _URL_LIKE.match(value)
        or _CONNECTIONS_FOLLOW.search(value)
        or value.lower() in _GENERIC_LABELS
        or not 2 <= len(value) <= 80
        or not _HAS_CONTENT.search(value)
        or _ONLY_NUMBERS.match(value)
    ):
        return None
    return value


def _deduplicated(references: List[Reference]) -> List[Reference]:
    """One reference per URL, at the position it first appeared, keeping the one with the richer label."""
    by_url: Dict[str, Reference] = {}
    for reference in references:
        existing = by_url.get(reference["url"])
        if existing is None or _richness(reference) > _richness(existing):
            by_url[reference["url"]] = reference
    return list(by_url.values())


def _richness(reference: Reference) -> Tuple[int, int]:
    return (1 if "text" in reference else 0, len(reference.get("text", "")))


def _is_linkedin_chrome(path: str) -> bool:
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return False
    first, second = segments[0], segments[1] if len(segments) > 1 else ""
    return (
        first in _CHROME_FIRST_SEGMENTS
        or (first == "search" and second == "results")
        or (first == "overlay" and second in {"background-photo", "browsemap-recommendations"})
        or (first == "preload" and second == "custom-invite")
    )


def _address(url: str) -> str:
    """A link as it is usually written in page text: lowercase, without scheme or trailing slash."""
    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path}".rstrip("/").lower()


def _is_linkedin_host(host: str) -> bool:
    host = host.lower().split(":", 1)[0]
    return host == LINKEDIN_DOMAIN or host.endswith("." + LINKEDIN_DOMAIN)
