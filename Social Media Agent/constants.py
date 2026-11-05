"""
All fixed values in one place, grouped by topic: sites, limits, settings, timings and input patterns.

Change a number here instead of hunting for it in the code. Names ending in _ENV are environment
setting names; their DEFAULT_ value sits next to them.
"""

import re

# ── Sites ───────────────────────────────────────────────────────────────────────────────────
LINKEDIN = "linkedin"
INSTAGRAM = "instagram"
FACEBOOK = "facebook"
X = "x"
LINKEDIN_DOMAIN = "linkedin.com"
LINKEDIN_ORIGIN = "https://www.linkedin.com"
X_DOMAINS = ("x.com", "twitter.com")

# Which sites each MCP function supports
LOGIN_SITES = (LINKEDIN, INSTAGRAM, FACEBOOK, X)
# Sites still read through Agent Reach (search_social, get_social_profile, get_social_posts)
SEARCH_SITES = (FACEBOOK, X)
PROFILE_SITES = (FACEBOOK, X)
POSTS_SITES = (X,)

# ── Request limits ──────────────────────────────────────────────────────────────────────────
DEFAULT_RESULT_LIMIT = 5
MAX_RESULT_LIMIT = 20
MAX_QUERY_CHARS = 200
MAX_RESPONSE_CHARS = 20_000
# Sections shorter than this are never cut further to fit the response.
MIN_CUT_SECTION_CHARS = 200
DAILY_REQUEST_LIMIT_ENV = "DAILY_REQUEST_LIMIT"
DEFAULT_DAILY_REQUEST_LIMIT = 50
# Instagram flags automated use faster than other sites, so it has its own, lower limit.
INSTAGRAM_DAILY_REQUEST_LIMIT_ENV = "INSTAGRAM_DAILY_REQUEST_LIMIT"
DEFAULT_INSTAGRAM_DAILY_REQUEST_LIMIT = 20

# ── Caller identity (headers added by the Toolstore Tool Router) ────────────────────────────
JWT_HEADER = "X-Toolstore-JWT"
AUTHORIZATION_HEADER = "Authorization"
USER_ID_HEADER = "X-Toolstore-User-Id"
# Toolstore's signed proof that a call came through it; passed on to the Dev API unchanged.
INTERNAL_TOKEN_HEADER = "X-Internal-Token"
JWT_USER_ID_CLAIMS = ("user_id", "sub", "uid")
# Names the user when the server runs locally without Toolstore in front of it. Not TOOLSTORE_USER_ID:
# Toolstore sets that to the developer's own id at publish time.
LOCAL_USER_ID_ENV = "SOCIAL_AGENT_LOCAL_USER_ID"

# ── Logins ──────────────────────────────────────────────────────────────────────────────────
# Sites already moved from Agent Reach to our own browser sessions: (login page, cookie set once logged in).
BROWSER_LOGIN_PAGES = {
    LINKEDIN: ("https://www.linkedin.com/login", "li_at"),
    INSTAGRAM: ("https://www.instagram.com/accounts/login/", "sessionid"),
}
LOGIN_WINDOW_SECONDS = 600
LOGIN_POLL_SECONDS = 2
LOGIN_ENCRYPTION_KEY_ENV = "LOGIN_ENCRYPTION_KEY"
VIEWER_URL_ENV = "VIEWER_URL"
DEFAULT_VIEWER_URL = "http://localhost:6080/vnc.html"

# ── Per-user records (saved logins, daily usage) ────────────────────────────────────────────
# Set by Toolstore when it publishes the tool; with all three, records live in the user's Toolstore data.
TOOLSTORE_API_BASE_ENV = "TOOLSTORE_API_BASE"
TOOLSTORE_DEV_SLUG_ENV = "TOOLSTORE_DEV_SLUG"
TOOLSTORE_TOOL_SLUG_ENV = "TOOLSTORE_TOOL_SLUG"
# This tool's own sub-collection, so Toolstore's activation secrets and OAuth data are never touched.
USER_RECORDS_SUB_COLLECTION = "social_media_agent"
TOOLSTORE_REQUEST_TIMEOUT_SECONDS = 20
# Without Toolstore: one JSON file per record; kept inside ~/.agent-reach because that folder is the persisted volume.
USER_DATA_DIR_ENV = "USER_DATA_DIR"
DEFAULT_USER_DATA_DIR = "~/.agent-reach/user-data"

# ── Browser sessions (Patchright) ───────────────────────────────────────────────────────────
BROWSER_LOCALE = "en-US"
# The full Chromium build for both the visible login window and the hidden reading browser. Its headless mode
# reports normal client hints (the stripped-down headless shell says "HeadlessChrome", which sites treat as a bot).
BROWSER_CHANNEL = "chromium"
NAVIGATION_TIMEOUT_MS = 30_000
# Playwright's message when a page script is cut off because the page moved on (a redirect).
NAVIGATED_AWAY = "Execution context was destroyed"
# A page script is run again on the new page, for redirect chains up to this many runs in all.
PAGE_SCRIPT_ATTEMPTS = 3
# After a page loads, wait up to this long for it to stop changing (OpenCLI's default).
PAGE_SETTLE_MS = 1_000
DOM_QUIET_MS = 500
# Same headroom as Agent Reach's slowest actions, so MCP clients need one timeout for both.
BROWSER_ACTION_TIMEOUT_SECONDS = 150
# Each extra page a call loads (a profile section, a search page) gets this much more time.
SECONDS_PER_EXTRA_PAGE_LOAD = 40
MAX_BROWSER_SESSIONS_ENV = "MAX_BROWSER_SESSIONS"
# Each open session costs roughly 150-300 MB, so parallel requests wait for a free slot.
DEFAULT_MAX_BROWSER_SESSIONS = 3

