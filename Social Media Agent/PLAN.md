# PLAN.md

## Tool goal

Read social media content with each user's own logged-in browser session by running Agent Reach in a per-user container, with no third-party scraping APIs.

## Current state

- Agent Reach forked to `Tool-Store/Agent-Reach`, pinned at `b742590` (v1.6.1 plus the configurable browser locale)
- Phase 1 container proven with LinkedIn: login through the viewer, job search returns data, login survives restart and container recreation

## Task backlog

### Phase 1 - Local container proof
- [x] Image builds (1.26 GB, shared by all users)
- [x] Virtual screen and web viewer start; viewer opens at `http://localhost:6080/vnc.html`
- [x] `agent-reach setup` and `agent-reach add <site>` succeed for linkedin, instagram, facebook, twitter
- [x] Browser backend is CloakBrowser (Chromium 146); Agent Reach passes `--no-sandbox` itself, so no extra container flags beyond `--shm-size=1g`
- [x] LinkedIn login through the viewer with `agent-reach login linkedin` (test account)
- [x] `agent-reach linkedin jobs` returns data (10-12 s per call); `agent-reach check linkedin` passes
- [x] LinkedIn login survives `docker restart` and a new container on the same volume
- [x] Memory: 76 MB idle (browser closed), 368 MB right after an action (browser open)
- [x] Facebook (test account): login works; `profile nasa` returns URL and follower count only (name empty); `search openai --limit 2` returns 1 page link with title and badge text joined ("OpenAIVerified account")
- [ ] Instagram (test account): login works, but the first `profile` call got HTTP 429 from Instagram and Agent Reach paused the channel for 1 hour; retry once after the pause
- [ ] X: log in and test (needs a test account)
- [ ] Memory and CPU during login
- [ ] Map `~/.agent-reach` subfolders: tools vs logins vs browser profile (volume is 1.38 GB, mostly tools)
- [ ] Switch the browser locale from `zh-CN` to English (hard-coded in Agent Reach; logged-out pages render as unreadable CJK glyphs without CJK fonts)

### Phase 1 findings
- `HOME` must not be set before the `agent` user exists, or root-owned files in `/home/agent` break `setup` and Chrome's crash handler
- A first failed launch can leave Agent Reach in its pipe fallback mode, which hides Chrome errors; CloakBrowser mode recovers once the browser can start
- Stale Xvfb locks in `/tmp` after `docker restart`, and Chrome `Singleton*` profile locks after container recreation, block startup; `entrypoint.sh` clears both
- Agent Reach falls back to Exa (third-party, free tier, rate limited) when the browser path fails; decide whether to disable that fallback
- Sign in with Google is likely blocked in the automated browser; use the site's own email and password form
- On a site's rate limit, Agent Reach pauses that channel (about 1 hour for Instagram) and answers later calls locally with a `Wait N seconds` hint; `agent_reach.py` must pass that hint on to the AI

