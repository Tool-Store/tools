# ARCHITECTURE_INDEX.md

## Files

```text
Social Media Agent/
├─ PROJECT.md             # Tool definition, supported sites, constraints
├─ ARCHITECTURE_INDEX.md  # This file
├─ PLAN.md                # Task checklist, findings and verification steps
├─ README.md              # Build, run, log in and test locally
├─ tool-data.yaml         # MCP contract (14 functions); must match server.py
├─ requirements.txt       # MCP server Python packages
├─ .env.example           # Settings and their defaults
├─ Dockerfile             # Python, Node, Agent Reach (pinned fork commit), Patchright Chromium, login viewer, MCP server
├─ entrypoint.sh          # Clears stale locks, starts the virtual screen and web viewer, then the server
│
├─ server.py              # All MCP function registrations; each validates, counts and delegates
├─ constants.py           # Every fixed value, grouped by topic (sites, limits, logins, browser, input patterns)
├─ errors.py              # Every error the tool raises, and the shared "log in again" message
├─ validators.py          # Input checks for every function argument and numeric settings
├─ responses.py           # JSON response blocks; fits item lists and section answers into the size limit
│
├─ caller.py              # Which Toolstore user made the request, and their tokens (from the Tool Router headers)
├─ sessions.py            # Login start (both paths), the per-user, per-site daily request limit and the pause between X calls
├─ login_store.py         # Each user's site logins (cookies), encrypted, as user_store records
├─ user_store.py          # A user's records: Toolstore user data (sub-collection) when published, local files otherwise
├─ file_store.py          # Safe file writes (temporary file, then swap) used by user_store
├─ browser_session.py     # Shared headless Chromium (Patchright); one isolated, logged-in context per request; login window
│
├─ linkedin/              # LinkedIn actions on browser sessions, one file per topic
│  ├─ page.py             # Login-wall check and whitespace clean-up shared by every LinkedIn action
│  ├─ sections.py         # Opens a section page, loads all of it, returns its text (clutter removed) and links
│  ├─ links.py            # Turns a section's links into short typed references (person, company, post...)
│  ├─ profile.py          # Profile: main page plus requested section pages
│  ├─ company.py          # Company: About page plus posts or jobs
│  └─ posts.py            # Post search (LinkedIn's "Posts" search tab) and its filters
├─ instagram/             # Instagram reads on browser sessions
│  ├─ page.py             # Opens Instagram as the user, runs a read script, maps Instagram's errors
│  └─ reads.py            # The 7 reads: profile, posts, search, followers, following, explore, saved
├─ x/                     # X reads on browser sessions
│  ├─ page.py             # Opens x.com as the user, runs a read script, maps X's errors
│  └─ reads.py            # The 4 reads Agent Reach offers: search, profile, tweets, thread
├─ page_scripts/          # Scripts sent into the browser page (instagram_read.js and x_read.js hold all reads of their site)
├─ third_party/           # Licenses of the two Apache-2.0 projects code was taken from, and NOTICE listing every ported file
│
├─ agent_reach.py         # Builds Agent Reach commands per site and action, reads replies, maps errors
├─ command_runner.py      # Subprocess execution for Agent Reach: argv only, timeout, output cap
│
├─ pytest.ini             # Imports tests by path (tests/linkedin/test_page.py and tests/instagram/test_page.py)
├─ scripts/
│  └─ smoke_test.py       # Checks a running server as an MCP client; --live calls each site once
└─ tests/                 # One test_<file>.py per code file, mirroring the folders (tests/linkedin/test_page.py)
```

`agent_reach.py` and `command_runner.py` serve the sites not yet ported (Facebook, LinkedIn jobs). They are removed once every site runs on browser sessions.

## Where to put new code

| New code | Goes in |
|---|---|
| A new MCP function | `server.py` (thin: validate, count, delegate) and `tool-data.yaml` |
| An Instagram read | a command in `page_scripts/instagram_read.js` and a function in `instagram/reads.py` |
| An X read | a command in `page_scripts/x_read.js` (its web API operation in `OPERATIONS`) and a function in `x/reads.py` |
| A LinkedIn action | `linkedin/<topic>.py`, built on `linkedin/sections.py`; any page script in `page_scripts/`; ported code gets a line in `third_party/NOTICE` |
| A new error | `errors.py` |
| A fixed number, name or pattern | `constants.py`, in its topic section |
| An input check | `validators.py` |

## Request flow

