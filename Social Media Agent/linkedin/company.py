"""
Reads LinkedIn company pages with the user's own logged-in session: the About page, then requested sections.

Section pages and layouts are ported from stickerdaniel/linkedin-mcp-server (linkedin/fields.py,
linkedin/company.py, Apache-2.0, see third_party/NOTICE).
"""

import re
from typing import Any, Dict, Sequence, Tuple
from urllib.parse import quote, urlsplit

import browser_session
from caller import Caller
from constants import LINKEDIN, LINKEDIN_COMPANY_PATH_PATTERN, LINKEDIN_ORIGIN
from errors import PageReadError
from linkedin.sections import Layout, SectionSpec, read_main_then_sections

# The About page ends after its overview and details; recruiting, commitments and locations follow.
ABOUT_PAGE_END = (
    re.compile(r"^Interested in working with us in the future\?$", re.MULTILINE),
    re.compile(r"^Commitments$", re.MULTILINE),
    re.compile(r"^Locations \(\d+\)$", re.MULTILINE),
)

# Section name -> (path after /company/<name>/, how the page loads)
SECTION_PAGES: Dict[str, Tuple[str, Layout]] = {
    "posts": ("posts/", Layout.ACTIVITY),
    "jobs": ("jobs/", Layout.STANDARD),
}


async def read_company(caller: Caller, company: str, sections: Sequence[str]) -> Dict[str, Any]:
    """Read a company's About page and the requested sections.

    `company` must already be a validated page name (e.g. 'microsoft'); `sections` names from SECTION_PAGES.
    """
    about_url = f"{LINKEDIN_ORIGIN}/company/{quote(company, safe='')}/about/"
    async with browser_session.user_page(caller, LINKEDIN) as page:
        return await read_main_then_sections(
            page,
            SectionSpec("about", about_url, Layout.STANDARD, end_markers=ABOUT_PAGE_END),
            lambda landed_url: _landed_company_url(landed_url, company),
            SECTION_PAGES,
            sections,
        )


def _landed_company_url(landed_url: str, company: str) -> str:
    """The company's own address after redirects (numeric ids redirect to the page name)."""
    match = LINKEDIN_COMPANY_PATH_PATTERN.match(urlsplit(landed_url).path)
    if not match:
        raise PageReadError(f"LinkedIn has no company page '{company}' (it showed {landed_url}). Check the name.")
    return f"{LINKEDIN_ORIGIN}/company/{match.group(1)}/"
