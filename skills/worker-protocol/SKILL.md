---
name: worker-protocol
description: Standard output format, feedback handling, and operational procedures for all worker agents.
when_to_use: Loaded by grunt, worker, senior, debugger, and documenter agents. Defines the worker_submission envelope format and commit workflow.
---

## Output format

Wrap your output in a `worker_submission` envelope per the message-schema skill:

```yaml
---
type: worker_submission
signal: rfr | blocked | escalate
files_changed:
  - path/to/file1
  - path/to/file2
ac_coverage:                          # optional — omit when no AC provided
  AC1: pass | fail | partial | na
  AC2: pass | fail | partial | na
qa_check: pass | fail
---
```

Then the markdown body:

```
## Result
[Your deliverable here]

## Self-Assessment
- Acceptance criteria met: [yes/no per criterion, one line each, or "No acceptance criteria were provided"]
- Known limitations: [any, or "none"]
```

## Your job

Produce the assigned deliverable. Accurately. Completely. Nothing more.

- Exactly what was asked. No unrequested additions.
- When uncertain about a specific fact, verify. Otherwise trust context and training.

## Self-QA

Before returning your output, run the `qa-checklist` skill against your work. Fix any issues you find — don't just note them. Set `qa_check: pass` or `qa_check: fail` in your frontmatter envelope. If you can't pass your own QA, flag what remains and why in your Self-Assessment.

## Cost sensitivity

- Keep responses tight. Result only.
- Context is passed inline, but if your task requires reading files not provided, verify by reading the relevant files. Don't guess at file contents. Keep it targeted.

## Commits

Do not commit until your orchestrator sends `signal: lgtm`.

- `signal: rfr` — you → orchestrator: work complete, ready for review
- `signal: lgtm` — orchestrator → you: approved, commit now
- `signal: revise` — orchestrator → you: needs fixes (issues attached)

When you receive `LGTM`:
- Commit using conventional commit format per project conventions
- One commit per logical change
- Include only files relevant to your task

## Operational failures

If blocked (tool failure, missing file, build error): try to work around it and note the workaround. If truly blocked, report to your orchestrator with what failed and what you need. No unexplained partial work.

## Receiving reviewer feedback

Your orchestrator may resume you with findings from the reviewer (code quality + AC verification) or the auditor (security + runtime validation), or both.

You already have the task context and your previous work. Address the issues specified. If feedback conflicts with the original requirements, flag to your orchestrator — don't guess. Resubmit complete output in standard format. In Self-Assessment, note which issues you addressed and reference the reviewer or auditor for each.
