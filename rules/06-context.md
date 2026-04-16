# Context Discipline for Large Files

**These rules are non-negotiable. Violating them will exhaust the context window and fail the task.**

- **Do not read log files or files larger than ~50 KB.** Ever. Use a search/grep tool to find matching lines, then read only a small window (±20 lines) around the hits if needed.
- **Do not paginate reads through a large file.** If a read returns "output capped" or "use offset to continue", STOP. Do not call read again with a higher offset. Switch to search/grep with a more specific pattern instead. Walking a file with repeated reads is the single fastest way to blow the context window.
- **Do not use shell commands that dump file contents** (`cat`, `head`, `tail`, `less`, `more`, `strings`, `xxd`, `od`) on logs or unknown large files. Shell output is not capped the same way as the read tool — it will flood context. Use the search tool.
- **One broad regex beats many narrow ones.** For triage, start with a single ripgrep union like `(?i)(panic|oops|segfault|error|fail|timeout|warn)` instead of issuing one call per keyword.
- **For unknown directories, list first, read last.** Start with a directory listing or glob to understand what's there. Do not recursively read.
- **When a search returns many hits, narrow the pattern or add a file filter.** Do not widen the search. Do not fall back to reading the source file in full.