# ── LinkedIn page reading (section pages) ───────────────────────────────────────────────────
# Most links kept per section; search results and the feed list more items than a profile section.
DEFAULT_REFERENCE_CAP = 12
REFERENCE_CAPS = {"search_results": 15, "feed": 50}
# How long to wait for a section's content to appear; a timeout still reads what is there.
SECTION_WAIT_MS = 10_000
# Pause between section pages, so LinkedIn sees a person-like pace.
SECTION_PAUSE_SECONDS = 2.0
# A section that shows only page chrome is usually rate-limited; it is retried once after this pause.
RATE_LIMIT_RETRY_SECONDS = 5.0
LINKEDIN_PROFILE_SECTIONS = (
    "experience", "education", "skills", "projects", "certifications", "languages",
    "honors", "volunteering", "interests", "contact_info", "posts",
)
LINKEDIN_COMPANY_SECTIONS = ("posts", "jobs")
# Each extra section is one more page load; the cap keeps one call from loading many pages.
MAX_EXTRA_SECTIONS = 5
# Post search loads more results while scrolling; one "page" is this many scrolls.
SEARCH_SCROLLS_PER_PAGE = 5
MAX_SEARCH_PAGES = 3
# LinkedIn's own tokens for the post search filters (any other value is silently ignored by LinkedIn).
POST_DATE_FILTERS = ("past-24h", "past-week", "past-month")
# Filter name offered to the AI -> LinkedIn's token
POST_CONTENT_TYPES = {
    "videos": "videos",
    "images": "photos",
    "job_posts": "jobs",
    "live_videos": "liveVideos",
    "documents": "documents",
}
DETAIL_SHOW_MORE_CLICKS = 5
STANDARD_SCROLLS = 5
STANDARD_SCROLL_DELAY_MS = 500
ACTIVITY_SCROLLS = 10
ACTIVITY_SCROLL_DELAY_MS = 1_000

# ── Instagram reads ─────────────────────────────────────────────────────────────────────────
INSTAGRAM_ORIGIN = "https://www.instagram.com"
# Where Instagram sends a session it does not accept.
INSTAGRAM_LOGIN_WALL_PATHS = ("/accounts/login", "/challenge", "/accounts/suspended")
# Instagram requests each read makes, counted toward the daily limit: one page view, nothing else.
INSTAGRAM_READ_COSTS = {"profile": 1, "posts": 1}
# A profile page carries its first 12 posts; more would need scrolling, which is more activity on the account.
INSTAGRAM_MAX_POSTS = 12

# ── Agent Reach commands (Instagram, Facebook, X and LinkedIn jobs until they are ported) ───
AGENT_REACH_BINARY = "agent-reach"
# Agent Reach allows its slowest browser actions 120s; leave headroom for start-up.
COMMAND_TIMEOUT_SECONDS = 150
MAX_COMMAND_OUTPUT_CHARS = 200_000

# ── MCP server ──────────────────────────────────────────────────────────────────────────────
# Host names the MCP server answers to (DNS-rebinding protection), comma-separated; "host:*" allows any port.
# On Toolstore set it to the tool's cluster host, or "*" to turn the check off: the MCP port is then reachable
# only inside the cluster, never from a browser. The library does not turn the check on by itself on 0.0.0.0.
MCP_ALLOWED_HOSTS_ENV = "MCP_ALLOWED_HOSTS"
DEFAULT_MCP_ALLOWED_HOSTS = "127.0.0.1:*,localhost:*"
ANY_HOST = "*"
MCP_ALLOWED_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*"]

# ── Input patterns ──────────────────────────────────────────────────────────────────────────
# No leading '-', so a username can never be read as a command option.
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._-]{0,99}$")
TWEET_ID_PATTERN = re.compile(r"^[0-9]{1,25}$")
TWEET_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_]{1,15}/status/[0-9]{1,25}/?$")
LINKEDIN_JOB_PATH_PATTERN = re.compile(r"^/jobs/view/(?:[^/]+-)?[0-9]+/?$")
LINKEDIN_PROFILE_PATH_PATTERN = re.compile(r"^/in/([^/]{1,100})/?$")
# A company page and any page under it, e.g. /company/microsoft/ or /company/microsoft/about/
LINKEDIN_COMPANY_PATH_PATTERN = re.compile(r"^/company/([^/]{1,100})(?:/.*)?$")
# No leading '-', no spaces or slashes, so it is always one URL path segment.
COMPANY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._%-]{0,99}$")
