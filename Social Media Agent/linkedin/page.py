"""
LinkedIn checks and text clean-up shared by every LinkedIn action.

Ported from OpenCLI's clis/linkedin/shared.js (Apache-2.0, see third_party/NOTICE).
"""

import re
from typing import Any

from browser_session import SitePage
from constants import LINKEDIN
from errors import NotLoggedInError, login_needed_message

_ODD_SPACES = re.compile(r"[  ]+")
_WHITESPACE = re.compile(r"\s+")


async def require_login(page: SitePage) -> None:
    """Raise NotLoggedInError when LinkedIn shows its login wall instead of the page."""
    if await page.run_script("linkedin_auth_probe"):
        raise NotLoggedInError(
            login_needed_message(LINKEDIN, "LinkedIn showed its login page, so the saved session has expired. Not logged in to")
        )


def normalize_whitespace(value: Any) -> str:
    text = "" if value is None else str(value)
    return _WHITESPACE.sub(" ", _ODD_SPACES.sub(" ", text)).strip()

