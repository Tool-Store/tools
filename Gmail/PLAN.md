# PLAN.md

## Tool goal
Build and maintain a Gmail MCP tool with reliable email management capabilities through the Gmail API v1, integrated with the Tool Store platform.

## Current state
- v1.0.0 initial implementation complete
- MCP server with messaging, drafts, labels, attachments, and profile capabilities
- OAuth activation flow configured with `gmail.modify` scope
- Attachment download/upload integrated with Tool Store storage

## Task backlog

### High priority
- [ ] Add server-side test harness with mocked Gmail API responses
- [ ] Add structured logging at every API boundary with redacted recipients
- [ ] Add quota-aware retry on `429 Too Many Requests`

### Medium priority
- [ ] Support inline attachments / `cid:` references in HTML bodies
- [ ] Support full thread reply (auto-collect history into References chain)
- [ ] Add label color settings to `create_label`

### Documentation
- [ ] Add Gmail `q` syntax cheat sheet to `prompts/usage.md`
- [ ] Document rate limiting and quota considerations

## Definition of done

- New features have test coverage with mocked Gmail API responses
- All functions validate inputs before external API calls
- OAuth tokens refresh automatically when expired
- Threading headers preserved on replies and forwards
- Changes to `tool-data.yaml` are consistent with `server.py` signatures
- Tool passes local verification (`python -c "import server; server.create_server()"`)

## Verification commands

```bash
# Syntax check
python -m py_compile server.py gmail.py toolstore_client.py

# Smoke test: server instantiates without errors
python -c "import server; server.create_server()"

# Run MCP server locally
python server.py
```
