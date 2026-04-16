# AI.conf

A portable agent-team config repo with shared authored sources and generated target outputs. Clone it, run the flake entrypoints or the `just` wrapper, and the repo will generate/install the target-specific config for the supported tools.

## Quick install

```bash
git clone <repo-url>
cd agent-team
nix develop              # enter devShell with yq + envsubst
nix run .#check          # validate protocols + generate artifacts
nix run .#install        # install generated outputs into the supported target config dirs
```

The supported user-facing entrypoints are the flake apps and the `just` wrapper. `generate.py` and `install.sh` remain the internal implementation layer behind them. Works on Linux, macOS, and Windows (Git Bash).

## Nix entrypoints

The flake exposes formal workflow entrypoints:

```bash
nix run .#validate   # syntax + protocol presence/basic shape checks
nix run .#build      # generate settings.json + claude/ + codex/
nix run .#check      # validate + build
nix run .#install    # run install.sh
nix flake check      # run flake checks (validate + build in sandboxed check derivations)
```

`just` is also supported as a convenience wrapper over those same flake commands:

```bash
just validate
just build
just check
just install
just clean          # removes generated artifacts: settings.json + claude/ + codex/
```

`generate.py` and `install.sh` are kept as internal implementation details for portability and debugging, but they are no longer the primary documented workflow.

## Maintenance

**Symlink fragility:** some generated target files are installed as symlinks by `install.sh`. Tools that rewrite those files may replace the symlink with a regular file. If repo edits stop being reflected in an installed target config, re-run `./install.sh` to restore the symlink.

## Agents

| Agent | Model policy | Role |
|---|---|---|
| `grunt` | fast | Cheap implementer for trivial, tightly scoped work. |
| `worker` | balanced | Standard implementer for normal development tasks. |
| `senior` | strong | Expensive implementer for ambiguous, architectural, or high-risk work. |
| `debugger` | balanced | Diagnoses and fixes bugs with minimal targeted changes. |
| `documenter` | balanced | Writes and updates docs. Never modifies source code. |
| `architect` | strong | Triage, research coordination, architecture design, wave decomposition. Read-only. |
| `researcher` | balanced | Parallel fact-finding. One instance per research question. Read-only. |
| `reviewer` | balanced | Code quality review + AC verification + claim checking. Read-only. |
| `auditor` | balanced | Security analysis + runtime validation. Read-only, runs in background. |

## Skills

| Skill | Purpose |
|---|---|
| `orchestrate` | Orchestration framework — load on demand to decompose and delegate complex tasks |
| `conventions` | Core coding conventions and quality priorities shared by all agents |
| `worker-protocol` | Output format, feedback handling, and operational procedures for worker agents |
| `qa-checklist` | Self-validation checklist workers run before returning results |
| `message-schema` | Typed YAML frontmatter envelopes for all inter-agent communication |

## Rules

Global instructions are modularized in `rules/`. Each file covers a focused topic (git workflow, Nix preferences, response style, etc.). Agent-team specific protocols live in skills, not rules. Target adapters decide how those rules are surfaced.

## Target usage

### Claude Code

Load the orchestrate skill when a task is complex enough to warrant delegation:

```
/skill orchestrate
```

Once loaded, Claude acts as orchestrator — decomposing tasks, selecting agents, reviewing output, and managing the git flow. Agents are auto-delegated based on task type; you don't invoke them directly.

For simple tasks, invoke an agent directly:

```
/agent worker Fix the broken pagination in the user list endpoint
/agent grunt Rename this variable consistently in one file
/agent senior Untangle this multi-file initialization bug
```

### Codex CLI

Agents are available as named agents in the installed Codex config. Invoke them with:

```
codex --agent worker "Fix the broken pagination in the user list endpoint"
```

## Dual-target generation

This repo uses two authored protocol files:

- [SETTINGS.yaml](SETTINGS.yaml) for runtime policy (filesystem, approvals, network, model intent)
- [TEAM.yaml](TEAM.yaml) for team inventory metadata (agents, skills, rules)

Long-form instructions remain authored in Markdown (`agents/*.md`, `skills/*/SKILL.md`, `rules/*.md`).

Runtime policy is documented in [spec/agent-runtime-v1.md](spec/agent-runtime-v1.md) and described by [schemas/agent-runtime.schema.json](schemas/agent-runtime.schema.json). Team inventory is documented in [spec/team-protocol-v1.md](spec/team-protocol-v1.md). `generate.py` derives target-specific outputs for the currently supported adapters.

### What gets generated

| Source | Generated | Location |
|---|---|---|
| `TEAM.yaml` + `agents/*.md` | `claude/agents/*.md` | Claude adapter output |
| `TEAM.yaml` + `agents/*.md` | `codex/agents/*.toml` | Codex adapter output |
| `SETTINGS.yaml` | `settings.json` (compatibility artifact, generated) | repo root |
| `SETTINGS.yaml` | `claude/settings.json` | Claude adapter output |
| `SETTINGS.yaml` | `codex/config.toml` | Codex adapter output |
| `TEAM.yaml` + `rules/*.md` | `codex/AGENTS.md` | Codex adapter output |
| `TEAM.yaml` + `skills/*/SKILL.md` | `codex/skills -> ../skills` | Codex adapter output |
| `TEAM.yaml` + `skills/*/SKILL.md` | installed skill dirs | target install output |

