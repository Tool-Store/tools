"""
Reads LinkedIn section pages: opens a page, waits for it, loads all of it and returns its text and links.

Each part of a profile or company has its own page (/details/experience/, /about/, /posts/...). Reading
that page's text keeps working when LinkedIn changes its layout, and the AI reads the text itself.

The text is cleaned of LinkedIn page clutter (footer, sidebar suggestions, upsells, player controls);
lines are matched whole, so the same words inside real post or profile text are kept.

Ported from stickerdaniel/linkedin-mcp-server (linkedin/capture.py, linkedin/content.py, linkedin/text.py,
core/utils.py, Apache-2.0, see third_party/NOTICE). Changes: runs on our per-user SitePage, uses OpenCLI's
scroll script, and also removes LinkedIn upsell lines seen on live pages.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Pattern, Sequence, Tuple

from browser_session import BrowserError, SitePage
from constants import (
    ACTIVITY_SCROLL_DELAY_MS,
    ACTIVITY_SCROLLS,
    DETAIL_SHOW_MORE_CLICKS,
    RATE_LIMIT_RETRY_SECONDS,
    SECTION_PAUSE_SECONDS,
    SECTION_WAIT_MS,
    STANDARD_SCROLL_DELAY_MS,
    STANDARD_SCROLLS,
)
from linkedin.links import Reference, build_references
from linkedin.page import require_login

log = logging.getLogger(__name__)

RATE_LIMITED = "LinkedIn returned only page chrome twice; the account is probably rate-limited. Retry in about an hour."
SKIPPED_AFTER_RATE_LIMIT = "Not read: an earlier section was rate-limited."
OVERLAY_NOT_OPEN = "The popup did not open, so nothing was read (the page behind it is never returned)."

_MAIN_ROOT = ["main"]
_OVERLAY_ROOTS = ["dialog[open]", ".artdeco-modal__content"]
_POPUP_CLOSE = 'button[aria-label="Dismiss"], button[aria-label="Close"], button.artdeco-modal__dismiss'
_SHOW_MORE = re.compile(r"^Show (more|all)\b", re.IGNORECASE)
_MAIN_PRESENT = "() => document.querySelector('main') !== null"
_OVERLAY_PRESENT = f"() => document.querySelector({', '.join(_OVERLAY_ROOTS)!r}) !== null"
# Detail pages first render a "Load more" placeholder or the sidebar before the list itself.
_DETAILS_READY = (
    "() => { const main = document.querySelector('main'); if (!main) return false;"
    " const text = main.innerText.trimStart();"
    " return !['Load more', 'More profiles for you', 'Explore premium profiles'].some(p => text.startsWith(p)); }"
)

# Everything from the earliest of these markers onwards is page chrome, not the section's content.
_CHROME_STARTS = [
    re.compile(r"^About\n+(?:Accessibility|Talent Solutions)", re.MULTILINE),
    re.compile(r"^More profiles for you$", re.MULTILINE),
    re.compile(r"^Explore premium profiles$", re.MULTILINE),
    re.compile(r"^Get up to .+ replies when you message with InMail$", re.MULTILINE),
    re.compile(
        r"^(?:Careers|Privacy & Terms|Questions\?|Select language)\n+"
        r"(?:Privacy & Terms|Questions\?|Select language|Advertising|Ad Choices|[A-Za-z]+ \([A-Za-z]+\))",
        re.MULTILINE,
    ),
    re.compile(r"^Are these results helpful\?$", re.MULTILINE),
]

_CLUTTER_LINES = [
    re.compile(r"^(?:Play|Pause|Playback speed|Turn fullscreen on|Fullscreen)$"),
    re.compile(r"^(?:Show captions|Close modal window|Media player modal window)$"),
    re.compile(r"^(?:Loaded:.*|Remaining time.*|Stream Type.*)$"),
    re.compile(r"^(?:Try|Activate) (?:Premium|Sales Navigator) for .+$"),
    re.compile(r"^\d+-month free trial .+$"),
    re.compile(r"^(?:Profile enhanced with Premium|Sales Insights|Key signals|Access exclusive tools & insights)$"),
    re.compile(r"^.+ posted in the past \d+ days$"),
    re.compile(r"^Do you find this post valuable\?$"),
]

# Suggestion boxes in the middle of a page: removed from their heading up to the next section heading.
_CLUTTER_BLOCKS = [
    re.compile(
        r"^People who follow .+ also follow$.*?(?=^(?:About|Featured|Activity|Experience|Education|Skills)$|\Z)",
        re.MULTILINE | re.DOTALL,
    ),
]

_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


class Layout(Enum):
    """How a section page loads its content, which decides how it is waited for and expanded."""

    STANDARD = "standard"
    DETAILS = "details"  # /details/<section>/ lists with "Show more" buttons
    ACTIVITY = "activity"  # post lists that load more while scrolling
    SEARCH = "search"  # search results that load more while scrolling
    OVERLAY = "overlay"  # a popup over the page, e.g. contact info


_MIN_TEXT_CHARS = {Layout.ACTIVITY: 200, Layout.SEARCH: 100}


@dataclass(frozen=True)
class SectionSpec:
    name: str
    url: str
    layout: Layout
    # "Show more" clicks for detail pages, scrolls for the others; None uses the layout's default.
    max_loads: Optional[int] = None
    # Where this section's own content ends on its page, e.g. the activity feed under a profile's main part.
    end_markers: Tuple[Pattern[str], ...] = ()


@dataclass(frozen=True)
class SectionText:
    text: str
    references: List[Reference] = field(default_factory=list)
    error: Optional[str] = None


async def read_section(page: SitePage, spec: SectionSpec) -> SectionText:
    """Read one section; a page showing only chrome is retried once, then reported as rate-limited."""
    section = await _read_once(page, spec)
    if section.error != RATE_LIMITED:
        return section
    log.info("Retrying %s after %ss: only page chrome came back", spec.url, RATE_LIMIT_RETRY_SECONDS)
    await asyncio.sleep(RATE_LIMIT_RETRY_SECONDS)
    return await _read_once(page, spec)


async def read_sections(
    page: SitePage, specs: Sequence[SectionSpec], after_other_page: bool = False
) -> Dict[str, SectionText]:
    """Read sections in order, pausing between page loads (also before the first when `after_other_page`).

    A failing section gets its error and the rest still run; after a rate-limited section the rest are skipped.
    """
    results: Dict[str, SectionText] = {}
    for index, spec in enumerate(specs):
        if any(section.error == RATE_LIMITED for section in results.values()):
            results.update(_skipped_after_rate_limit(specs[index:]))
            break
        if index or after_other_page:
            await asyncio.sleep(SECTION_PAUSE_SECONDS)
        results[spec.name] = await _read_safely(page, spec)
    return results


async def read_main_then_sections(
    page: SitePage,
    main: SectionSpec,
    base_url_of: Callable[[str], str],
    section_pages: Mapping[str, Tuple[str, Layout]],
    names: Sequence[str],
) -> Dict[str, Any]:
    """Read a main page, then the named sections under it, and return the answer.

    `base_url_of` turns the address the main page landed on into the base for the section paths
    (it raises when LinkedIn redirected somewhere else, so no more pages are loaded).
    `section_pages` maps a section name to (path under the base, layout).
    """
    first = await read_section(page, main)
    base_url = base_url_of(page.url)
    specs = [SectionSpec(name, base_url + section_pages[name][0], section_pages[name][1]) for name in names]
    if first.error == RATE_LIMITED:
        rest = _skipped_after_rate_limit(specs)
    else:
        rest = await read_sections(page, specs, after_other_page=True)
    return section_result(base_url, {main.name: first, **rest})


def _skipped_after_rate_limit(specs: Sequence[SectionSpec]) -> Dict[str, SectionText]:
    return {spec.name: SectionText("", error=SKIPPED_AFTER_RATE_LIMIT) for spec in specs}


def section_result(url: str, results: Dict[str, SectionText]) -> Dict[str, Any]:
    """The answer shape for section reads: url, sections (name -> text), and links and errors when there are any."""
    answer: Dict[str, Any] = {"url": url, "sections": {name: section.text for name, section in results.items() if section.text}}
    references = {name: section.references for name, section in results.items() if section.references}
    errors = {name: section.error for name, section in results.items() if section.error}
    if references:
        answer["references"] = references
    if errors:
        answer["section_errors"] = errors
    return answer


async def _read_safely(page: SitePage, spec: SectionSpec) -> SectionText:
    try:
        return await read_section(page, spec)
    except BrowserError as error:
        log.warning("Reading %s failed: %s", spec.url, error)
        return SectionText("", error=f"The page could not be read: {error}")


async def _read_once(page: SitePage, spec: SectionSpec) -> SectionText:
    await page.goto(spec.url)
    await require_login(page)
    if spec.layout is Layout.OVERLAY:
        return await _read_overlay(page, spec)
    await page.wait_until(_MAIN_PRESENT, SECTION_WAIT_MS)
    await page.click_first(_POPUP_CLOSE)
    await _wait_for_content(page, spec.layout)
    if spec.layout is Layout.DETAILS:
        await _click_show_more(page, spec.max_loads or DETAIL_SHOW_MORE_CLICKS)
    await page.auto_scroll(*_scrolling(spec))
    content = await page.run_script("linkedin_section_content", {"selectors": _MAIN_ROOT})
    return _section_text(content, spec)


async def _read_overlay(page: SitePage, spec: SectionSpec) -> SectionText:
    await page.wait_until(_OVERLAY_PRESENT, SECTION_WAIT_MS)
    content = await page.run_script("linkedin_section_content", {"selectors": _OVERLAY_ROOTS})
    if content.get("source") != "root":
        return SectionText("", error=OVERLAY_NOT_OPEN)
    return _section_text(content, spec)


async def _wait_for_content(page: SitePage, layout: Layout) -> None:
    if layout is Layout.DETAILS:
        await page.wait_until(_DETAILS_READY, SECTION_WAIT_MS)
    elif layout in _MIN_TEXT_CHARS:
        condition = f"() => (document.querySelector('main')?.innerText.length || 0) > {_MIN_TEXT_CHARS[layout]}"
        await page.wait_until(condition, SECTION_WAIT_MS)


async def _click_show_more(page: SitePage, max_clicks: int) -> None:
    for _ in range(max_clicks):
        if not await page.click_first("main button", _SHOW_MORE):
            return
        await asyncio.sleep(1.0)


def _scrolling(spec: SectionSpec) -> Tuple[int, int]:
    if spec.layout is Layout.ACTIVITY:
        return spec.max_loads or ACTIVITY_SCROLLS, ACTIVITY_SCROLL_DELAY_MS
    if spec.layout is Layout.SEARCH:
        return spec.max_loads or STANDARD_SCROLLS, STANDARD_SCROLL_DELAY_MS
    return STANDARD_SCROLLS, STANDARD_SCROLL_DELAY_MS


def _section_text(content: Dict[str, Any], spec: SectionSpec) -> SectionText:
    raw = str(content.get("text") or "")
    if not raw.strip():
        return SectionText("")
    text = strip_clutter(raw)
    if not text:
        return SectionText("", error=RATE_LIMITED)
    # Cut after the rate-limit check: a section's own end marker is not a sign of rate limiting.
    text = _cut_at_first(text, spec.end_markers)
    return SectionText(text, build_references(content.get("references") or [], spec.name, text))


def strip_clutter(text: str) -> str:
    content = _cut_at_first(text, _CHROME_STARTS)
    for block in _CLUTTER_BLOCKS:
        content = block.sub("", content)
    kept = [line for line in content.splitlines() if not any(pattern.match(line.strip()) for pattern in _CLUTTER_LINES)]
    return _EXTRA_BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()


def _cut_at_first(text: str, markers: Sequence[Pattern[str]]) -> str:
    starts = [match.start() for pattern in markers if (match := pattern.search(text))]
    return text[: min(starts, default=len(text))].strip()
