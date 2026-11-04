# ARCHITECTURE_INDEX.md

## Files

```text
Social Media Agent/
├─ PROJECT.md             # Tool definition, supported sites, constraints
├─ ARCHITECTURE_INDEX.md  # This file
├─ PLAN.md                # Task checklist, findings and verification steps
├─ README.md              # Build, run, log in and test locally
├─ tool-data.yaml         # MCP contract (10 functions); must match server.py
├─ requirements.txt       # MCP server Python packages
├─ .env.example           # Settings and their defaults
├─ Dockerfile             # Python, Node, Agent Reach (pinned fork commit), Playwright Chromium, login viewer, MCP server
├─ entrypoint.sh          # Clears stale locks, starts the virtual screen and web viewer, then the server
│
├─ server.py              # All MCP function registrations; each validates, counts and delegates
├─ constants.py           # Every fixed value, grouped by topic (sites, limits, logins, browser, input patterns)
├─ errors.py              # Every error the tool raises, and the shared "log in again" message
├─ validators.py          # Input checks for every function argument and numeric settings
├─ responses.py           # JSON response blocks; fits item lists and section answers into the size limit
│
├─ caller.py              # Which Toolstore user made the request (from the Tool Router headers)
├─ sessions.py            # Login start (both paths) and the per-user, per-site daily request limit
├─ login_store.py         # Each user's site logins (cookies), encrypted on disk
├─ file_store.py          # Safe file writes (temporary file, then swap) used by sessions and login_store
├─ browser_session.py     # Shared headless Chromium; one isolated, logged-in context per request; login window
│
├─ linkedin/              # LinkedIn actions on browser sessions, one file per topic
│  ├─ page.py             # Login-wall check and whitespace clean-up shared by every LinkedIn action
│  ├─ sections.py         # Opens a section page, loads all of it, returns its text (clutter removed) and links
│  ├─ links.py            # Turns a section's links into short typed references (person, company, post...)
│  ├─ profile.py          # Profile: main page plus requested section pages
│  ├─ company.py          # Company: About page plus posts or jobs
│  └─ posts.py            # Post search (LinkedIn's "Posts" search tab) and its filters
├─ page_scripts/          # Scripts sent into the browser page
├─ third_party/           # Licenses of the two Apache-2.0 projects code was taken from, and NOTICE listing every ported file
│
├─ agent_reach.py         # Builds Agent Reach commands per site and action, reads replies, maps errors
├─ command_runner.py      # Subprocess execution for Agent Reach: argv only, timeout, output cap
│
├─ scripts/
│  └─ smoke_test.py       # Checks a running server as an MCP client; --live calls each site once
└─ tests/                 # One test_<file>.py per code file, mirroring the folders (tests/linkedin/test_page.py)
```

`agent_reach.py` and `command_runner.py` serve the sites not yet ported (Instagram, Facebook, X, LinkedIn jobs). They are removed once every site runs on browser sessions.

## Where to put new code

| New code | Goes in |
|---|---|
| A new MCP function | `server.py` (thin: validate, count, delegate) and `tool-data.yaml` |
| A LinkedIn action | `linkedin/<topic>.py`, built on `linkedin/sections.py`; any page script in `page_scripts/`; ported code gets a line in `third_party/NOTICE` |
| A new error | `errors.py` |
| A fixed number, name or pattern | `constants.py`, in its topic section |
| An input check | `validators.py` |

## Request flow

1. The AI calls a function in `server.py`.
2. `validators.py` checks every argument; bad input stops here and is not counted.
3. `caller.current_user_id` reads the user from the request; a request without a user stops here.
4. `sessions.count_request` checks and counts that user's daily limit for the site: one per page the call loads (a profile with 2 extra sections is 3).
5. The site action runs on one of two paths:
   - **Browser sessions (LinkedIn profile, company, post search):** the `linkedin/` module opens `browser_session.user_page`, which loads the user's cookies from `login_store`. `linkedin/sections.py` opens each section page, waits for it, clicks "Show more" or scrolls, and reads its text and links with `page_scripts/linkedin_section_content.js`, removes page clutter from the text, and `links.py` cleans the links. The refreshed cookies are saved and the context is closed.
   - **Agent Reach (LinkedIn jobs, Instagram, Facebook, X):** `agent_reach.run_action` builds `agent-reach <channel> <action> ... --backend opencli` and runs it through `command_runner.run_command`.
6. `responses.fit_items` (item lists) or `responses.fit_sections` (section answers, cutting the longest sections) keeps the answer within `MAX_RESPONSE_CHARS`, and `responses.to_text_content` returns it as JSON.

## Login flow (browser-session sites)

`start_login` → `sessions.start_browser_login` opens the site's login page in a visible Chromium on the virtual screen and returns the viewer link. A background task waits until the site's login cookie appears (up to `LOGIN_WINDOW_SECONDS`), then `login_store.save_cookies` encrypts and saves the cookies for that user. One login window at a time.

## Runtime layout (inside the container)

| Path | Owner | Purpose |
|---|---|---|
| `/opt/agent-reach` | image | Agent Reach virtualenv |
| `/opt/ms-playwright` | image | Playwright's Chromium |
| `/app` | image | MCP server code |
| `/home/agent/.agent-reach` | volume | Agent Reach logins and tools, encrypted logins (`logins/`), daily usage counts |
| `:99` | `entrypoint.sh` | Virtual screen used by the login browser |
| port `6080` | `entrypoint.sh` | noVNC web viewer (localhost only) |
| port `5900` | `entrypoint.sh` | x11vnc, container-internal only |
| port `8000` | `server.py` | MCP server, streamable HTTP at `/mcp` |

## Dependency direction

`server.py` → `caller.py`, `sessions.py`, `linkedin/profile.py`, `linkedin/company.py`, `linkedin/posts.py`, `agent_reach.py`, `responses.py`.
`linkedin/profile.py`, `company.py`, `posts.py` → `linkedin/sections.py` → `linkedin/links.py`, `linkedin/page.py` → `browser_session.py` → `login_store.py` → `file_store.py`.
`sessions.py` → `browser_session.py`, `login_store.py`, `file_store.py`, `agent_reach.py` → `command_runner.py`.
`constants.py`, `errors.py` and `validators.py` are used by all; they import nothing from the tool except `constants.py`.
