# PLAN.md

## Tool goal
Build a Social Media Scraper MCP tool that reads public web, YouTube and Reddit content for AI agents, integrated with the Tool Store platform.

## Current state
- Phase 1 implemented: `scrape_url` (Jina Reader) and `get_youtube_transcript` (yt-dlp)
- Optional `JINA_API_KEY` activation form configured

## Task backlog

### Phase 0 - Source validation (dev environment only)
- [ ] Jina Reader on a public article, a LinkedIn profile and an Instagram profile
- [ ] yt-dlp subtitles on a public YouTube video from the container
- [ ] Reddit app-only OAuth search from the container
- [ ] Confirm an all-optional activation form can be skipped

### Phase 1 - Core
- [x] `scrape_url`
- [x] `get_youtube_transcript`
- [ ] Verify locally (syntax, server instantiation, stdio run)

### Phase 2 - Reddit
- [ ] `search_reddit` and `get_reddit_post` via Reddit app-only OAuth
- [ ] Optional `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` activation fields
- [ ] Cache the Reddit access token until expiry

### Deferred
- [ ] Twitter/X via official API, pending read-access pricing

## Definition of done

- All functions validate inputs before external calls
- Every outbound request has a timeout and every result is bounded by `max_chars`
- Upstream failures raise explicit, actionable errors
- Changes to `tool-data.yaml` are consistent with `server.py` signatures
- Tool passes local verification

## Verification commands

```bash
# Syntax check
python -m py_compile server.py scraper.py toolstore_client.py

# Smoke test: server instantiates without errors
python -c "import server; server.create_server()"

# Run MCP server locally
python server.py
```
