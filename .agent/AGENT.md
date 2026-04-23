# Development Rules

## 0) Required load order (always)

**CRITICAL: The Vibe Code workflow happens at the TOOL LEVEL, not the repo level.**

1. Identify which tool project you are working on (e.g., `Google Contacts/`)
2. Load that tool's Vibe Code docs in order:
   - `<tool-folder>/PROJECT.md` (tool definition and acceptance outcomes)
   - `<tool-folder>/ARCHITECTURE_INDEX.md` (tool-specific architecture map)
   - `<tool-folder>/PLAN.md` (tool's active execution plan)
3. `.agent/architecture-rules/shared.md` (shared repo-level rules)
4. Load service-specific rules from `.agent/architecture-rules/` based on the tool's tech stack
5. `.agent/skills/quality-and-tdd.md` (quality gates and verification)

If a tool folder is missing PROJECT.md, ARCHITECTURE_INDEX.md, or PLAN.md, create them inside that tool folder based on its actual implementation.

## 1) Source of truth

- **Tool-level docs drive development**: `<tool-folder>/PROJECT.md`, `<tool-folder>/ARCHITECTURE_INDEX.md`, `<tool-folder>/PLAN.md`
- **Repo-level docs are indexes only**: `docs/PROJECT.md`, `docs/ARCHITECTURE_INDEX.md`, `docs/PLAN.md` just list tools and link to tool-level docs
- The tool folder's actual files define runtime shape, dependencies, packaging, and tests
- `.agent/architecture-rules/*.md` provide default technical guidance
- If repo docs conflict with a tool's implementation, the tool's implementation wins

## 2) Operating principles

- **Each tool is its own project** with its own Vibe Code docs inside its folder
- Repo-level guidance supports but doesn't override tool-level decisions
- Do not force one tool's conventions onto another tool
- Keep changes scoped to the specific tool being modified
- Build for production quality: correctness, security, observability, maintainability

## 3) Plan-before-code (required)

Before implementation, output:
1. Target tool folder
2. Read and summarize that tool's PROJECT.md and current PLAN.md
3. Impacted files within that tool folder
4. Changes to the tool's capabilities, `tool-data.yaml`, or MCP contract
5. Step-by-step implementation checklist with verification steps

Do not start coding until this plan is coherent and testable.

## 4) Execution policy (required)

For tool work:
- Use the tool's own PLAN.md to track tasks and progress
- Update the tool's ARCHITECTURE_INDEX.md when file/module locations change
- Update the tool's PROJECT.md when capabilities or constraints change
- Only update repo-level `docs/*.md` when adding a new tool to the index

Follow `.agent/skills/quality-and-tdd.md` for quality gates.
Never mark a task complete unless all required verification passes.

## 5) Anti-stuck execution rules

- Try up to 3 viable implementation/debug paths before declaring blocked
- If blocked, report: exact blocker, evidence, options with tradeoffs, recommended action
- Ask for clarification only when it materially changes architecture, scope, security, or paid-service usage
- Never silently skip requirements

## 6) Change control and safety

- No architecture or behavior changes outside approved scope
- No temporary hacks, fake implementations, or hidden TODO debt
- No dummy data in production paths unless explicitly allowed
- Ask before introducing paid services, external integrations, secrets, or irreversible migrations
- Validate input/output boundaries and error handling for every changed flow

## 7) Definition of done

A task is done only when all are true:
- Tool-level acceptance criteria are satisfied
- Tests cover success, failure, and edge cases (if the tool has tests)
- Lint/type/test checks pass for the tool or documented verification path
- Logging/error messages are actionable
- Tool-level docs updated: `<tool-folder>/PLAN.md`, `<tool-folder>/ARCHITECTURE_INDEX.md` if needed
- Known risks and follow-ups explicitly listed

## 8) Output discipline

At handoff, provide:
- What changed (files + behavior)
- Commands run
- Verification results
- Updated tool docs references
- Remaining risks/follow-ups (if any)
