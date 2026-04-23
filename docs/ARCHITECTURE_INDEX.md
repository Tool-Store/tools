# Repo Index: Tool Architecture

This file indexes tool-level architecture documentation. Each tool's architecture, ownership, and boundaries are defined in that tool's own ARCHITECTURE_INDEX.md.

## Tool Architecture Indexes

| Tool | Architecture Index | Tech Stack |
|------|-------------------|------------|
| Google Contacts | [Google Contacts/ARCHITECTURE_INDEX.md](./Google%20Contacts/ARCHITECTURE_INDEX.md) | Python, MCP SDK, Google People API |

## Repository Structure

```
tools/
├── <tool-name>/              # Each tool is its own project
│   ├── PROJECT.md            # Tool definition
│   ├── ARCHITECTURE_INDEX.md # Tool architecture
│   ├── PLAN.md               # Tool execution plan
│   ├── tool-data.yaml        # MCP contract
│   └── ...                   # Tool implementation
├── docs/                     # Repo-level indexes (this folder)
└── README.md                 # Tool authoring guide
```

## Adding a New Tool

1. Create a new folder for your tool
2. Add your tool's PROJECT.md, ARCHITECTURE_INDEX.md, and PLAN.md inside that folder
3. Update this index to link to your tool's docs
4. Include `tool-data.yaml` at minimum for platform integration

## Cross-Repo References

- [Backend Architecture](../../backend/docs/ARCHITECTURE_INDEX.md) - Tool Store platform APIs
- [Webapp Architecture](../../Webapp/docs/ARCHITECTURE_INDEX.md) - Consumer/developer frontend
