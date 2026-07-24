# ARCHITECTURE_INDEX.md (Tool Architecture Map)

## Canonical tool tree

```text
.
├─ server.py           # MCP entrypoint + tool registration
├─ cli_runtime.py      # Install state, safety checks, subprocess execution
├─ tool-data.yaml      # MCP contract / marketplace metadata
├─ Dockerfile          # Shared CLI runtime image
├─ .env.example        # Local env template
├─ PROJECT.md          # Tool definition
├─ PLAN.md             # Execution plan
└─ README.md           # Usage
```

## Service ownership

- **MCP lifecycle**: `server.py`
- **Runtime logic**: `cli_runtime.py` only
- **Contract**: `tool-data.yaml`

## Ownership boundaries

- `server.py` registers tools and maps errors; no subprocess logic
- `cli_runtime.py` owns install state, validation, and process execution
- Do not add per-skill Dockerfiles — skills pass recipes into this runner

## Where changes belong

- New MCP function → `server.py` + `tool-data.yaml` + `cli_runtime.py` if needed
- Safety / install policy → `cli_runtime.py`
- Image packages (e.g. node) → `Dockerfile`
