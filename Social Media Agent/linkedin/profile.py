"""
Reads LinkedIn profiles with the user's own logged-in session: the main page, then each requested section's page.

Section pages and layouts are ported from stickerdaniel/linkedin-mcp-server (linkedin/fields.py,
linkedin/person.py, Apache-2.0, see third_party/NOTICE).
"""

import re
from typing import Any, Dict, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import browser_session
from constants import LINKEDIN, LINKEDIN_ORIGIN, LINKEDIN_PROFILE_PATH_PATTERN
from errors import PageReadError
from linkedin.sections import Layout, SectionSpec, read_main_then_sections

OWN_PROFILE_URL = f"{LINKEDIN_ORIGIN}/in/me/"

# The main page ends where its activity feed starts; those posts come from the "posts" section instead.
MAIN_PAGE_END = (re.compile(r"^Activity\n+[\d,.]+[KM]? followers?$", re.MULTILINE),)

# Section name -> (path after /in/<handle>/, how the page loads)
SECTION_PAGES: Dict[str, Tuple[str, Layout]] = {
    "experience": ("details/experience/", Layout.DETAILS),
    "education": ("details/education/", Layout.DETAILS),
    "skills": ("details/skills/", Layout.DETAILS),
    "projects": ("details/projects/", Layout.DETAILS),
    "certifications": ("details/certifications/", Layout.DETAILS),
    "languages": ("details/languages/", Layout.DETAILS),
    "honors": ("details/honors/", Layout.DETAILS),
    "volunteering": ("details/volunteering-experiences/", Layout.DETAILS),
    "interests": ("details/interests/", Layout.DETAILS),
    "contact_info": ("overlay/contact-info/", Layout.OVERLAY),
    "posts": ("recent-activity/all/", Layout.ACTIVITY),
}


async def read_profile(user_id: str, profile_url: Optional[str], sections: Sequence[str]) -> Dict[str, Any]:
    """Read a profile's main page and the requested sections; with no URL, the user's own profile.

    `sections` must already be validated names from SECTION_PAGES.
    """
    requested_url = profile_url or OWN_PROFILE_URL
    async with browser_session.user_page(user_id, LINKEDIN) as page:
        return await read_main_then_sections(
            page,
            SectionSpec("main_profile", requested_url, Layout.STANDARD, end_markers=MAIN_PAGE_END),
            lambda landed_url: _landed_profile_url(landed_url, requested_url),
            SECTION_PAGES,
            sections,
        )


def _landed_profile_url(landed_url: str, requested_url: str) -> str:
    """The profile's own address after redirects; LinkedIn sends unknown profiles to /404/."""
    match = LINKEDIN_PROFILE_PATH_PATTERN.match(urlsplit(landed_url).path)
    if not match:
        raise PageReadError(f"LinkedIn has no profile at {requested_url} (it showed {landed_url}). Check the link.")
    return f"{LINKEDIN_ORIGIN}/in/{match.group(1)}/"
