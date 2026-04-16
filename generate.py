#!/usr/bin/env python3
"""Generate Claude, Codex, and OpenCode build artifacts from TEAM.yaml + SETTINGS.yaml.

Ports generate.sh to Python. Ecosystem dependencies:
  * pyyaml     — YAML parsing
  * jsonschema — schema validation for SETTINGS.yaml / TEAM.yaml

Agent source files in agents/*.md are the single source of truth; this script
derives tool-specific equivalents for each harness. Template variables in
agent bodies are expanded via string.Template:
  ${WEB_SEARCH}   — how web search is referenced
  ${SEARCH_TOOLS} — how codebase search tools are referenced

Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from string import Template
from typing import Any

import yaml
from jsonschema import validate

# NOTE: TOML output (Codex) is hand-built rather than generated via tomli_w
# because tomli_w does not emit multiline-basic-string (`"""..."""`) literals,
# which would force every embedded quote/newline in a developer_instructions
# body to be escaped onto a single line — unreadable for humans and diff tools.

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent

TEAM_YAML = SCRIPT_DIR / "TEAM.yaml"
SETTINGS_SHARED_YAML = SCRIPT_DIR / "SETTINGS.yaml"
SETTINGS_JSON = SCRIPT_DIR / "settings.json"
CLAUDE_MD_SRC = SCRIPT_DIR / "CLAUDE.md"

TEAM_SCHEMA = SCRIPT_DIR / "schemas" / "team.schema.json"
SETTINGS_SCHEMA = SCRIPT_DIR / "schemas" / "agent-runtime.schema.json"

CLAUDE_DIR = SCRIPT_DIR / "claude"
CLAUDE_AGENTS_DIR = CLAUDE_DIR / "agents"

CODEX_DIR = SCRIPT_DIR / "codex"
CODEX_AGENTS_DIR = CODEX_DIR / "agents"

OPENCODE_DIR = SCRIPT_DIR / "opencode"
OPENCODE_AGENTS_DIR = OPENCODE_DIR / "agents"
OPENCODE_BASE_CONFIG = OPENCODE_DIR / "config.json"
OPENCODE_SKILLS_DIR = OPENCODE_DIR / "skills"

ORCHESTRATE_SKILL = SCRIPT_DIR / "skills" / "orchestrate" / "SKILL.md"
OPENCODE_MODEL_ID = "llama-stack/llamacpp/Qwen3.6-35B-A3B-UD-Q6_K"

# ---------------------------------------------------------------------------
# Template variable values per target
# ---------------------------------------------------------------------------
CLAUDE_VARS = {
    "WEB_SEARCH": "via WebFetch/WebSearch",
    "SEARCH_TOOLS": "Use Grep/Glob/Read",
}
CODEX_VARS = {
    "WEB_SEARCH": "via web search",
    "SEARCH_TOOLS": "Search the codebase",
}
OPENCODE_VARS = dict(CODEX_VARS)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def load_body(path: Path) -> str:
    """Return the markdown body of a file, skipping YAML frontmatter if present.

    We intentionally do NOT rely on python-frontmatter's content stripping,
    because some agent bodies begin with a blank line that must be preserved
    for downstream parity with the bash output. We detect frontmatter by
    checking whether the first line is "---", then skip up to the next "---".
    """
    raw = path.read_text()
    if not raw.startswith("---\n"):
        return raw
    # Find the closing fence after position 4.
    idx = raw.find("\n---\n", 4)
    if idx == -1:
        # Malformed — return as-is.
        return raw
    return raw[idx + len("\n---\n"):]


def expand(body: str, variables: dict[str, str]) -> str:
    return Template(body).safe_substitute(variables)


def replace_symlink(link: Path, target: Path) -> None:
    """Create or replace a relative symlink at `link` pointing to `target`."""
    if link.is_symlink() or link.exists():
        if link.is_symlink() or link.is_file():
            link.unlink()
        else:
            shutil.rmtree(link)
    link.symlink_to(target)


import re

_BARE_YAML_SCALAR = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")


def dump_yaml_scalar_block(fields: dict[str, Any]) -> str:
    """Dump a dict as YAML block-style, preserving key order.

    Mirrors generate.sh's output style: top-level string scalars are
    single-quoted; list items that look like bare identifiers stay unquoted;
    ints and bools render unquoted.
    """
    lines: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_yaml_list_item(str(item))}")
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: {_yaml_single_quoted(str(v))}")
        else:
            lines.append(f"{key}: {_yaml_single_quoted(str(value))}")
    return "\n".join(lines)


def _yaml_single_quoted(s: str) -> str:
    """YAML 1.2 single-quoted scalar: double any embedded apostrophes."""
    return "'" + s.replace("'", "''") + "'"


def _yaml_list_item(s: str) -> str:
    """List items stay unquoted when they're bare identifiers, matching bash output."""
    if _BARE_YAML_SCALAR.match(s):
        return s
    return _yaml_single_quoted(s)


