# CLI Runner Manual Verification Scripts

Same style as `tools/Gmail/scripts/`: each script prints PASS/FAIL and exits non-zero on failure.

These tests exercise `cli_runtime` + MCP tool registration. They do **not** call GCP/Kubernetes
and do **not** install heavy packages like `agent-browser` by default.

## Prerequisites

1. Activated venv with `mcp` and `python-dotenv` installed.
2. Run from the `cli-runner/` folder so imports resolve.

```bash
cd /home/python/Desktop/toolstore/tools/cli-runner
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CLI_RUNNER_TEST_STATE_FILE` | `/tmp/cli-runner-test-state.json` | Install-state file used by runtime tests |

## Recommended run order

```bash
python scripts/verify_server.py
python scripts/01_binary_and_status.py
python scripts/02_install_lifecycle.py
python scripts/03_run_cli.py
python scripts/04_safety.py
```

## Safety summary

| Script | Side effects |
|---|---|
| `verify_server.py` | None (introspection only) |
| `01_binary_and_status.py` | None (read-only PATH checks) |
| `02_install_lifecycle.py` | Writes temp state file; runs `echo` only |
| `03_run_cli.py` | Runs local `node`/`python3` only |
| `04_safety.py` | None (expects validation errors) |
