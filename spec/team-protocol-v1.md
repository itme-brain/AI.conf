# Team Protocol v1

`TEAM.yaml` defines the team metadata and inventory protocol for portable generation targets in this repo.

Implementation status:

- Wave 1: protocol + documentation introduced
- Wave 2: generator + install integration completed; TEAM metadata is the active source of truth for team inventory behavior

## Goals

- Define a neutral, schema-backed source for agents, skills, and rules metadata.
- Keep Claude and Codex as adapter targets rather than protocol sources.
- Preserve Markdown as the human-authored instruction content format.
- Preserve current generated output behavior unless a narrow caveat is explicitly documented.

## Scope

Version 1 standardizes:

- agent inventory and metadata required for generation
- skill inventory metadata
- rule inventory and deterministic ordering
- adapter boundaries for Claude and Codex
- validation requirements needed by the generator

Version 1 does not standardize:

- full prose structure for skills/rules/agents
- provider-specific runtime/tool grammars
- every future adapter target

## Source-of-Truth Split

- `SETTINGS.yaml`: runtime policy protocol (filesystem, approval intent, network, model intent)
- `TEAM.yaml`: team inventory protocol (agents, skills, rules metadata and references)
- Markdown files: instruction bodies
  - agents: `agents/*.md`
  - skills: `skills/*/SKILL.md`
  - rules: `rules/*.md`

Generated artifacts remain:

- `settings.json`
- `claude/`
- `codex/`

## Required TEAM Inventories

`TEAM.yaml` must contain:

- `agents`
- `skills`
- `rules`

## Agent Contract

Each agent entry includes metadata required for adapter generation:

- `id`
- `name`
- `description`
- `model`
- `effort`
- `permission_mode`
- `tools`
- `disallowed_tools`
- `max_turns`
- `skills`
- optional `background`
- optional `memory`
- optional `isolation`
- `instruction_file`

`instruction_file` points to the Markdown source for long-form instructions.

## Skill Contract

Each skill entry includes lightweight metadata and content reference:

- `id`
- `name`
- `description`
- `instruction_file`
- target/install metadata (`applies_to`, `install_mode`)

Skill prose remains in `skills/*/SKILL.md`.

## Rule Contract

Each rule entry includes:

- `id`
- `source_file`
- deterministic order metadata
- optional target metadata

Rule prose remains in `rules/*.md`.

## Adapter Boundaries

Claude and Codex are render targets.

Current target behavior:

- Claude generation consumes TEAM metadata + Markdown content and outputs:
  - `claude/CLAUDE.md`
  - `claude/settings.json`
  - `claude/agents/*.md`
- Codex generation consumes TEAM metadata + Markdown content and outputs:
  - `codex/config.toml`
  - `codex/AGENTS.md`
  - `codex/agents/*.toml`
  - `codex/skills` symlinked to the shared skill directories for relative `skills.config` references

## Validation Requirements

TEAM validation enforces schema + runtime checks for:

- schema version correctness
- required sections present
- unique IDs for agents/skills/rules
- referenced files exist
- deterministic rule ordering inputs are valid
- `order` IDs match declared inventory keys
- item `id` matches keyed map entry

## Compatibility Caveats

- Existing YAML frontmatter in `agents/*.md` may remain for editorial continuity, but generation does not use it for team metadata.
- Output diffs that are purely formatting-related are acceptable; semantic behavior changes are not unless explicitly documented.
- TEAM schema is intentionally rigid/repo-specific in v1; inventory additions/removals require schema updates in lockstep.
- Agent metadata is not fully portable across targets. Current Codex custom-agent docs cover session-style fields such as `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, and `skills.config`, but do not document per-agent equivalents for TEAM's `background`, `memory`, or `isolation` fields.

## Out of Scope

- Rewriting instruction prose for style
- Full content schemas for skill/rule prose
- Generalizing all future adapters in v1