def _assemble_markdown(frontmatter_text: str, body: str) -> str:
    """Assemble frontmatter + body the same way bash's heredoc did.

    Bash did: echo "---"; echo ""; echo "$body" — so output after the closing
    fence is "\\n<body>\\n" (an explicit blank line, then the body, then echo's
    trailing newline). Source bodies also begin with a blank line of their
    own, so the visible framing is: fence, blank, blank, content.
    """
    return "---\n" + frontmatter_text + "\n---\n\n" + body


# ---------------------------------------------------------------------------
# Shared mappings
# ---------------------------------------------------------------------------
def model_class_to_claude(cls: str) -> str:
    return {"fast": "haiku", "powerful": "opus", "balanced": "sonnet"}.get(cls, "sonnet")


def approval_intent_to_codex(intent: str) -> str:
    return {
        "manual": "on-request",
        "full-auto": "never",
        "guarded-auto": "untrusted",
    }.get(intent, "untrusted")


def filesystem_intent_to_claude_mode(fs: str) -> str:
    return {"read-only": "plan", "workspace-write": "acceptEdits"}.get(fs, "acceptEdits")


def portable_tool_to_claude(tool: str) -> str:
    return {
        "shell": "Bash",
        "read": "Read",
        "edit": "Edit",
        "write": "Write",
        "glob": "Glob",
        "grep": "Grep",
        "web_fetch": "WebFetch",
        "web_search": "WebSearch",
    }.get(tool, tool)


def claude_model_for_agent(agent: dict) -> str:
    return agent["model"]


def codex_model_for_agent(agent: dict) -> str:
    return {
        "opus": "gpt-5.4",
        "sonnet": "gpt-5.3-codex",
        "haiku": "gpt-5.1-codex-mini",
    }.get(agent["model"], "gpt-5.3-codex")


def codex_effort_for_agent(agent: dict) -> str:
    effort = agent.get("effort") or "medium"
    return {"low": "low", "medium": "medium", "high": "high", "max": "xhigh"}.get(effort, "medium")


def codex_sandbox_for_agent(agent: dict, codex_override: str | None) -> str:
    if codex_override:
        return codex_override
    if agent.get("permission_mode") == "plan":
        return "read-only"
    if agent.get("permission_mode") == "acceptEdits":
        tools = agent.get("tools") or []
        if "Write" in tools or "Edit" in tools:
            return "workspace-write"
    return "read-only"


def codex_default_sandbox(default_mode: str, override: str | None) -> str:
    if override:
        return override
    return {"plan": "read-only", "acceptEdits": "workspace-write"}.get(default_mode, "workspace-write")


def codex_approval_policy(runtime_approval: str, override: str | None) -> str:
    if override:
        return override
    return approval_intent_to_codex(runtime_approval)


def opencode_temperature_for_agent(agent: dict) -> float:
    """Map agent role to opencode temperature per opencode's own guidance.

    0.0-0.2 — analytical/planning
    0.3-0.5 — general development
    """
    if agent.get("permission_mode") == "plan":
        return 0.1

    tools = set(agent.get("tools") or [])
    disallowed = set(agent.get("disallowed_tools") or [])
    can_write = "Write" in tools and "Write" not in disallowed
    can_edit = "Edit" in tools and "Edit" not in disallowed
    if not can_write and not can_edit:
        return 0.1
    return 0.3