All final config files are generated artifacts. The authored protocol sources are `SETTINGS.yaml`, `TEAM.yaml`, and Markdown instruction content. The primary workflows are `nix run .#build` / `nix run .#install` or the equivalent `just` commands.

Narrow compatibility caveats:

- TEAM schema is intentionally rigid/repo-specific in v1. Inventory changes require schema updates in lockstep.
- Claude generated agent frontmatter is normalized by generator serialization (field order/quoting), which may produce non-semantic diffs.
- Codex skill installation is TEAM-authoritative when `TEAM.yaml` is present. Legacy directory fallback is used only when TEAM is absent or unparseable.
- Codex custom-agent files do not preserve every TEAM agent field. `background`, `memory`, and `isolation` have no documented per-agent equivalents in current Codex docs. TEAM `skills` are mapped into per-agent Codex `skills.config` entries.

Shared runtime intent is generated conservatively across tools:

| Shared source | Claude adapter | Codex adapter |
|---|---|---|
| `runtime.filesystem = read-only` | `permissions.defaultMode = "plan"` | `sandbox_mode = "read-only"` |
| `runtime.filesystem = workspace-write` | `permissions.defaultMode = "acceptEdits"` | `sandbox_mode = "workspace-write"` |
| `runtime.approval = manual` | partially represented | `approval_policy = "on-request"` |
| `runtime.approval = guarded-auto` | partially represented | `approval_policy = "untrusted"` |
| `runtime.approval = full-auto` | partially represented | `approval_policy = "never"` |

The adapters do not expose identical config surfaces. For example, Codex does not support Claude-style per-tool `allow` / `deny` / `ask` patterns directly. The shared protocol keeps the intent portable, then adapters derive the closest target behavior.

`runtime.filesystem`, `runtime.approval`, and `runtime.network_access` are the primary source of truth. `targets.codex.sandbox_mode`, `targets.codex.approval_policy`, and `targets.codex.network_access` are compatibility overrides for exceptional cases only. When set, they override the Codex-derived value.

This repo intentionally sets those Codex overrides to `sandbox_mode: danger-full-access`, `approval_policy: never`, and `network_access: true`. The reason is not that Codex has no approval controls at all, but that it lacks Claude-equivalent pattern-level permission controls for tool/path `allow` / `deny` / `ask`. In this repo, Codex therefore runs with a deliberately more permissive top-level policy than the portable runtime defaults.

Use target-specific fields only when you intentionally need a target-only override:

```yaml
targets:
  codex:
    sandbox_mode: danger-full-access
    approval_policy: untrusted
    network_access: false
  claude:
    claude_md_excludes:
      - .claude/agent-memory/**
```

## Shared protocol

The protocol source is YAML because it is easier to read and annotate than JSON or TOML while still being easy to validate with JSON Schema.

- Runtime policy: [SETTINGS.yaml](SETTINGS.yaml)
- Runtime schema: [schemas/agent-runtime.schema.json](schemas/agent-runtime.schema.json)
- Runtime spec: [spec/agent-runtime-v1.md](spec/agent-runtime-v1.md)
- Team/inventory spec: [spec/team-protocol-v1.md](spec/team-protocol-v1.md)

The protocol is intentionally small in v1:

- portable model tier and reasoning level
- filesystem access intent
- approval intent
- network access
- portable tool classes
- protected paths
- dangerous shell command prompts
- limited target-specific escape hatches

Example:

```yaml
version: 1

model:
  class: balanced
  reasoning: medium

runtime:
  filesystem: workspace-write
  approval: guarded-auto
  network_access: false
  tools:
    - shell
    - read
    - edit
    - write
    - glob
    - grep
    - web_fetch
    - web_search

safety:
  protected_paths:
    - ~/.ssh/**
    - ~/.aws/**
    - ~/.gnupg/**
    - "**/.env*"
  dangerous_shell_commands:
    ask:
      - rm *
      - git reset --hard*
      - sudo *
```

## Model mapping by target

| Claude adapter | Codex adapter |
|---|---|
| `opus` | `gpt-5.4` |
| `sonnet` | `gpt-5.3-codex` |
| `haiku` | `gpt-5.1-codex-mini` |

## Template variables

Agent body text uses `${VAR}` placeholders that are expanded per-target by `generate.py`:

| Variable | Claude adapter | Codex adapter |
|---|---|---|
| `${PLANS_DIR}` | `.claude/plans` | `plans` |
| `${WEB_SEARCH}` | `via WebFetch/WebSearch` | `via web search` |
| `${SEARCH_TOOLS}` | `Use Grep/Glob/Read` | `Search the codebase` |

Skills and rules are tool-agnostic and shared as-is — do not add tool-specific references to them.

## Project-specific config

Each project repo can extend the team with local config in `.claude/`:

- `.claude/CLAUDE.md` — project-specific instructions (architecture notes, domain conventions, stack details)
- `.claude/agents/` — project-local agent overrides or additions

Commit `.claude/` with the project so the team has context wherever it runs.

## Memory

Two memory systems coexist:

- **Project memory** (`memory/`) — curated context files with YAML frontmatter, indexed by `MEMORY.md`. This is the portable, instruction-level memory source shared across targets.
- **Agent memory** (`.claude/agent-memory/`) — Claude Code's built-in runtime memory, written automatically by agents with `memory: project` scope. Excluded from CLAUDE.md context via `claudeMdExcludes` to avoid polluting the context window.

Commit both directories when used so memory persists across machines and sessions.
