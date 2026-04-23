# api.md

**Supporting rules for tool runtime development.** The actual development plan and architecture for each tool are defined in that tool's own PROJECT.md, ARCHITECTURE_INDEX.md, and PLAN.md inside its folder.

Load this file when the task touches tool runtime code, MCP server behavior, Tool Store platform integration, or third-party API integration.

## Technology stack
- Tool projects may use different programming languages and runtimes
- MCP server/runtime SDK chosen by the owning tool project
- Tool Store Developer API
- Third-party APIs chosen by the owning tool project, such as Google People API
- YAML tool contract files (`tool-data.yaml`)

## API goals
- Production-ready MVP suitable for real users
- Tool runtime code is the source of truth for tool-specific MCP behavior
- Validate and authorize every runtime boundary
- Provide repo-level runtime rules without assuming one universal tool layout
 
## Backend rules
- Each tool project owns its own runtime layout, entrypoint naming, dependency management, packaging, and local verification workflow
- Keep MCP registration in the owning tool project's runtime entrypoint using that tool's language/runtime conventions
- Put third-party integration logic in tool-local modules appropriate for that tool project
- Put Tool Store platform integration in tool-local helpers/clients appropriate for that tool project
- Keep `tool-data.yaml` synchronized with runtime capabilities, activation requirements, permissions, and deployment settings
- Validate tool inputs before calling third-party APIs or Tool Store endpoints
- Keep logging and error handling explicit at external API and Tool Store integration boundaries
- Prefer fail-fast behavior for missing env vars, missing tokens, or invalid activation state
- Keep side effects explicit and idempotent where retries are possible
- Use Tool Store storage and user-data APIs instead of inventing repo-local persistence layers
- Do not assume every tool project shares the current Python example structure
- Treat the current Python example as evidence of one valid pattern, not the only valid pattern
- Keep secrets and service credentials in environment/config management only

## Authentication and authorization
- Tool runtimes should use Tool Store-provided identity and JWT context rather than implementing their own auth systems
- Third-party OAuth tokens should be obtained from Tool Store-managed activation/user data
- Never trust tool input or external API responses without validation

## Storage layout
- Tool files should use Tool Store storage paths such as `/{dev_slug}-{tool_slug}/{user_slug}/{file_name}`
- Tool user data should use Tool Store collections such as `{dev_slug}-{tool_slug}` and their sub-collections

## Testing locations
- Tool-local tests should follow the impacted tool project's own conventions and live with that tool project's codebase
 
## Deliverables
- Tool implementation in the owning tool folder, including that tool project's runtime files and `tool-data.yaml`
- Canonical docs in `/docs/PROJECT.md`, `/docs/PLAN.md`, and `/docs/ARCHITECTURE_INDEX.md`
- Local run support appropriate for the owning tool project's runtime
- Lint, test, and run steps documented or implemented for the impacted tool project
- CI-ready tool-project commands where the owning tool project supports them