1. The AI calls a function in `server.py`.
2. `validators.py` checks every argument; bad input stops here and is not counted.
3. `caller.current_caller` reads the user and their Toolstore tokens from the request; a request without a user stops here.
4. `sessions.count_request` checks and counts that user's daily limit for the site: one per page the call loads (a profile with 2 extra sections is 3); Instagram and X have their own lower limits (1 per call), and X calls of one user must be at least 10 seconds apart.
5. The site action runs on one of two paths:
   - **Browser sessions (LinkedIn profile, company, post search):** the `linkedin/` module opens `browser_session.user_page`, which loads the user's cookies from `login_store`. `linkedin/sections.py` opens each section page, waits for it, clicks "Show more" or scrolls, and reads its text and links with `page_scripts/linkedin_section_content.js`, removes page clutter from the text, and `links.py` cleans the links. The refreshed cookies are saved and the context is closed.
   - **Instagram:** `instagram/reads.py` → `instagram/page.py` opens one Instagram page as the user, then `page_scripts/instagram_read.js` reads the profile and posts from the JSON data that page already carries (no extra requests).
   - **X:** `x/reads.py` → `x/page.py` opens x.com's home page as the user, then `page_scripts/x_read.js` asks X's own web API from inside the page (web app token, session cookies, ct0 as anti-forgery header), following result pages; a query id X has renamed is looked up in X's own website scripts.
   - **Agent Reach (LinkedIn jobs, Facebook):** `agent_reach.run_action` builds `agent-reach <channel> <action> ... --backend opencli` and runs it through `command_runner.run_command`.
6. `responses.fit_items` (item lists) or `responses.fit_sections` (section answers, cutting the longest sections) keeps the answer within `MAX_RESPONSE_CHARS`, and `responses.to_text_content` returns it as JSON.

## Where user records live (`user_store.py`)

| Running | Records (encrypted logins, daily counts) | Who checks access |
|---|---|---|
| On Toolstore (`TOOLSTORE_API_BASE`, `TOOLSTORE_DEV_SLUG`, `TOOLSTORE_TOOL_SLUG` set at publish) | Dev API `/tool-user-data/sub-collection/{dev}/{tool}/{user}/social_media_agent/{record}` | The Dev API, with the request's own user token and `X-Internal-Token` |
| Locally / Docker without Toolstore | `USER_DATA_DIR/<sha256(user id)>/<record>.json`, files `0600` | The tool (`SOCIAL_AGENT_LOCAL_USER_ID`) |

The tool's own sub-collection keeps its records apart from the user's main document, where Toolstore keeps activation secrets and OAuth data.

## Login flow (browser-session sites)

`start_login` → `sessions.start_browser_login` opens the site's login page in a visible Chromium on the virtual screen and returns the viewer link. A background task waits until the site's login cookie appears (up to `LOGIN_WINDOW_SECONDS`), then `login_store.save_cookies` encrypts the cookies and `user_store` saves them for that user. One login window at a time.

## Runtime layout (inside the container)

| Path | Owner | Purpose |
|---|---|---|
| `/opt/agent-reach` | image | Agent Reach virtualenv |
| `/opt/ms-playwright` | image | Patchright's Chromium |
| `/app` | image | MCP server code |
| `/home/agent/.agent-reach` | volume | Agent Reach logins and tools; when not on Toolstore, encrypted logins and daily counts (`user-data/`) |
| `:99` | `entrypoint.sh` | Virtual screen used by the login browser |
| port `6080` | `entrypoint.sh` | noVNC web viewer (localhost only) |
| port `5900` | `entrypoint.sh` | x11vnc, container-internal only |
| port `8000` | `server.py` | MCP server, streamable HTTP at `/mcp` |

## Dependency direction

`server.py` → `caller.py`, `sessions.py`, `linkedin/profile.py`, `linkedin/company.py`, `linkedin/posts.py`, `instagram/reads.py`, `x/reads.py`, `agent_reach.py`, `responses.py`.
`instagram/reads.py` → `instagram/page.py` and `x/reads.py` → `x/page.py`, both → `browser_session.py`.
`linkedin/profile.py`, `company.py`, `posts.py` → `linkedin/sections.py` → `linkedin/links.py`, `linkedin/page.py` → `browser_session.py` → `login_store.py` → `user_store.py` → `file_store.py`.
`sessions.py` → `browser_session.py`, `login_store.py`, `user_store.py`, `agent_reach.py` → `command_runner.py`.
`constants.py`, `errors.py` and `validators.py` are used by all; they import nothing from the tool except `constants.py`.
