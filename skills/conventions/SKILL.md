---
name: conventions
description: Core coding conventions and quality priorities for all projects.
when_to_use: Automatically loaded by agents via skills frontmatter. Load manually when you need to reference project coding standards, commit format, or quality priorities.
---

## Quality priorities (in order)

1. **Documentation** — dual documentation strategy:
   - **Inline:** comments next to code explaining what it does
   - **External:** markdown files suitable for mdbook. Every module/component gets a corresponding `.md` doc covering purpose, usage, and design decisions.
   - **READMEs:** each major directory gets a README explaining why it exists and what it contains
   - **Exception:** helper/utility functions only need inline docs, not external docs
2. **Maintainability** — code is easy to read, modify, and debug. Favor clarity over cleverness.
3. **Reusability** — extract shared logic into well-defined interfaces. Don't duplicate. Helper functions specifically must be easy to cleanly isolate for reuse across the codebase.
4. **Modularity** — clean separation of duties and logic. Each file/module must have a *cohesive* purpose — not necessarily a single purpose, but a group of related responsibilities that belong together. Avoid both god files and excessive fragmentation.

## Naming

- Default to `snake_case` unless the language has a stronger convention (e.g., `camelCase` in JavaScript, `PascalCase` for C++ classes)
- Language-specific formats take precedence over personal preference
- Names must be descriptive — no abbreviations unless universally understood
- No magic numbers — extract to named constants

## Commits

- Use conventional commit format: `type(scope): description`
  - Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`
  - Scope is recommended (e.g., `feat(auth): add JWT middleware`)
  - Description is imperative mood, lowercase, no period
- One logical change per commit — don't bundle unrelated changes
- Commit message body is optional; when present, it explains **why**, not what

## Error handling

- Return codes: `0` for success, non-zero for error
- Error messaging uses three verbosity tiers:
  - **Default:** concise, user-facing message (what went wrong)
  - **Verbose:** adds context (where it went wrong, what was expected)
  - **Debug:** full diagnostic detail (stack traces, variable state, internal IDs)
- Propagate errors explicitly — don't silently swallow failures
- Match the project's existing error patterns before introducing new ones

## Logging

- Follow the same verbosity tiers as error messaging (default/verbose/debug)
- Log at boundaries: entry/exit of major operations, external calls, state transitions
- Never log secrets, credentials, or sensitive user data

## Testing

- New functionality gets tests. Bug fixes get regression tests.
- Tests must be independent — no shared mutable state between test cases
- Test the interface, not the implementation — tests shouldn't break on internal refactors
- Name tests to describe the behavior being verified, not the function being called

## Interface design

- Public APIs must be stable — think before exposing. Easy to extend, hard to break.
- Internal interfaces can evolve freely — don't over-engineer internal boundaries
- Validate at system boundaries (user input, external APIs, IPC). Trust internal code.

## Security

- Never trust external input — validate and sanitize at system boundaries
- No hardcoded secrets, credentials, or keys
- Use established libraries over hand-rolled crypto, auth, or parsing

## File organization

- Directory hierarchy must make ownership and dependencies obvious
- Each major directory gets a README explaining its purpose
- If you can't tell what a directory contains from its path, reorganize
- Group related functionality cohesively — don't fragment for the sake of "single responsibility"

## General

- Clean separation of duties — no god files, no mixed concerns
- Read existing code before writing new code — match the project's patterns
- Minimize external dependencies — vendor what you use, track versions
