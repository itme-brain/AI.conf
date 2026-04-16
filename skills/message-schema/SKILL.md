---
name: message-schema
description: Typed envelope schema for all inter-agent communication. Defines message types, required fields, and signal routing contracts.
when_to_use: Automatically loaded by all agents and the orchestrator via skills frontmatter. Reference when producing or consuming agent output.
---

Every agent output and orchestrator dispatch uses a **YAML frontmatter envelope** followed by a **markdown body**. The envelope contains routing metadata; the body contains human-readable content.

```
---
type: <message_type>
signal: <routing_signal>
# ... type-specific fields
---

[markdown body]
```

The `signal` field is the orchestrator's primary routing key. It determines the next action without parsing prose.

---

## Signals

### Agent → Orchestrator

| Signal | Meaning | Emitted by |
|--------|---------|------------|
| `rfr` | Work complete, ready for review | worker, debugger, documenter |
| `pass` | Review/audit passed cleanly | reviewer, auditor |
| `pass_with_notes` | Passed with non-blocking findings | reviewer, auditor |
| `fail` | Review/audit failed, needs rework | reviewer, auditor |
| `triage_complete` | Triage done, research questions identified (or none) | architect |
| `plan_complete` | Plan written to file | architect |
| `research_complete` | Research question answered | researcher |
| `blocked` | Cannot proceed, needs orchestrator intervention | any agent |
| `escalate` | Beyond agent scope, needs user decision | any agent |

### Orchestrator → Agent

| Signal | Meaning | Sent to |
|--------|---------|---------|
| `execute` | Perform this task | worker, debugger, documenter, architect |
| `revise` | Fix listed issues and resubmit | worker, debugger, documenter |
| `lgtm` | Approved, commit now | worker, debugger, documenter |
| `research` | Answer this research question | researcher |
| `plan` | Produce architecture and wave decomposition | architect |

---

## Agent → Orchestrator Message Types

### worker_submission

Emitted by: grunt, worker, senior, debugger, documenter

```yaml
---
type: worker_submission
signal: rfr | blocked | escalate
files_changed:
  - path/to/file1
  - path/to/file2
ac_coverage:
  AC1: pass | fail | partial | na
  AC2: pass | fail | partial | na
qa_check: pass | fail
---
```

Required: `type`, `signal`, `files_changed`, `qa_check`
Optional: `ac_coverage` (omit when no AC provided in assignment)

Body: `## Result` section with implementation details, then `## Self-Assessment` with per-criterion notes and known limitations.

**Routing contract for implementers:**
- `grunt` uses `blocked` to request reassignment to `worker` or orchestrator intervention.
- `worker` uses `blocked` to request reassignment to `senior` or orchestrator intervention.
- `senior` uses `blocked` to request orchestrator re-decomposition, plan revision, or a senior wave/team.
- Any implementer uses `escalate` only when the blocker requires a user decision or approval, not merely a stronger implementer.

When `signal: blocked` or `signal: escalate` is used, the body must include a one-line route hint:
- `Route: worker`
- `Route: senior`
- `Route: orchestrator`
- `Route: orchestrator (re-decompose)`
- `Route: orchestrator (user decision required)`

### review_verdict

Emitted by: reviewer

```yaml
---
type: review_verdict
signal: pass | pass_with_notes | fail
critical_count: 0
moderate_count: 2
minor_count: 1
ac_coverage:
  AC1: pass | fail
  AC2: pass | fail
---
```

Required: `type`, `signal`, `critical_count`, `moderate_count`, `minor_count`
Optional: `ac_coverage` (omit when no acceptance criteria were provided in the assignment)

**Hard rule:** `critical_count > 0` requires `signal: fail`.

Body: Findings by severity (CRITICAL / MODERATE / MINOR), then AC Coverage details when applicable, then one-line summary.

### audit_verdict

Emitted by: auditor

```yaml
---
type: audit_verdict
signal: pass | pass_with_notes | fail
security_findings:
  critical: 0
  high: 0
  medium: 0
  low: 0
build_status: pass | fail | skipped
test_status: pass | fail | partial | skipped
typecheck_status: pass | fail | skipped
---
```

