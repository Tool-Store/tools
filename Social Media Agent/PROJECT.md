# PROJECT.md (Tool Definition)

Social Media Agent is an MCP tool that reads social media content through each user's own logged-in browser session.

It is moving from running the [Agent Reach](https://github.com/Tool-Store/Agent-Reach) CLI in a per-user container to calling site code directly in one shared container: each request opens a fresh, isolated browser session loaded with that user's saved login, and no CLI runs in between. The site code is ported from [OpenCLI](https://github.com/jackwener/opencli) (Apache-2.0), which Agent Reach called underneath. LinkedIn moves first (all of OpenCLI's LinkedIn commands); Instagram, Facebook and X stay on Agent Reach until LinkedIn is done.

It is separate from Social Media Scraper, which reads public data through third-party APIs.

## It should

- Let a user log in to a supported site once, through a browser they see in a web viewer.
- Keep that login encrypted and tied to the user, so it survives restarts and no other user can use it.
- Read profiles, posts and search results with the user's session, without third-party scraping APIs.
- Know which Toolstore user each request is for, and refuse requests that do not say.
- Keep users apart: every request gets its own browser context, closed when the request ends.
- Limit requests per user per day to lower the risk of account bans.

## Supported sites

| Site | Actions | Runs through |
|---|---|---|
| LinkedIn | `profile` (with sections), `company`, `post search` | Browser sessions (section pages) |
| LinkedIn | `jobs` (search), `read` (job post) | Agent Reach (optional level) |
| Instagram | `search` (users), `profile`, `posts` | Agent Reach (experimental) |
| Facebook | `search`, `profile` | Agent Reach (experimental) |
| X / Twitter | `search`, `profile`, `tweets`, `thread` | Agent Reach (experimental) |

Feed, post analytics, profile analytics and services are next (`PLAN.md` batch 2b), then people search, connections, messages, Sales Navigator, and connection requests and messages.

## Technical stack

- Python 3.11 (`python:3.11-slim-bookworm`)
- Playwright (Python) with its Chromium, for browser sessions; page scripts in `page_scripts/`
- LinkedIn page reading ported from stickerdaniel/linkedin-mcp-server 4.29.0 and OpenCLI 2.0.2 (both Apache-2.0, see `third_party/NOTICE`)
- `cryptography` (Fernet) for saved logins
- Agent Reach CLI, installed from the Tool-Store fork at a pinned commit
- OpenCLI and Node.js 22 (Agent Reach site adapters)
- CloakBrowser, with Debian Chromium as fallback
- Xvfb, x11vnc and noVNC for the login viewer

## MCP functions

- `start_login` - Open a site's login page in the user's browser and return the viewer link. For LinkedIn the login is saved for the calling user as soon as it finishes.
- `get_linkedin_profile` - Read a LinkedIn profile as text (own profile when no link is given), with up to 5 extra sections (experience, education, skills, projects, certifications, languages, honors, volunteering, interests, contact info, posts). Browser session.
- `get_linkedin_company` - Read a company's About page, plus its posts or jobs. Browser session.
- `search_linkedin_posts` - Search posts by keywords, optionally by date and content type, 1-3 pages. Browser session.
- `search_linkedin_jobs` - Search LinkedIn jobs.
- `read_linkedin_job` - Read one LinkedIn job post.
- `search_social` - Search Instagram users, Facebook, or X posts.
- `get_social_profile` - Get an Instagram, Facebook or X profile.
- `get_social_posts` - Get recent Instagram posts or X tweets.
- `get_x_thread` - Get a tweet with its replies.

Every request uses the browser session only (`--backend opencli` on the Agent Reach path), is limited per user per site per day (`DAILY_REQUEST_LIMIT`, default 50), and returns at most 20 items within 20,000 characters (section answers cut their longest sections instead and name them in `truncated_sections`). On the browser-session path every page a call loads counts as one request, and a call that would go over the limit is refused. A request counts as soon as it passes input checks, even if the site then fails, because the site still received it. When a site rate-limits the account, the error says how long to wait.

## Current scope

Phase 1 (container, login, persistence) and Phase 2 (MCP server) are done on Agent Reach. Phase 4 moves LinkedIn to shared-container browser sessions with no CLI (see `PLAN.md`).

## Constraints

- Agent Reach is installed only from the Tool-Store fork, pinned to a commit.
- All persisted state lives in `~/.agent-reach`; only that path is persisted.
- Saved logins are encrypted with `LOGIN_ENCRYPTION_KEY` (from the environment, never in code); without it, logins cannot be saved or read.
- The user id comes from the Toolstore request headers and is trusted as given (JWT signature not checked here), so the MCP port must only be reachable through the Toolstore Tool Router.
- Code taken from OpenCLI and stickerdaniel/linkedin-mcp-server keeps their Apache-2.0 licenses and a notice of every ported file and change (`third_party/`).
- The login viewer is published on localhost only and has no password, so it must never be exposed on a public interface.
- The user always logs in themselves; the tool never handles passwords.
