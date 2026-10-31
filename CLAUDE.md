# CLAUDE.md

Follow `AGENTS.md` for conventions and `README.md` for architecture. Project name: **BranchVerse**
(the working directory is still called GitScope).

## Commands
* Backend tests: `cd backend && .venv/Scripts/python -m pytest`
* Frontend: `cd frontend && pnpm test -- --run && pnpm build`
* Dev servers: see README "Run". Demo repo: `backend/.venv/Scripts/python fixtures/create_demo_repo.py`

## Working here
* Preserve read-only Git behaviour. If a feature seems to need a mutating Git command, don't build it.
* Run the relevant tests before saying something works; report failures with their output.
* Use `backend/.venv/Scripts/python`, not bare `python` (on this Windows machine `python` is the Store stub).
* The demo repo generator must never write inside a real repository.
* Key places: `backend/app/core/git_runner.py` (security choke point), `backend/app/services/`,
  `frontend/src/lib/graphLayout.ts` (graph algorithm), `frontend/src/lib/lessons.ts` (Learn content).