Required: `type`, `signal`, `security_findings`, `build_status`, `test_status`
Optional: `typecheck_status`

**Hard rule:** `security_findings.critical > 0` or `security_findings.high > 0` or `build_status: fail` or `test_status: fail` requires `signal: fail`.

Body: Security findings by severity (or CLEAN), then Runtime section with tested/passed/failed.

### triage_result

Emitted by: architect (Phase 1)

```yaml
---
type: triage_result
signal: triage_complete
tier: 0 | 1 | 2 | 3
research_needed: true | false
research_count: 3
---
```

Required: `type`, `signal`, `tier`, `research_needed`
Optional: `research_count` (present when `research_needed: true`)

**Routing:** `research_needed: false` means the orchestrator skips research and resumes architect directly for Phase 2.

Body: Triage section (Tier, Problem, Constraints, Success criteria, Out of scope), then Research Questions if any.

### plan_result

Emitted by: architect (Phase 2)

```yaml
---
type: plan_result
signal: plan_complete | blocked
plan_file: plans/kebab-case-title.md
wave_count: 3
step_count: 7
risk_tags:
  - security
  - data-mutation
has_blockers: false
---
```

Required: `type`, `signal`, `plan_file`, `wave_count`, `risk_tags`, `has_blockers`
Optional: `step_count`

**Routing:** `has_blockers: true` triggers user escalation before worker dispatch.

Body: One-paragraph summary of what the plan covers.

### research_result

Emitted by: researcher

```yaml
---
type: research_result
signal: research_complete
topic: "brief topic identifier"
verified: true | false
has_gotchas: true | false
---
```

Required: `type`, `signal`, `topic`, `verified`
Optional: `has_gotchas`

**Routing:** `verified: false` flags unverified assumptions to the architect before planning.

Body: Answer, Verified Facts with sources, Version Constraints, Gotchas, Unverified claims.

---

## Orchestrator → Agent Message Types

### task_assignment

Sent to: grunt, worker, senior, debugger, documenter

```yaml
---
type: task_assignment
signal: execute
task: "short task title"
plan_file: plans/kebab-case-title.md
wave: 1
step: 2
---
```

Required: `type`, `signal`
Optional: `task`, `plan_file`, `wave`, `step` (Tier 0 tasks may lack plan context)

Body: Task spec, Acceptance Criteria, Context (interface contracts, constraints, out-of-scope), Files to modify/read.

### revision_request

Sent to: grunt, worker, senior, debugger, documenter

```yaml
---
type: revision_request
signal: revise
iteration: 2
max_iterations: 5
fix_severity: critical | critical+moderate | all
---
```

Required: `type`, `signal`, `iteration`
Optional: `max_iterations`, `fix_severity`

`fix_severity` maps to iteration: 1-3 = `all`, 4-5 = `critical`.

Body: Issues to fix (from reviewer and/or auditor), grouped by source, with guidance.

### approval

Sent to: grunt, worker, senior, debugger, documenter

```yaml
---
type: approval
signal: lgtm
---
```

Required: `type`, `signal`. Pure control signal — commit using conventional commit format.

### triage_request

Sent to: architect (Phase 1)

```yaml
---
type: triage_request
signal: execute
---
```

Required: `type`, `signal`

Body: Raw user request and any relevant project context.

### architecture_request

Sent to: architect (Phase 2, resume)

```yaml
---
type: architecture_request
signal: plan
---
```

Required: `type`, `signal`

Body: Assembled `## Research Context` block from all researchers, or "No research needed — proceed."

### research_request

Sent to: researcher

```yaml
---
type: research_request
signal: research
topic: "brief topic identifier"
---
```

Required: `type`, `signal`, `topic`

Body: Specific question, why it matters (what decision it gates), where to look, relevant project context.

---

## Schema Compliance

Before returning output, verify:

1. Output starts with a valid YAML frontmatter envelope (`---` delimiters)
2. `type` matches your message type
3. `signal` uses a valid enum value for your direction (agent→orch or orch→agent)
4. All required fields for your message type are present
5. Enum fields use exact values from this schema (no variations like "PASS" vs "pass")
6. Hard rules are satisfied (e.g., `critical_count > 0` implies `signal: fail`)
