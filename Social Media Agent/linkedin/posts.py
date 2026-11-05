"""
Searches LinkedIn posts with the user's own logged-in session (LinkedIn's "Posts" search tab).

Search URL and filters are ported from stickerdaniel/linkedin-mcp-server (linkedin/posts.py,
linkedin/search_urls.py, Apache-2.0, see third_party/NOTICE). Post links come from the page's own
anchors; the upstream response listener that adds more post links is not ported.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import browser_session
from caller import Caller
from constants import LINKEDIN, LINKEDIN_ORIGIN, POST_CONTENT_TYPES, SEARCH_SCROLLS_PER_PAGE
from linkedin import sections
from linkedin.sections import Layout, SectionSpec


async def search_posts(
    caller: Caller, keywords: str, date_posted: Optional[str], content_type: Optional[str], pages: int
) -> Dict[str, Any]:
    """Return the text of the post search results; the AI reads authors, posts and counts from it.

    Arguments must already be validated: `date_posted` from POST_DATE_FILTERS, `content_type` from POST_CONTENT_TYPES.
    """
    url = search_url(keywords, date_posted, content_type)
    spec = SectionSpec("search_results", url, Layout.SEARCH, max_loads=pages * SEARCH_SCROLLS_PER_PAGE)
    async with browser_session.user_page(caller, LINKEDIN) as page:
        results = await sections.read_sections(page, [spec])
    return sections.section_result(url, results)


def search_url(keywords: str, date_posted: Optional[str], content_type: Optional[str]) -> str:
    """LinkedIn's own post search address; filters are one-item JSON lists, in the order LinkedIn writes them."""
    params: List[Tuple[str, str]] = [("keywords", keywords), ("origin", "FACETED_SEARCH")]
    if date_posted:
        params.append(("datePosted", json.dumps([date_posted])))
    if content_type:
        params.append(("contentType", json.dumps([POST_CONTENT_TYPES[content_type]])))
    return f"{LINKEDIN_ORIGIN}/search/results/content/?{urlencode(params)}"