### Phase 2 - MCP server
- [x] `server.py` with 7 functions: `start_login`, `search_linkedin_jobs`, `read_linkedin_job`, `search_social`, `get_social_profile`, `get_social_posts`, `get_x_thread`
- [x] `agent_reach.py`, `sessions.py`, `command_runner.py`, `validators.py`, `constants.py` with tests (78 passing, offline)
- [x] Per-site daily request limit, saved on the volume
- [x] `tool-data.yaml` matches `server.py` (names, parameters, required fields)
- [x] Dockerfile installs and starts the MCP server on port 8000
- [x] Image builds and the server starts in the container
- [x] Live call through MCP Inspector returns LinkedIn jobs (9 s with the browser open, 13 s when it has to start; MCP clients need a timeout above the Inspector's 10 s default)
- [x] `--backend opencli` stops the Exa fallback: the reply lists only the `opencli` attempt, and Agent Reach's dispatcher runs public-web routes only when no backend is forced
- [x] Browser locale configurable in the fork (`REACH_BROWSER_LOCALE`, branch `english-browser-locale`, commit `b742590`); Dockerfile pins it and sets `en-US`
- [x] Rebuild and confirm a logged-out login page renders in English (Instagram login page checked)
- [ ] Merge `english-browser-locale` into the fork's `main` and repin to the merge commit
- [ ] Move tool installation into the image so the volume holds only user state
- [ ] Decide pricing in `tool-data.yaml` (currently `free`) once the per-user plan is set

### Hardening (before any cloud use)
- [x] Agent Reach replies that are not a JSON object raise `UNREADABLE_REPLY`
- [x] `items` that are not a list of objects raise `UNREADABLE_REPLY` (missing `items` means no results)
- [x] Rate-limit errors tell the caller how long to wait (from Agent Reach's `Wait <n> seconds` hint)
- [x] Every Agent Reach error code keeps its code and message
- [x] A single item larger than the response limit returns an explanation instead of an empty answer
- [x] Failed requests still count toward the daily limit (documented and tested)
- [x] Response shaping moved from `server.py` to `responses.py`; tool registration split into three helpers (longest function 24 lines)
- [x] `true`/`false` as `limit` not handled in code: the MCP layer converts it to `1` before our validators run
- [x] Timeout inside a real tool call reaches the caller and still counts the request
- [x] Parallel requests: all counted, and the limit is never exceeded (104 tests, stable over repeated runs)
- [x] `entrypoint.sh` stale-lock cleanup: verified by restart and container recreation (documented check in README; needs the real screen and Chrome, so not a unit test)
- [x] `scripts/smoke_test.py`: default run (no site contacted) passes 6/6 against the running container
- [ ] `scripts/smoke_test.py --live` once Instagram's pause is over and X has a test account
- [x] Independent code review (12 findings)
- [x] Review 1: tools are async and run Agent Reach in worker threads, so a slow request no longer blocks other calls; one browser lock keeps Agent Reach commands one at a time
- [x] Review 2: usernames may not start with '-', so they cannot be read as command options
- [x] Review 5: DNS-rebinding protection on, allowing only `127.0.0.1` and `localhost` hosts (must be revisited for the platform's host name before cloud use)
- [ ] Review 4: on timeout, stop the whole process group (browser and helpers), not only `agent-reach`
- [ ] Review 3: correct the output-cap docstring and report "reply too large" instead of "unreadable reply"
- [x] Review 10: all Agent Reach channel and action names live in `agent_reach.py`; `server.py` only refers to them
- [ ] Review 6-9, 11-12: skip counting requests the site never received, shorter stderr logs, `truncated` flag for a single oversized item, `tini` in the image, docs in sync, pinned Python packages

### Phase 3 - Single cloud VM test (dev project only)
- [ ] Run the image on one e2-medium VM
- [ ] Check whether sites block logins from cloud IPs (decides the proxy requirement)
- [ ] Check logins survive VM stop/start; record wake-up time and real cost

### Phase 4 - LinkedIn without a CLI, shared container (decided 2026-11-03)
Direction from the client call: no per-user machine and no CLI between the AI and the site. Agent Reach's LinkedIn actions only run `opencli linkedin ...`, so the site code is ported from OpenCLI 2.0.2 (Apache-2.0): Python + Playwright, with OpenCLI's in-page scripts copied unchanged into `page_scripts/` (named `opencli_scripts/` until batch 2). All 23 OpenCLI LinkedIn commands, including Sales Navigator and the 3 write actions.

Batch 1 - foundation and first function
- [x] `caller.py`: user id from `X-Toolstore-JWT` / `Authorization` / `X-Toolstore-User-Id`; mismatch refused; local runs use `SOCIAL_AGENT_LOCAL_USER_ID` (was `TOOLSTORE_USER_ID`, renamed 2026-11-05)
- [x] `login_store.py`: per-user cookies, Fernet-encrypted, `0600`, folder named by user-id hash
- [x] `browser_session.py`: one shared headless Chromium, a new context per request with the user's cookies, rotated cookies saved after success, `MAX_BROWSER_SESSIONS` limit; visible login window
- [x] `linkedin/page.py`, `linkedin/profile.py`, `get_linkedin_profile`
- [x] `start_login` for LinkedIn saves the login for the calling user; one login window at a time
- [x] Daily limit counted per user and site
- [x] All tests pass (188, stable over 3 runs), including `test_browser_session.py` against a real headless Chromium
- [x] Local live test without Docker (2026-11-04, test account): login window opened on the desktop and closed itself after login; `linkedin.enc` saved `0600` with no readable cookie; own profile returned real data; second call needed no new login; usage counted per user
- [x] Found live: an unknown profile link landed on LinkedIn's `/404/` page and its header was returned as a profile ("0 notifications"); now reported as "LinkedIn has no profile at ..." (regression test added; confirmed live after restart)
- [x] Live: a public profile (williamhgates) returned name, headline, About and Featured. Experience, education and location came back empty, and About starts with the word "About": limits of OpenCLI's profile-read script, to be covered by the dedicated batch 2 functions
- [x] Docker (2026-11-04, fresh volume): image builds; login through the noVNC viewer saved `linkedin.enc` (`0600`, owner `agent`, no readable cookie); own profile, public profile and unknown-profile error all correct; login survives `docker restart`
- [x] Cleanup (2026-11-04): all errors in `errors.py`, shared safe file write in `file_store.py`, LinkedIn code in `linkedin/`, `constants.py` grouped by topic; ruff clean, 126 non-browser tests pass

Batch 2 (decided 2026-11-04 after a live comparison with [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server), Apache-2.0, v4.29.0)
Its "open the section's own page and read its text" method returned full experience, education and location for williamhgates where OpenCLI's profile-read returned them empty, and its post search returned full posts. Its feed was mostly sidebar clutter, and it is built for one user (one browser, calls one at a time), so only its page-reading code is ported, onto our per-user sessions. OpenCLI stays where exact counts matter.
- Daily limit: every LinkedIn page load counts as one request; at most 5 extra sections per call.
- Response size: each section's text is cut to fit `MAX_RESPONSE_CHARS` and marked `truncated`, instead of returning nothing.
- Licenses: both projects' LICENSE files and one NOTICE listing every ported file in `third_party/`.

Batch 2a - section reading core and the most useful functions
- [x] Clutter removal: remove LinkedIn clutter lines (from `text.py`); merged into `linkedin/sections.py` on 2026-11-04
- [x] `linkedin/links.py`: clean, de-duplicated references; unrelated "people also viewed" links dropped (from `link_metadata.py`)
- [x] `linkedin/sections.py`: open a section page, load all of it (show more / scroll), read main text and links (from `capture.py`, `content.py`)
- [x] `get_linkedin_profile` rewritten on sections (`sections` parameter); live: williamhgates shows experience and education
- [x] `search_linkedin_posts`; live: "AI marketing" returns full posts, authors and post links
- [x] `get_linkedin_company` (about, posts, jobs); live: microsoft returns overview and details
- [x] Also done: page loads counted per call (`count_request(..., page_loads)`), refused when over the limit; time limit grows 40 s per extra page; section answers cut to fit (`responses.fit_sections`); scripts folder renamed `page_scripts/`; licenses in `third_party/`; the unused OpenCLI profile scripts removed; 285 tests pass, lint clean
- [x] Local live test 1 (2026-11-04): all three functions return real data; williamhgates experience and education filled; unknown profile error; +6 requests counted. Answers too big: profile main page carried 10 activity posts and a "People who follow X also follow" box, company About carried recruiting, commitments and a locations map, links had count labels ("261")
- [x] Trimmed (tests from the live output): profile main page ends before its activity feed (use the `posts` section), suggestion box removed, company About ends before recruiting/commitments/locations, number-only labels and outside links not in the kept text dropped
- [x] Local live test 2 (2026-11-04): profile answer about 4,700 characters (was about 14,000), company about 3,800 (was about 9,000); experience and education unchanged. Unlabelled outside links from the cut-off part were still listed; now kept only when their address is in the kept text
- [x] Docker (2026-11-04, rebuilt image, saved login reused): profile, company and post search match the local runs; company links reduced to the page and its website
- [x] Docs: PROJECT.md, ARCHITECTURE_INDEX.md, README.md, tool-data.yaml, third_party/NOTICE

Batch 2b - OpenCLI ports
- [ ] `get_linkedin_feed` (OpenCLI `timeline`); live, compared with stickerdaniel's feed output
- [ ] `get_linkedin_post_analytics`, `get_linkedin_profile_analytics`, `get_linkedin_services`
- [ ] Local live test, Docker test, docs
Batch 3 - network and jobs: `people-search`, `connections`, `sent-invitations`, `search`, `job-detail`, `jobs-preferences` (jobs leave Agent Reach)
Batch 4 - messages and Sales Navigator: `inbox`, `thread-snapshot`, `salesnav-search`, `salesnav-inbox`, `salesnav-thread`
Batch 5 - write actions (dry-run by default): `connect`, `safe-send`, `salesnav-message`
Then: proper login window in the web app (replaces the shared viewer), post generator, Instagram/Facebook/X the same way, remove Agent Reach and Node from the image.

### Phase 5 - Instagram on browser sessions (decided 2026-11-05)
The manager chose the same approach as LinkedIn (the user's own login in a private browser session) over third-party scrapers. LinkedIn restricted one test account and blocked a network within two days, and Instagram paused the Agent Reach test account on its first profile call, so the safety measures come first. Reading only; the 13 OpenCLI actions (post, reel, story, like, comment, follow, save) wait for the manager's approval. Reads are ported from OpenCLI 2.0.2 `clis/instagram` (Apache-2.0): one page load, then Instagram's own web API from inside the page.
- [x] Patchright (stealth Playwright) instead of Playwright, for every site; all existing tests pass (318)
- [x] `instagram/page.py`: open Instagram with the user's session, run a read script, clear errors (not logged in, user not found, rate-limited); real-browser tests against a local fake Instagram API that only answers with the saved session cookie
- [x] `instagram/reads.py` (one file instead of the planned accounts.py and posts.py: each would have held about 20 lines): `get_instagram_profile`, `get_instagram_posts`, `search_instagram`, `get_instagram_followers`, `get_instagram_following`, `get_instagram_explore`, `get_instagram_saved`
- [x] Instagram login (`sessionid` cookie), own daily limit (20 Instagram requests per user, 2-3 per call), Instagram removed from the Agent Reach path; 352 tests pass, lint clean
- [x] Live test 1 (2026-11-05): login with an email code worked and all cookies were saved, but every read answered "Instagram has no account". Diagnosis: Instagram answered the API with its logged-out 404 page, because the login came from the visible window ("Chrome/156") and the reads from the headless shell ("HeadlessChrome/156", also in its client hints), which sites treat as a bot; this likely also contributed to the LinkedIn restriction. Fixed: both browsers use the full Chromium build, the hidden one in its headless mode (normal client hints) with the visible window's browser name; a logged-out 404 page is reported as an expired login. Regression tests: the browser tells a local server no "Headless" anywhere, and a fake Instagram's logged-out 404 page asks to log in again (354 tests).
- [x] Live test 2 (2026-11-05): login and the fixed browser worked (pages loaded logged in), but Instagram's website no longer uses the web API OpenCLI calls (`/api/v1/users/web_profile_info` answered 404 even when logged in); the site now loads data with GraphQL requests and puts the profile and its first 12 posts as JSON inside the profile page.
- [x] Phase A (approved 2026-11-05): `get_instagram_profile` and `get_instagram_posts` read the JSON the profile page already carries (posts up to 12, falls back to the page summary for counts), one request per call; `search_instagram`, `get_instagram_followers`, `get_instagram_following`, `get_instagram_explore` and `get_instagram_saved` taken out of the function list until each is ported and live-tested
- [x] Live test 3 (2026-11-05): `get_instagram_profile natgeo` returned the full profile (followers, bio, website, avatar) and `get_instagram_posts natgeo limit 3` returned 3 posts with full captions, likes, comments, type, date and link; no login or wait page
- [ ] Phase B: search, followers, following, explore, saved, one at a time after checking what each page carries live
- [ ] Docker test

### Phase 6 - Reddit and X (client priority, decided 2026-11-09)
R&D with Agent Reach 1.6.1 on a laptop (home and mobile networks, test accounts, CloakBrowser), 2026-11-09:
- Reddit: Agent Reach reads Reddit through OpenCLI, which asks Reddit's `.json` addresses from inside reddit.com. Plain automated Chrome was blocked at the first login ("too many requests"); CloakBrowser logged in, but every data request was refused ("blocked by network security"), also in a normal Chrome, logged in or not, on two networks. Reddit's Responsible Builder Policy requires written approval for any commercial data access. Decision: Reddit's official Data API, after Reddit approves the request; no browser-session reading of Reddit (it would also risk the approved app).
- X: all 4 Agent Reach actions worked with CloakBrowser (18 reads in about 15 minutes: search with operators and 30 results across pages, profiles, tweets, threads with replies; 5-10 s each). Login asked for an email code, no captcha, no warning; the session still worked afterwards. Open: account safety over several days, and from a cloud IP.

X on browser sessions (ported from OpenCLI 1.8.7, the version tested live):
- [x] `x/page.py`, `x/reads.py`, `page_scripts/x_read.js`: `search_x`, `get_x_profile`, `get_x_tweets`, `get_x_thread` (up to 20 tweets; thread counts the tweet itself), from x.com's home page through X's own web API; a renamed query id is looked up in X's own website scripts (no third-party list)
- [x] X login through `start_login` (`auth_token` cookie); X removed from the Agent Reach path; `get_social_posts` removed (replaced by `get_x_tweets`); `search_social` and `get_social_profile` are Facebook only
- [x] Own daily limit (`X_DAILY_REQUEST_LIMIT`, default 30, 1 per call) and at least 10 seconds between one user's X calls
- [x] Real-browser tests against a local fake x.com that only answers with the session cookies and the anti-forgery header; 379 tests pass
- [x] Docs: PROJECT.md, ARCHITECTURE_INDEX.md, README.md, tool-data.yaml (matches server.py), .env.example, third_party/NOTICE, scripts/smoke_test.py (its live check no longer fails on functions without a `site` argument)
- [x] Local live test with the X test account (2026-11-09): login through our window (Patchright) worked with an email code, no captcha, no warning (the first login page was blank until a refresh; the window now opens `x.com/login`, to be rechecked at the next login); all 4 functions worked (8 reads), plus not-found, invalid-name and 10-second-gap errors
- [x] Bug found live (2026-11-09): `get_x_thread` gave 0 views for every tweet because its request did not ask for view counts (also missing in OpenCLI); fixed, with a fake x.com that leaves views out unless asked
- [x] Docker test (2026-11-09): image builds, X login through the viewer worked (`x.com/login` loaded straight away, no blank page), all 4 functions worked. The first call in a fresh container also starts the hidden browser and took over 10 seconds, so the MCP Inspector's default 10-second timeout cancelled it; with 60 seconds every call returned.
- [ ] Check how long Toolstore waits for a tool call: X calls take about 5-15 seconds, longer on the first call after a start
- [ ] 2-3 days with the test account on dev before real users
- [ ] Reddit: request commercial Data API access (one request, from a dedicated account); build on the API once approved

Before any cloud use
- [x] User records on Toolstore (2026-11-05): logins and daily counts in the user's Toolstore data (`user_store.py`, own sub-collection), read with the request's user token and `X-Internal-Token`, so the Dev API checks who is asking; no secret in the tool and no volume needed. Backend fix the same day: the Dev API now refuses another user's data (403).
- [ ] The login viewer is one shared screen: any user with the link sees whoever is logging in. Replace it with a per-user login page (one-time link, private browser, same port) before dev.
- [x] Allowed hosts from `MCP_ALLOWED_HOSTS` (default localhost; `*` turns the check off for cluster-only ports; empty refuses to start).
- [x] `TOOLSTORE_USER_ID` is never used as the caller (Toolstore sets it to the developer's id at publish); the local setting is `SOCIAL_AGENT_LOCAL_USER_ID`.
- [ ] Daily counts are exact within one server process; several replicas could each let one extra request through at the same moment.
- [x] Bug found live (2026-11-05): when LinkedIn redirected the page while it was being read, the call failed with Playwright's "Execution context was destroyed". Page scripts now run again on the page it moved to (up to 3 runs), and a security check or login page is reported with its address (regression tests with a real self-redirecting page).
- [ ] Risk seen live (2026-11-05): after several fresh automated logins in two days (laptop, Docker, another tool), LinkedIn asked the test account to verify a phone number. Before real users: reuse saved sessions as long as possible (rotated cookies are already saved), keep one browser profile and location per user, and consider a stealth browser (Patchright, as stickerdaniel/linkedin-mcp-server uses). Never verify a test account with a number tied to a personal account.

### Later (platform work, outside this folder)
- Per-user container or VM creation, routing, idle stop and deletion
- Authenticated login viewer in the web app
- Paid plan for this tool

## Definition of done (Phase 1)

- All Phase 1 boxes checked with results written into this file
- Measured memory per user and the persisted-folder map recorded
- Known blockers listed with evidence

## Verification commands

See `README.md` for build, run, login and test commands.
