# PLAN.md

## Tool goal
Build a Social Media Scraper MCP tool that reads public web, YouTube, Instagram, Facebook, LinkedIn, X, Telegram and Reddit content for AI agents, integrated with the Tool Store platform.

## Current state
- Phase 1 implemented: `scrape_url` (Jina Reader) and `get_youtube_transcript` (yt-dlp)
- Phase 1b implemented (free-only, pending manual testing): `get_telegram_channel_posts`, `get_social_profile`, `get_social_posts` via Apify Free plan
- Optional `JINA_API_KEY` activation form configured

## Task backlog

### Phase 0 - Source validation (dev environment only)
- [ ] Jina Reader on a public article
- [ ] yt-dlp subtitles on a public YouTube video from the container
- [ ] Reddit app-only OAuth search from the container
- [ ] Confirm an all-optional activation form can be skipped

### Phase 1 - Core
- [x] `scrape_url`
- [x] `get_youtube_transcript`
- [ ] Verify locally (syntax, server instantiation, stdio run)

### Phase 1b - Social platforms (Apify Free plan, no billing)
- [x] `get_telegram_channel_posts` via `t.me/s` preview and Jina Reader
- [x] `get_social_profile` and `get_social_posts` for instagram, facebook, linkedin, x via Apify
- [x] Per-run spending cap (`maxTotalChargeUsd`) and `limit` capped at 50
- [x] Manual test with a free Apify token in local `.env`: Telegram → Instagram → Facebook → LinkedIn → X (2026-10-28: all 9 calls returned correct data, 1-26s per call)
- [x] Return only useful fields per platform (drop image links and repeated author data) so all posts fit in `max_chars`
- [x] Re-run live tests after field trimming (5 Instagram posts: 4,059 chars; LinkedIn profile: 3,055; 5 X posts: 2,386; none truncated)
- [x] Clear errors for missing/private accounts: Apify `error` items, empty posts, Telegram "Contact @" page; keep X `protected` flag
- [x] Live-check a real private Instagram account (profile returns `private: true`; only collab posts shared with a public account come back, which Instagram shows logged-out)
- [ ] Record Apify cost per call from the Apify console
- [ ] Decide per-user usage limits and pricing before setting `APIFY_API_TOKEN` in any deployed environment

### Phase 2 - Reddit
- [ ] `search_reddit` and `get_reddit_post` via Reddit app-only OAuth
- [ ] Optional `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` activation fields
- [ ] Cache the Reddit access token until expiry

### Deferred
- [ ] Twitter/X via official API (pay-per-use, needs billing)
- [ ] Keyword search across social platforms
- [ ] Meta official access (Instagram Business Discovery, Page Public Content Access) after app review

## Definition of done

- All functions validate inputs before external calls
- Every outbound request has a timeout and every result is bounded by `max_chars`
- Upstream failures raise explicit, actionable errors
- Changes to `tool-data.yaml` are consistent with `server.py` signatures
- Tool passes local verification

## Verification commands

```bash
# Syntax check
python -m py_compile server.py scraper.py social_platforms.py toolstore_client.py

# Unit tests (offline: all HTTP calls are mocked, no Apify credit used)
python -m pytest tests -v

# Smoke test: server instantiates without errors
python -c "import server; server.create_server()"

# Run MCP server locally
python server.py
```
