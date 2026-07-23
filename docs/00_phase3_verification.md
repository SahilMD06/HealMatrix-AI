# Phase 3–6 Verification Report

Date: 2026-07-23 · Scope: agents, LangGraph/CrewAI orchestration, RAG, remaining dashboards,
frontend testing, deployment configuration

This report covers four phases together rather than one apiece because they were built and
verified as one continuous arc: the agent framework (Phase 3) is what the four new dashboards
(Phase 5) render, and the test suite plus deployment configuration (Phase 6) verifies both at
once. Splitting them into separate reports would mean re-describing the same test runs three
times.

## Result

**188 backend tests, 21 frontend tests — all passing.** The backend suite still runs entirely
against an in-memory MongoDB (`mongomock-motor`) with no `GOOGLE_API_KEY` configured, so every
agent's deterministic fallback path is what CI actually exercises; the frontend suite runs
under Vitest + Testing Library with a mocked API layer, so it needs no backend running either.

```
backend/tests/unit/test_triage_rules.py          37 tests   (Phase 2, unchanged)
backend/tests/unit/test_simulator.py             19 tests   (Phase 2, unchanged)
backend/tests/api/test_auth.py                   16 tests   (Phase 2, unchanged)
backend/tests/api/test_clinical_flow.py          16 tests   (Phase 2, unchanged)
backend/tests/api/test_agents_and_analytics.py   10 tests   (Phase 2, unchanged)
backend/tests/unit/test_agents_fallback.py       13 tests   (Phase 3)
backend/tests/unit/test_agents_guardrails.py     25 tests   (Phase 3)
backend/tests/unit/test_agents_contract.py       20 tests   (Phase 3)
backend/tests/unit/test_agents_determinism.py     4 tests   (Phase 3)
backend/tests/unit/test_graph_routing.py         11 tests   (Phase 3)
backend/tests/integration/test_agent_cycle.py     5 tests   (Phase 3)
backend/tests/api/test_sustainability_and_admin.py 12 tests (Phase 5)
                                                 ──────────
                                                 188 passed

frontend/src/components/ui/Badge.test.jsx         5 tests   (Phase 6)
frontend/src/components/ui/StatCard.test.jsx      7 tests   (Phase 6)
frontend/src/hooks/useApi.test.js                 5 tests   (Phase 6)
frontend/src/pages/dashboards/InventoryDashboard.test.jsx 4 tests (Phase 6)
                                                 ──────────
                                                  21 passed
```

## Bugs Found and Fixed During Verification

Four genuine defects, each caught by actually executing the agent code end-to-end (with fakes
standing in for the database) rather than by reading it — the same lesson Phase 2's
verification drew, holding a second time.

### 1. LangGraph silently drops any state key not declared in the shared `TypedDict`

The initial `HealMatrixState` only declared the handful of keys the `patient_arrival` branch
needed. Invoking the compiled graph with a richer `scheduled_cycle` state (hourly energy
history, recent admission counts, and so on) made every sustainability agent fail with
"insufficient data" — not because the data wasn't passed in, but because LangGraph's state
reducer filters out any key the `TypedDict` doesn't declare *before* a node ever sees it. This
is not documented anywhere obvious in LangGraph's own materials and would have been a
genuinely confusing production incident. Fixed by declaring every field each agent's
`analyse()` reads via `state.get(...)` in `app/agents/state.py`.

### 2. Disease Forecast Agent's outbreak detector had a self-referential baseline

The 2-sigma-over-baseline outbreak test computed its baseline mean/std from the same trailing
window used to seed the forecast. An injected admissions spike inflated its own baseline along
with the forecast, so the outbreak threshold could never be crossed — the alarm was
structurally incapable of firing on the exact case it exists to catch. Fixed by computing the
baseline from the period *before* the lag window (`history[:-ADMISSIONS_LAG_DAYS]`) once
enough history exists, so a recent spike is judged against what came before it, not against
itself.

### 3. Biomedical Waste Agent's keyword fallback matched on generic prose, not defining vocabulary

The deterministic classification fallback did naive word-overlap against each CPCB category's
full descriptive text. Because those descriptions share common words ("waste", "material"),
an ambiguous description could match a category on incidental overlap rather than genuine
category-defining content. Fixed by replacing free-text overlap with `CATEGORY_KEYWORDS` — a
curated set of nouns each category is actually defined by — so an ambiguous description now
correctly falls through to `requires_manual_review` instead of guessing.

### 4. Executive Crew's critical-stockout filter was not valid logic