def opencode_permission_block(agent: dict) -> dict[str, str]:
    tools = set(agent.get("tools") or [])
    disallowed = set(agent.get("disallowed_tools") or [])

    def allowed(name: str) -> bool:
        return name in tools and name not in disallowed

    # Note: `read` is intentionally omitted so global opencode.json read rules
    # (which are pattern-based) aren't shadowed by a per-agent catch-all.
    # See config.ts:264 — agent.permission is merged LAST, and evaluate() uses
    # findLast(), so any per-agent `read: "allow"` here becomes a `{pattern: "*",
    # action: "allow"}` rule that defeats the global pattern denies.
    return {
        "edit": "allow" if allowed("Edit") else "deny",
        "write": "allow" if allowed("Write") else "deny",
        "bash": "allow" if allowed("Bash") else "deny",
        "webfetch": "allow" if (allowed("WebFetch") or allowed("WebSearch")) else "deny",
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_protocol_files(team: dict, settings: dict) -> None:
    validate(instance=settings, schema=json.loads(SETTINGS_SCHEMA.read_text()))
    validate(instance=team, schema=json.loads(TEAM_SCHEMA.read_text()))

    for agent_id in team["agents"]["order"]:
        path = SCRIPT_DIR / team["agents"]["items"][agent_id]["instruction_file"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing agent instruction file: {path}")

    for skill_id in team["skills"]["order"]:
        path = SCRIPT_DIR / team["skills"]["items"][skill_id]["instruction_file"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing skill instruction file: {path}")

    for rule_id in team["rules"]["order"]:
        path = SCRIPT_DIR / team["rules"]["items"][rule_id]["source_file"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing rule source file: {path}")


# ---------------------------------------------------------------------------
# Legacy settings.json
# ---------------------------------------------------------------------------
def generate_legacy_settings_json(settings: dict) -> None:
    model_class = settings["model"]["class"]
    reasoning = settings["model"]["reasoning"]
    fs = settings["runtime"]["filesystem"]
    approval = settings["runtime"]["approval"]

    claude_model = model_class_to_claude(model_class)
    claude_mode = filesystem_intent_to_claude_mode(fs)

    codex_target = settings.get("targets", {}).get("codex", {}) or {}
    codex_approval = codex_target.get("approval_policy") or approval_intent_to_codex(approval)
    codex_network = codex_target.get("network_access", settings["runtime"].get("network_access", False))

    allow = [portable_tool_to_claude(t) for t in settings["runtime"].get("tools", [])]

    deny: list[str] = []
    for path in settings.get("safety", {}).get("protected_paths", []):
        deny.extend([f"Read({path})", f"Write({path})", f"Edit({path})"])

    ask = [f"Bash({cmd})" for cmd in settings.get("safety", {}).get("dangerous_shell_commands", {}).get("ask", [])]

    claude_target = settings.get("targets", {}).get("claude", {}) or {}
    claude_md_excludes = claude_target.get("claude_md_excludes", [".claude/agent-memory/**"])

    payload: dict[str, Any] = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "attribution": {"commit": "", "pr": ""},
        "permissions": {
            "allow": allow,
            "deny": deny,
            "ask": ask,
            "defaultMode": claude_mode,
        },
        "model": claude_model,
        "effortLevel": reasoning,
        "codex": {
            "approvalPolicy": codex_approval,
            "networkAccess": codex_network,
        },
        "claudeMdExcludes": claude_md_excludes,
    }
    SETTINGS_JSON.write_text(json.dumps(payload, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Claude generator
# ---------------------------------------------------------------------------
def generate_claude(team: dict) -> None:
    log("=== Generating Claude output ===")

    if CLAUDE_DIR.exists():
        shutil.rmtree(CLAUDE_DIR)
    CLAUDE_AGENTS_DIR.mkdir(parents=True)

    shutil.copy(CLAUDE_MD_SRC, CLAUDE_DIR / "CLAUDE.md")
    log(f"Copied: {CLAUDE_DIR / 'CLAUDE.md'}")

    shutil.copy(SETTINGS_JSON, CLAUDE_DIR / "settings.json")
    log(f"Copied: {CLAUDE_DIR / 'settings.json'}")

    replace_symlink(CLAUDE_DIR / "rules", Path("../rules"))
    log(f"Symlinked: {CLAUDE_DIR / 'rules'} -> ../rules")
    replace_symlink(CLAUDE_DIR / "skills", Path("../skills"))
    log(f"Symlinked: {CLAUDE_DIR / 'skills'} -> ../skills")

    for agent_id in team["agents"]["order"]:
        agent = team["agents"]["items"][agent_id]
        src = SCRIPT_DIR / agent["instruction_file"]
        body = expand(load_body(src), CLAUDE_VARS)

        fm: dict[str, Any] = {
            "name": agent["name"],
            "description": agent["description"],
            "model": claude_model_for_agent(agent),
        }
        if agent.get("effort"):
            fm["effort"] = agent["effort"]
        if agent.get("permission_mode"):
            fm["permissionMode"] = agent["permission_mode"]
        fm["tools"] = ", ".join(agent["tools"])
        if agent.get("disallowed_tools"):
            fm["disallowedTools"] = ", ".join(agent["disallowed_tools"])
        if agent.get("background"):
            fm["background"] = True
        if agent.get("memory"):
            fm["memory"] = agent["memory"]
        if agent.get("isolation"):
            fm["isolation"] = agent["isolation"]
        if agent.get("max_turns") is not None:
            fm["maxTurns"] = int(agent["max_turns"])
        if agent.get("skills"):
            fm["skills"] = list(agent["skills"])

        dst = CLAUDE_AGENTS_DIR / f"{agent['name']}.md"
        dst.write_text(_assemble_markdown(dump_yaml_scalar_block(fm), body))
        log(f"Generated: {dst}")


# ---------------------------------------------------------------------------
# Codex generator
# ---------------------------------------------------------------------------
def generate_codex(team: dict, settings: dict) -> None:
    log("")
    log("=== Generating Codex output ===")

    if CODEX_DIR.exists():
        shutil.rmtree(CODEX_DIR)
    CODEX_AGENTS_DIR.mkdir(parents=True)

    replace_symlink(CODEX_DIR / "skills", Path("../skills"))
    log(f"Symlinked: {CODEX_DIR / 'skills'} -> ../skills")

    codex_target = settings.get("targets", {}).get("codex", {}) or {}
    codex_sandbox_override = codex_target.get("sandbox_mode")

    log("Generating Codex agent definitions...")
    for agent_id in team["agents"]["order"]:
        agent = team["agents"]["items"][agent_id]
        src = SCRIPT_DIR / agent["instruction_file"]
        body = expand(load_body(src), CODEX_VARS)

        # Bash's command substitution strips trailing newlines from extract_body
        # before concatenating with the heredoc, so strip ours too for parity.
        body = body.rstrip("\n")
        disallowed = agent.get("disallowed_tools") or []
        if disallowed:
            body = body + "\n\nYou do NOT have access to these tools: " + ", ".join(disallowed)

        if '"""' in body:
            raise ValueError(
                f"agent instruction contains raw triple quotes which break TOML in {src}"
            )

        dst = CODEX_AGENTS_DIR / f"{agent['name']}.toml"
        lines: list[str] = []
        lines.append(f'name = "{agent["name"]}"')
        lines.append(f'description = "{agent["description"]}"')
        lines.append(f'model = "{codex_model_for_agent(agent)}"')
        lines.append(f'model_reasoning_effort = "{codex_effort_for_agent(agent)}"')
        lines.append(f'sandbox_mode = "{codex_sandbox_for_agent(agent, codex_sandbox_override)}"')
        lines.append('developer_instructions = """')
        lines.append(body)
        lines.append('"""')

        agent_skills = set(agent.get("skills") or [])
        for skill_id in team["skills"]["order"]:
            skill = team["skills"]["items"][skill_id]
            if "codex" not in skill.get("applies_to", []):
                continue
            enabled = "true" if skill_id in agent_skills else "false"
            lines.append("[[skills.config]]")
            lines.append(f'path = "../skills/{skill_id}/SKILL.md"')
            lines.append(f"enabled = {enabled}")
            lines.append("")

        dst.write_text("\n".join(lines) + "\n")
        log(f"Generated: {dst}")

    # AGENTS.md
    log("")
    log("Generating codex/AGENTS.md...")
    (CODEX_DIR / "AGENTS.md").write_text(_build_agents_md(team, "codex"))
    log(f"Generated: {CODEX_DIR / 'AGENTS.md'}")

    # config.toml
    log("")
    log("Generating codex/config.toml...")
    default_mode = filesystem_intent_to_claude_mode(settings["runtime"]["filesystem"])
    config_sandbox = codex_default_sandbox(default_mode, codex_sandbox_override)
    config_approval = codex_approval_policy(
        settings["runtime"]["approval"],
        codex_target.get("approval_policy"),
    )
    codex_network = codex_target.get("network_access", settings["runtime"].get("network_access", False))

    config_lines = [
        "#:schema https://developers.openai.com/codex/config-schema.json",
        'model = "gpt-5.3-codex"',
        'model_reasoning_effort = "medium"',
        f'sandbox_mode = "{config_sandbox}"',
        f'approval_policy = "{config_approval}"',
    ]
    if config_sandbox == "workspace-write":
        config_lines.append("")
        config_lines.append("[sandbox_workspace_write]")
        config_lines.append(f"network_access = {'true' if codex_network else 'false'}")

    (CODEX_DIR / "config.toml").write_text("\n".join(config_lines) + "\n")
    log(f"Generated: {CODEX_DIR / 'config.toml'}")


# ---------------------------------------------------------------------------
# OpenCode generator
# ---------------------------------------------------------------------------
def generate_opencode(team: dict) -> None:
    log("")
    log("=== Generating OpenCode output ===")

    if OPENCODE_AGENTS_DIR.exists():
        shutil.rmtree(OPENCODE_AGENTS_DIR)
    agents_md = OPENCODE_DIR / "AGENTS.md"
    opencode_json = OPENCODE_DIR / "opencode.json"
    if agents_md.exists():
        agents_md.unlink()
    if opencode_json.exists():
        opencode_json.unlink()
    OPENCODE_AGENTS_DIR.mkdir(parents=True)

    # Per-skill symlinks filtered by applies_to
    if OPENCODE_SKILLS_DIR.is_symlink() or OPENCODE_SKILLS_DIR.exists():
        if OPENCODE_SKILLS_DIR.is_symlink() or OPENCODE_SKILLS_DIR.is_file():
            OPENCODE_SKILLS_DIR.unlink()
        else:
            shutil.rmtree(OPENCODE_SKILLS_DIR)
    OPENCODE_SKILLS_DIR.mkdir(parents=True)
    for skill_id in team["skills"]["order"]:
        skill = team["skills"]["items"][skill_id]
        if "opencode" not in skill.get("applies_to", []):
            continue
        link = OPENCODE_SKILLS_DIR / skill_id
        link.symlink_to(Path("../..") / "skills" / skill_id)
        log(f"Symlinked: {link} -> ../../skills/{skill_id}")

    # Subagents
    for agent_id in team["agents"]["order"]:
        agent = team["agents"]["items"][agent_id]
        src = SCRIPT_DIR / agent["instruction_file"]
        body = expand(load_body(src), OPENCODE_VARS)

        fm: dict[str, Any] = {
            "description": agent["description"],
            "mode": "subagent",
            "model": OPENCODE_MODEL_ID,
            "temperature": opencode_temperature_for_agent(agent),
            "steps": int(agent.get("max_turns", 25)),
            "permission": opencode_permission_block(agent),
        }

        dst = OPENCODE_AGENTS_DIR / f"{agent['name']}.md"
        dst.write_text(_assemble_markdown(_dump_opencode_frontmatter(fm).rstrip("\n"), body))
        log(f"Generated: {dst}")

    # Orchestrator primary agent (synthesized from orchestrate skill body)
    orchestrate_body = expand(load_body(ORCHESTRATE_SKILL), OPENCODE_VARS)
    orchestrator_fm = {
        "description": (
            "Primary orchestrator. Decomposes complex tasks and dispatches subagents in "
            "parallel waves. The default entrypoint for any non-trivial work — never "
            "implements directly."
        ),
        "mode": "primary",
        "model": OPENCODE_MODEL_ID,
        "temperature": 0.1,
        "steps": 50,
        "permission": {
            "edit": "deny",
            "write": "deny",
            "bash": "deny",
            "webfetch": "allow",
            "task": {"*": "allow"},
        },
    }
    orchestrator_path = OPENCODE_AGENTS_DIR / "orchestrator.md"
    orchestrator_path.write_text(
        _assemble_markdown(_dump_opencode_frontmatter(orchestrator_fm).rstrip("\n"), orchestrate_body)
    )
    log(f"Generated: {orchestrator_path}")

    # AGENTS.md
    log("")
    log("Generating opencode/AGENTS.md...")
    agents_md.write_text(_build_agents_md(team, "opencode"))
    log(f"Generated: {agents_md}")

    # opencode.json — merge base config with generated overlay
    log("")
    log("Generating opencode/opencode.json...")
    if not OPENCODE_BASE_CONFIG.exists():
        raise FileNotFoundError(f"missing base config at {OPENCODE_BASE_CONFIG}")
    base = json.loads(OPENCODE_BASE_CONFIG.read_text())
    overlay = {
        "permission": {
            "read": {
                "*": "allow",
                "**/*.log": "deny",
                "**/*.log.*": "deny",
                "**/syslog": "deny",
                "**/syslog.*": "deny",
                "**/dmesg": "deny",
                "**/dmesg.*": "deny",
                "**/kern.log*": "deny",
                "**/messages": "deny",
                "**/messages.*": "deny",
                "**/auth.log*": "deny",
                "**/journal/**": "deny",
            },
            "edit": "allow",
            "bash": {"*": "allow"},
            "webfetch": "allow",
            "skill": {"*": "allow"},
        },
        "compaction": {"auto": True, "prune": True},
        "snapshot": True,
    }
    merged = _deep_merge(base, overlay)
    opencode_json.write_text(json.dumps(merged, indent=2) + "\n")
    log(f"Generated: {opencode_json}")


def _build_agents_md(team: dict, harness: str) -> str:
    """Concatenate rule files for a harness, matching bash's `echo ""; cat` pattern.

    Bash did: echo header, then for each applicable rule, echo blank + cat file.
    `cat` preserves the file's own trailing whitespace, so trailing blank lines
    in a rule file become visible separators in the output. We replicate that
    by reading file contents verbatim rather than stripping.
    """
    out = "# Agent Team Instructions\n\nAgent-team specific protocols live in skills (orchestrate, conventions, worker-protocol, qa-checklist, message-schema).\n"
    for rule_id in team["rules"]["order"]:
        rule = team["rules"]["items"][rule_id]
        if harness not in rule.get("applies_to", []):
            continue
        out += "\n" + (SCRIPT_DIR / rule["source_file"]).read_text()
    return out


def _deep_merge(a: dict, b: dict) -> dict:
    """Deep-merge b into a, producing a new dict. Matches `jq -s '.[0] * .[1]'`."""
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _dump_opencode_frontmatter(fm: dict[str, Any]) -> str:
    """Opencode accepts YAML 1.2; use pyyaml with block style for nested maps."""
    # Use yaml.dump for the nested permission structure; top-level scalars we
    # want unquoted for parity with the current bash output where possible.
    out: list[str] = []
    for key, value in fm.items():
        if isinstance(value, dict):
            out.append(f"{key}:")
            for k, v in value.items():
                if isinstance(v, dict):
                    out.append(f"  {k}:")
                    for k2, v2 in v.items():
                        out.append(f'    "{k2}": {v2}')
                else:
                    out.append(f"  {k}: {v}")
        elif isinstance(value, str):
            # Description uses single quotes for parity; other strings unquoted.
            if key == "description":
                out.append(f"{key}: {_yaml_single_quoted(value)}")
            else:
                out.append(f"{key}: {value}")
        elif isinstance(value, bool):
            out.append(f"{key}: {'true' if value else 'false'}")
        else:
            out.append(f"{key}: {value}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    team = yaml.safe_load(TEAM_YAML.read_text())
    settings = yaml.safe_load(SETTINGS_SHARED_YAML.read_text())

    log(f"Using shared config: {SETTINGS_SHARED_YAML}")
    validate_protocol_files(team, settings)
    generate_legacy_settings_json(settings)
    log(f"Generated compatibility artifact: {SETTINGS_JSON}")

    generate_claude(team)
    generate_codex(team, settings)
    generate_opencode(team)

    log("")
    log("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
