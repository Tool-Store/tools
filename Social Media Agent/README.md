# Social Media Agent

Runs Agent Reach in a container with its own browser, so a user can log in to social sites once and the tool can read content with that session. See `PROJECT.md` for scope and `PLAN.md` for progress.

## Build

```bash
cd "tools/Social Media Agent"
docker build -t social-media-agent:local .
```

## Run

Create a `.env` from `.env.example` and set `LOGIN_ENCRYPTION_KEY` (and `SOCIAL_AGENT_LOCAL_USER_ID` when calling the server directly, without Toolstore):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```bash
docker volume create social-agent-data
docker run -d --init --name social-agent \
  --shm-size=1g \
  --env-file .env \
  -e MCP_TRANSPORT=streamable-http -e MCP_HOST=0.0.0.0 \
  -e USER_DATA_DIR=/home/agent/.agent-reach/user-data \
  -p 127.0.0.1:6080:6080 \
  -p 127.0.0.1:8000:8000 \
  -v social-agent-data:/home/agent/.agent-reach \
  social-media-agent:local
```

The `-e` lines override `.env` values meant for running on the host: inside the container the server must listen on `0.0.0.0`, and logins and usage counts must live on the volume.

Keep the same `LOGIN_ENCRYPTION_KEY`: a new key makes every saved login unreadable, and users must log in again.

- `--init` reaps the background screen and viewer processes.
- `--shm-size=1g` gives Chrome enough shared memory.
- The viewer (`6080`) and MCP server (`8000`) are bound to `127.0.0.1` because neither has authentication.

## Set up Agent Reach and the sites

```bash
docker exec -it social-agent agent-reach setup
docker exec -it social-agent agent-reach add linkedin
docker exec -it social-agent agent-reach add instagram
docker exec -it social-agent agent-reach add facebook
docker exec -it social-agent agent-reach add twitter
docker exec -it social-agent agent-reach doctor --text
```

## Log in

### LinkedIn (browser sessions)

1. Open `http://localhost:6080/vnc.html` and click **Connect**.
2. Call `start_login` with `{"site": "linkedin"}` (MCP Inspector, see below).
3. Log in to LinkedIn in the browser window shown in the viewer. The window closes and the login is saved, encrypted, for that user as soon as LinkedIn sets its session cookie (up to 10 minutes).

### Instagram, Facebook and X (Agent Reach)

1. Open `http://localhost:6080/vnc.html` and click **Connect**.
2. Run `docker exec -it social-agent agent-reach login linkedin`.
3. Log in to the site in the browser window shown in the viewer.
4. Repeat for `instagram`, `facebook` and `twitter`.

## Test the actions

```bash
docker exec social-agent agent-reach linkedin jobs python --limit 2
docker exec social-agent agent-reach instagram profile nasa
docker exec social-agent agent-reach instagram posts nasa --limit 2
docker exec social-agent agent-reach facebook profile nasa
docker exec social-agent agent-reach twitter tweets nasa --limit 2
```

Add `--help` after an action to see its options, for example `agent-reach instagram posts --help`.

## Test the MCP server

Unit tests (offline, from this folder). `tests/test_browser_session.py` starts a real headless Chromium against a local page, so install Patchright's Chromium once first:

```bash
python -m patchright install chromium
python -m pytest tests
```

Smoke test against the running container (`../venv/bin/python` or any Python with `mcp` installed):

```bash
python scripts/smoke_test.py          # no site contacted, nothing counted
python scripts/smoke_test.py --live   # also calls LinkedIn, Facebook, Instagram and X once each
```

`--live` counts one request per site toward the daily limit. Site errors such as "not logged in" or "rate limited" are reported as answers, not failures.

Live, with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector, choose transport **Streamable HTTP**, URL `http://localhost:8000/mcp`, click **Connect**, then run `search_linkedin_jobs` with `{"query": "python", "limit": 2}`, or `get_linkedin_profile` with `{}` for the logged-in user's own profile, `{"profile_url": "https://www.linkedin.com/in/williamhgates/", "sections": ["experience", "education"]}`, `get_linkedin_company` with `{"company": "microsoft"}`, or `search_linkedin_posts` with `{"keywords": "AI marketing"}`, or `get_instagram_profile` with `{"username": "natgeo"}` after `start_login` with `{"site": "instagram"}`.

## Check that logins survive a restart

```bash
docker restart social-agent
docker logs --since 1m social-agent
docker exec social-agent agent-reach linkedin jobs python --limit 1 --backend opencli
```

The logs must show the web viewer and `Uvicorn running` with no x11vnc or Xvfb errors, and the viewer must connect. Repeat after `docker rm -f social-agent` and a new `docker run` on the same volume: the job search must work without logging in again. This covers `entrypoint.sh` clearing stale screen and Chrome profile locks.

## Measure resources

```bash
docker stats social-agent
```

## Clean up

```bash
docker rm -f social-agent
docker volume rm social-agent-data
```

Removing the volume deletes all saved logins.
