# Session Behavior

- Treat each session as stateless — do not assume context from prior sessions
- The instruction hierarchy and `memory/` are the only sources of persistent context
- If something needs to carry forward across sessions, persist it in the appropriate file — not in session memory

# Project Memory

- Project-specific memory lives in `memory/` at the project root
- Use `MEMORY.md` in that directory as the index (one line per entry pointing to a file)
- Memory files use frontmatter: `name`, `description`, `type` (user/feedback/project/reference)
- Commit `memory/` with the repo so memory persists across machines and sessions
- Tool-specific runtime memory (for example `.claude/agent-memory/`) is supplemental and MUST NOT replace `memory/` as the project source of truth
