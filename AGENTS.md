# AGENTS.md — BranchVerse conventions

See README.md for what the project is and how to run it. This file lists the rules for changing it.

## Architecture
* `backend/` FastAPI + Python 3.12. All Git access lives in `app/services/*` and goes through
  `app/core/git_runner.run_git`. `app/api` only routes; `app/schemas` are the Pydantic response models.
* `frontend/` React + TypeScript + Vite + Tailwind v4. Types in `src/types/git.ts` mirror the Pydantic schemas —
  change both together. Pure logic goes in `src/lib` (and gets a Vitest test).
* The browser never runs Git; the backend never renders UI.

## Dependencies
No Redux/Zustand, React Flow, D3, Axios, charting libraries, ORMs or databases. Prefer the standard library.

## Git safety (non-negotiable)
* Read-only. Subcommands are allow-listed in `READ_ONLY_SUBCOMMANDS`; never add a mutating one.
* Network use is limited to `git_runner.clone_bare`, `git_runner.fetch_pull_ref` (both only inside `CACHE_ROOT`) and the
  single fixed `github_api.fetch_pull_meta` URL. Keep them restricted to values rebuilt from `parse_github_url` and
  validated integers; never widen protocols or hosts. Treat API responses as untrusted (`clean_pull`).
* Prefer `iter_git` (streaming) for potentially large outputs and `core.cache.cached` for expensive read-only results.
* Never use a shell or string-built commands. Never pass client text as a revision: SHAs are validated
  (`validate_sha`) and refs/paths are checked against what the repository itself reports. Use `--` before paths.
* Keep timeouts and output caps on every call; paginate anything unbounded.
* Render repository content as text only.

## Style
* Python: type hints, small functions, domain errors from `app/core/errors.py` (never leak stderr/tracebacks).
* TypeScript: strict, `import type`, files ≲150 lines, no `any`, no `dangerouslySetInnerHTML`.

## Testing
Tests use real temporary repos (`backend/tests/conftest.py`, `fixtures/create_demo_repo.py`) — do not mock Git.
New endpoints need service tests, and security-relevant changes need a test in `test_security.py`.