`[sku for sku in medicine.get(...).get("stockout_risk") == "high" and [...] or []]` is a
boolean short-circuit expression misused inside a list comprehension — it does not do what it
looks like it does. Fixed to a plain filter: `[row["sku"] for row in low_stock_alerts if
row.get("is_critical")]`.

## What the Tests Actually Prove

| Property | Test |
|----------|------|
| Red-flag vitals force ESI 1 whether the trained model ran or the rule engine did | `test_red_flags_force_esi_one_via_the_trained_model_path`, `test_red_flags_force_esi_one_via_the_rule_engine_fallback_path` |
| OT/ICU HVAC setpoints never leave 20–24 °C, at any outside temperature | `test_recommended_setpoints_never_leave_clinical_limits`, `test_ot_and_icu_are_hard_clamped_to_20_24` |
| An unsafe HVAC candidate is discarded outright, not clamped into range | `test_an_unsafe_candidate_is_discarded_not_clamped` |
| A maintenance bed is never recommended, at any acuity level | `test_maintenance_bed_is_never_recommended` |
| A cold-chain medicine transfer needs every link (donor, recipient, route) capable — one gap blocks it | `TestColdChainGuardrail` (5 tests) |
| Waste classification never guesses without grounding evidence above threshold | `test_no_supporting_evidence_yields_manual_review` |
| Every agent's fallback returns a valid, schema-complete `AgentResult` with the LLM fully disabled | `test_fallback_output_carries_every_required_key` (parametrised over all 10 agents) |
| Carbon Intelligence produces byte-identical output for identical inputs | `test_repeated_runs_on_the_same_agent_are_byte_identical`, `test_fresh_agent_instances_agree` |
| The compiled graph is a DAG — no cycle can hang a scheduled Celery run | `test_the_compiled_graph_is_a_dag` |
| A full `patient_arrival` run writes exactly one `agent_logs` document per executed agent | `test_exactly_one_agent_log_per_executed_agent` |
| A manual `POST /agents/run-cycle` produces a real executive synthesis and appears in the audit trail | `test_admin_can_trigger_a_cycle_run`, `test_a_manual_run_appears_in_the_agent_logs` |
| The staff roster never leaks a password hash and is scoped to the caller's hospital | `test_roster_never_leaks_password_hashes`, `test_roster_is_scoped_to_the_callers_hospital` |
| `useApi` surfaces the normalised error shape and stops fetching when disabled | `useApi.test.js` (5 tests) |
| A dashboard renders real headline KPIs and an honest empty state when there is nothing to show | `InventoryDashboard.test.jsx` (4 tests) |

## Environment Issues Encountered (not code defects)

Worth recording since they cost real time and would recur for anyone else on this exact setup:

- **bcrypt/passlib version mismatch.** The verification sandbox had `bcrypt==5.0.0` installed,
  which removed the `__about__` attribute `passlib==1.7.4` reads, and separately enforces a
  strict 72-byte password limit that older bcrypt silently truncated. `backend/requirements.txt`
  already pins `bcrypt==4.0.1` with a comment explaining exactly this — the fix was reinstalling
  to the pinned version, not a code change.
- **Corrupted `node_modules` under the Windows-mounted project folder.** `npm install` failed
  with `ENOTEMPTY` renaming `ajv`, and `rm -rf` on files already written there returned
  `Operation not permitted` — the mount enforces a write-once policy on existing files.
  Frontend build/lint/test verification was done from a clean scratch copy instead; this does
  not affect the real repository, only where verification had to run.

## Reproducing

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
pytest -q                  # 188 passed
ruff check app tests

# Train the ML artifacts first if app/ml/artifacts/*.joblib is missing —
# the triage and admissions-forecast agents fall back to the rule engine
# and seasonal-naive forecast respectively without them, which is safe but
# not what most of the guardrail tests are designed to exercise:
python -m app.ml.training.train_triage_model
python -m app.ml.training.train_admissions_forecast

# Frontend
cd frontend
npm install
npm test                   # 21 passed
npm run lint
npm run build
```

## Deferred to Phase 7 / 8

`docs/05_api_specification.md` has been rewritten against the real, running API (it previously
described a Phase-1 aspirational surface — pharmacy CRUD, ambulance dispatch routes, a
reports/notifications layer, rate limiting — none of which this build ships; see that
document's section 3 for the full list of what was descoped and why). Remaining: the pitch
materials (PPT, Lean Canvas, concept note, poster, demo script) that make up Phase 8.
