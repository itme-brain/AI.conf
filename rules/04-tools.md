# Tool & Approach Philosophy

- Use tools and solutions that are declarative and reproducible over imperative one-offs
- Portability across dev environments is a first-class concern — avoid hardcoding machine-specific paths or assumptions
- The right tool for the job is the right tool — no language/framework bias, and prioritize tools that are version-pinned and reproducible

# Nix

- Nix is the meta package manager on all systems — assume it is available even on non-NixOS Linux
- Use a project-level `flake.nix` as the canonical way to define dev environments, build systems, and scripts
- Dev environments go in `devShells`, project scripts/tools go in `packages` or as `apps` within the flake
- Never suggest `apt`, `brew`, `pip install --user`, `npm install -g`, or other imperative global installs — reach for `nix shell`, `nix run`, or the project devshell instead
- Use `nix run` for one-off tool invocations and `nix develop` (or `direnv` + `use flake`) for persistent dev shells
- Binaries and tools introduced to a project MUST be pinned and run through Nix, not assumed to be on `$PATH` from the host
- Flakes are the required interface — avoid legacy `nix-env` or channel-based patterns

# Developer Workflows

- When scaffolding a project, you MUST include `just` as standard developer tooling and make it the user-facing UX for common development workflows
- Commonly run development workflows MUST be wired into `just` recipes as the user-facing entrypoints
- Temporary artifacts created during work MUST be cleaned up before completion unless the user explicitly asked to keep them

