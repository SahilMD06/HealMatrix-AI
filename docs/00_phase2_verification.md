# Phase 2 Verification Report

Date: 2026-07-21 · Scope: auth, repositories, services, routers, simulator

## Result

**98 tests passing, lint clean.** The suite runs against an in-memory MongoDB
(`mongomock-motor`), so it needs no running database and executes in CI in under two
seconds.

```
backend/tests/unit/test_triage_rules.py      37 tests
backend/tests/unit/test_simulator.py         19 tests
backend/tests/api/test_auth.py               16 tests
backend/tests/api/test_clinical_flow.py      16 tests
backend/tests/api/test_agents_and_analytics.py 10 tests
                                             ──────────
                                             98 passed
```

## Bugs Found and Fixed During Verification

Verification was worth doing — it caught four defects that would each have surfaced
during a live demo.

### 1. Clinical under-triage (severity: high)

A patient presenting with shock index 1.23, SpO₂ 92 %, respiratory rate 26 and pain
8/10 — a textbook time-critical cardiac presentation — was being triaged **ESI 3
(Urgent)** instead of **ESI 2 (Emergent)**, giving a 30-minute target response instead
of 10 minutes.

Two causes:
- The SpO₂ scoring band was `< 92`, so a reading of exactly 92 % fell through to the
  mildest band. 93 % is the recognised concern threshold in adult triage, so the band
  now sits there.
- The ESI 2 cut-off was set at 8.0, which was too strict. It is now 7.5. In emergency
  medicine under-triage is the dangerous error, so the bands are deliberately biased
  toward escalation.

Regression test: `test_cardiac_case_is_emergent_not_urgent`.

### 2. Stroke routing gap (severity: high)

`suggest_department()` matched the literal word "stroke" but not "weakness of the
right side" — which is how a stroke is actually described on arrival. The case was
routed to General Medicine rather than Neurology. Laterality phrases, slurred speech,
facial droop and numbness are now matched explicitly.

Regression test: `test_complaint_maps_to_department[Sudden weakness of the right side-NEURO]`.

### 3. 500 error on any custom validation failure (severity: high)

`serialise()` only converted top-level `ObjectId` values. Nested identifiers — such as
`triage.recommended_department_id` and the embedded `occupancy_history` array — reached
Pydantic unconverted and raised `PydanticSerializationError`, producing a 500 on
`/admissions/queue`. The serialiser is now recursive.

Separately, the `RequestValidationError` handler passed Pydantic's raw error list
straight into `JSONResponse`. When a custom field validator raises, Pydantic puts the
exception *instance* in `ctx`, which is not JSON-serialisable — so every custom
validation failure returned 500 instead of 422. Error entries are now sanitised.

Regression tests: `test_queue_is_enriched_for_display`, `test_weak_password_is_rejected`.

### 4. Tooling: Python version mismatch

`ruff --fix` rewrote `timezone.utc` to `datetime.UTC` (3.11+). The project targets
3.11, but pinning to it would have made the suite unrunnable on 3.10 tooling. `UP017`
is now disabled with a documented reason, keeping CI-green equivalent to
locally-verified.

## What the Tests Actually Prove

| Property | Test |
|----------|------|
| Red flags always force ESI 1, whatever the score says | `test_red_flags_always_force_esi_one` |
| A maintenance bed is never assigned by any code path | `test_maintenance_bed_is_never_assigned` |
| A monitored bed is chosen for high acuity, a general bed for low | `test_critical_arrival_is_triaged_and_allocated` |
| The triage queue is ordered by acuity, not arrival order | `test_queue_is_ordered_by_acuity` |
| One hospital cannot read another's data, even by explicit request | `test_cannot_request_another_hospitals_data` |
| Login cannot be used to enumerate valid accounts | `test_unknown_email_gives_identical_error` |
| An access token cannot be replayed at the refresh endpoint | `test_access_token_cannot_be_used_to_refresh` |
| Every agent decision records its inputs, rationale and confidence | `test_trace_entries_are_auditable` |
| Discharge frees the bed and records realised length of stay | `test_discharge_closes_admission_and_frees_bed` |
| Double discharge is rejected rather than silently repeated | `test_double_discharge_is_rejected` |
| Identical seeds regenerate identical simulated history | `test_same_seed_produces_identical_arrivals` |
| The simulator reproduces the evening ED peak and monsoon disease shift | `test_evening_is_busier_than_pre_dawn`, `test_monsoon_shifts_the_disease_mix` |
| Generated vitals always satisfy the Pydantic ranges | `test_vitals_stay_within_model_bounds` |
| Recycling is credited as avoided emissions | `test_recycling_is_credited_as_avoided_emissions` |

## Reproducing

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q          # 98 passed
ruff check app tests
```

## Deferred to Phase 3

The triage and bed decisions currently run through the **deterministic rule engine**,
which is the documented fallback path. Phase 3 adds the XGBoost models and Gemini
rationale on top, with these rules remaining as the guardrail and the offline path.
Agents 3–10 and the LangGraph orchestrator are not yet implemented; `/agents/status`
reports them honestly as `implemented: false` rather than faking activity.
