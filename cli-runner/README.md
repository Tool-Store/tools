# CLI Runner

Shared Tool Store MCP tool for CLI-based skills.

## What it does

1. **Install once** — `install_skill_cli` runs install steps and records state  
2. **Run actions** — `run_cli` executes mapped argv commands (no shell)  
3. **Skip reinstall** — later activates see `already_installed`

## MCP functions

| Function | Purpose |
|----------|---------|
| `get_skill_install_status` | Check install state for a skill slug |
| `check_cli_binary` | Is binary on PATH? |
| `install_skill_cli` | Run install steps + verify bins |
| `run_cli` | Run `["binary", "arg1", ...]` |

## Example: agent-browser

```text
install_skill_cli(
  skill_slug="agent-browser",
  bins=["agent-browser"],
  install_steps=[
    "npm install -g agent-browser",
    "agent-browser install"
  ]
)

run_cli(argv=["agent-browser", "open", "https://example.com"])
```

## Local run

```bash
cd tools/cli-runner
pip install mcp python-dotenv
cp .env.example .env
python server.py
```

## Docker

```bash
docker build -t cli-runner .
```

Backend wiring (activate + action mapping) comes after this tool is tested.
