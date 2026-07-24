# PLAN.md

## Tool goal

Ship one shared CLI runner image that many OpenClaw/CLI skills can use for install-once + run mapped commands.

## Current state

- v1.0.0 scaffold complete: status, check binary, install, run_cli
- Install state persisted at `CLI_RUNNER_STATE_PATH`
- Base image includes nodejs/npm

## Task backlog

### High priority
- [ ] Local verification of create_server + install/run against a sample CLI
- [ ] Wire backend activate flow to call `install_skill_cli`
- [ ] Wire skill actions to `run_cli` argv mapping

### Later
- [ ] Stronger install allowlists by package manager
- [ ] Optional uninstall / prune unused binaries

## Definition of done

- Functions match `tool-data.yaml`
- `run_cli` never shells out
- Re-install skipped unless `force=true`
- `python -c "import server; server.create_server()"` succeeds with deps installed

## Verification

```bash
cd tools/cli-runner

# MCP registration smoke
python scripts/verify_server.py

# Runtime checks (Gmail-style PASS/FAIL scripts)
python scripts/01_binary_and_status.py
python scripts/02_install_lifecycle.py
python scripts/03_run_cli.py
python scripts/04_safety.py

# optional: docker build -t cli-runner .
```
