# PROJECT.md (Tool Definition)

CLI Runner is the shared MCP runtime for CLI-based skills. Many skills reuse this one tool/image instead of each skill shipping its own container.

## It should

- Install a skill's CLI deps once per container (skip on later activates).
- Check whether required binaries exist on PATH.
- Run mapped skill actions as argv lists (no shell).
- Persist install state so re-activate does not reinstall.

## Capabilities

- `get_skill_install_status` — was this skill already installed here?
- `check_cli_binary` — is a binary on PATH?
- `install_skill_cli` — run install steps + verify bins
- `run_cli` — execute mapped command argv

## Technical stack

- Python 3.11
- MCP Python SDK (FastMCP)
- Base image includes `nodejs` / `npm` for common skill installs

## Quality constraints

- Validate all inputs at the boundary
- Deny dangerous install patterns
- `run_cli` never uses shell=True
- Fail fast with clear errors
- No Tool Store OAuth required for v1
