# PLAN.md

## Tool goal
Maintain and enhance the Google Contacts MCP tool with reliable contact management capabilities through the Google People API, integrated with the Tool Store platform.

## Current state
- MCP server operational with 9 functions and 2 resources
- OAuth activation flow configured
- Basic CRUD operations for contacts implemented
- CSV/VCF export and import supported
- Birthday retrieval feature working

## Task backlog

### High priority
- [ ] Add pagination support for large contact lists
- [ ] Implement batch operations for bulk updates
- [ ] Add photo/avatar support for contacts

### Medium priority
- [ ] Support additional contact fields (addresses, organizations, notes)
- [ ] Add contact group/label management
- [ ] Improve error messages with context-specific suggestions

### Documentation
- [ ] Add inline code documentation for complex transformations
- [ ] Create usage examples for each MCP function
- [ ] Document rate limiting and quota considerations

## Definition of done

- New features have test coverage with mock Google API responses
- All functions validate inputs before external API calls
- OAuth tokens refresh automatically when expired
- Changes to `tool-data.yaml` are validated against runtime
- Tool passes local verification with `server.py --test`

## Verification commands

```bash
# Run MCP server locally
python server.py

# Test with MCP inspector (if available)
npx @anthropics/mcp-inspector

# Validate tool-data.yaml
# (Validation happens at Tool Store upload time)
```
