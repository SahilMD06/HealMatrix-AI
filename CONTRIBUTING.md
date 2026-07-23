# Contributing to HealMatrix AI

## Getting set up

```bash
git clone <repo>
cd HealMatrix-AI
cp .env.example .env          # fill in GOOGLE_API_KEY at minimum
docker compose up --build     # API on :8000, UI on :5173
```

Or run each side locally without Docker — see the README's Quick Start (section 7) for the
`venv`/`npm install` steps. Either way, seed some data before you rely on any dashboard showing
something other than empty states:

```bash
docker compose exec backend python /scripts/seed_database.py --force
```

## Before opening a PR

Both of these are exactly what CI runs (`.github/workflows/ci.yml`), so a green local run means
a green PR:

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
ruff check app tests
pytest -q

# Frontend
cd frontend
npm install
npm run lint
npm test
npm run build
```

If you touched the agents (`backend/app/agents/`), run the full suite, not just the file you
changed — `tests/unit/test_agents_guardrails.py` and `tests/integration/test_agent_cycle.py`
catch cross-agent regressions (a changed message payload, a state key silently dropped by
LangGraph) that a single agent's own tests won't.

## Code style

- **Backend:** `ruff` is the only formatter/linter (`pyproject.toml`'s `[tool.ruff]`); there is
  no separate `black`/`isort` step. Type hints are expected on every function signature.
- **Frontend:** `eslint` + `prettier` (`npm run lint`, `npm run format`). JavaScript, not
  TypeScript — this is a deliberate project constraint (see `docs/02_system_architecture.md`
  ADR-6), not an oversight; please don't introduce `.ts`/`.tsx` files.
- Both sides: prefer an explicit, slightly verbose name over a clever short one. Every module
  in this codebase carries a docstring explaining *why* it exists, not just what it does —
  match that when you add a new one.

## Adding a new agent or endpoint

- Agents: read `docs/04_agent_design.md` first. Every agent implements `BaseAgent`
  (`analyse()` + `fallback()`), and the fallback path must never raise and must never touch the
  network — it is what runs with no `GOOGLE_API_KEY` configured, which is this project's
  default operating mode, not an edge case. Add it to `app/agents/graph/builder.py`'s
  `build_graph()` if it belongs in one of the three trigger branches, and write at minimum a
  fallback test (`tests/unit/test_agents_fallback.py`) and, if it has a guardrail, a guardrail
  test (`tests/unit/test_agents_guardrails.py`).
- Endpoints: add the route, then update `docs/05_api_specification.md`'s catalogue in the same
  PR. That document is meant to describe the *running* API, not an aspiration — Phase 1's
  original version drifted from the implementation for exactly this reason, and
  `docs/00_phase3_verification.md` records what it took to reconcile it.

## Reporting a bug

Open an issue with: what you ran, what you expected, what happened instead, and — if it's a
backend issue — the `correlation_id` from the response's error envelope or the `X-Correlation-ID`
response header, which pinpoints the exact log line.

## License

By contributing, you agree your contribution is licensed under this repository's MIT license
(see `LICENSE`).
