# API Specification
## HealMatrix AI REST API · `/api/v1`

Version 2.0 · Interactive documentation is served at `/docs` (Swagger) and `/redoc`.

> **Note on this revision.** Version 1.0 of this document was written during Phase 1, before
> any endpoint existed, and described an idealised full surface (pharmacy CRUD, ambulance
> dispatch routes, a reports/notifications/WebSocket layer, a RAG assistant endpoint). Building
> through Phases 2–6 made different scope calls — some of that surface was never needed for the
> vertical slices actually built, some of it is served by an agent rather than a dedicated route.
> This revision documents **what the running API actually does**, catalogued directly from
> `backend/app/api/v1/`, with a closing section listing what Version 1.0 promised that this
> build does not ship, so nothing here overstates the system.

---

## 1. Conventions

- **Base URL:** `https://<host>/api/v1`
- **Auth:** `Authorization: Bearer <access_token>` on every endpoint except those marked *public*
- **Tenancy:** `hospital_id` is derived from the token. Network admins and managers may pass
  `?hospital_id=` to cross scope; all other roles receive `403 tenant_isolation_violation` if
  they try (see `app/api/deps.py`'s `resolve_hospital_id`).
- **Pagination:** `?skip=0&limit=50&sort_by=created_at&sort_desc=true` (`app/api/deps.py`'s
  `get_pagination`), applied consistently across every list endpoint that accepts it.
- **Correlation:** every response carries `X-Correlation-ID` (echoed from the request header if
  supplied, otherwise generated) and `X-Process-Time-Ms`.

**Error envelope** (every non-2xx response, see `app/main.py`'s exception handlers):

```json
{
  "error": {
    "code": "bed_unavailable",
    "message": "No suitable bed is currently available.",
    "details": { "esi_level": 1 },
    "correlation_id": "3f9c1b7e-..."
  }
}
```

**Status codes actually in use:** 200 OK · 201 Created · 204 No Content · 400 · 401 · 403 ·
404 · 409 · 422 · 500. There is no 429/rate-limiting middleware and no 502/503 from the API
layer itself (503 is only ever returned by `/health/ready` reporting a downstream dependency
as down, not by a business endpoint).

---

## 2. Endpoint Catalogue

### 2.1 Meta *(public, no `/api/v1` prefix)*
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Service banner (name, version, environment) |
| GET | `/health` | Liveness — always 200 once the process is running |
| GET | `/health/ready` | Readiness: MongoDB reachability and whether Gemini is configured |

### 2.2 Authentication `/auth`
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| POST | `/auth/register` | admin | Create a user account (no public self-registration) |
| POST | `/auth/login` | *public* | Issue an access + refresh token pair |
| POST | `/auth/refresh` | *public* | Exchange a refresh token for a new access token |
| GET | `/auth/me` | any | Current user's profile |
| PATCH | `/auth/me` | any | Update profile (name, phone, avatar, theme, default dashboard) |
| POST | `/auth/change-password` | any | Change own password |
| GET | `/auth/users` | admin, manager | Staff roster for the caller's hospital (Admin Dashboard) |

There is no `POST /auth/logout` — access tokens are short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`)
and the client simply discards both tokens; nothing server-side needs revoking for this build's
threat model.

### 2.3 Hospitals & Organisation
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/hospitals` | any | Every active hospital in the network |
| POST | `/hospitals` | admin | Add a hospital |
| GET | `/hospitals/{id}` | any | Hospital detail |
| GET | `/departments` | any | Active departments for the caller's hospital |

There is no `PATCH /hospitals/{id}`, no department creation route, and no `/rooms` or `/staff`
endpoints — rooms are only ever read as part of a bed record, and staff duty rosters were
descoped in favour of the simpler `/auth/users` read-only roster above.

### 2.4 Clinical — Patients & Admissions
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/patients` | doctor, nurse, admin, manager | Paginated list |
| POST | `/patients` | doctor, nurse, admin | Register a patient |
| GET | `/patients/{id}` | doctor, nurse, admin, manager | Patient detail |
| POST | `/admissions/arrival` | doctor, nurse, admin | **Arrival → runs the Patient Triage and Bed Allocation agents synchronously** |
| GET | `/admissions/queue` | doctor, nurse, admin, manager | Live queue, ordered by acuity then wait time |
| GET | `/admissions` | doctor, nurse, admin, manager | Filter by `status`, `department_id`, `esi_level` |
| GET | `/admissions/{id}` | doctor, nurse, admin, manager | Detail, with the patient embedded |
| PATCH | `/admissions/{id}/status` | doctor, nurse, admin | Manual status transition |
| POST | `/admissions/{id}/discharge` | doctor, admin | Discharge, release the bed, record length of stay |

`POST /admissions/arrival` is synchronous, not queued: the response already contains the
finished triage decision and bed assignment (or the reasons neither could complete), because
`AdmissionService.handle_arrival` awaits the LangGraph `patient_arrival` branch before
responding — there is no separate polling step and no `202 Accepted` path for this endpoint.

### 2.5 Beds
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/beds` | any | List, optionally filtered by `status`/`type` |
| GET | `/beds/availability` | any | Assignable beds only (available, unoccupied) |
| GET | `/beds/occupancy-summary` | any | Occupancy KPIs, network- or department-level |
| POST | `/beds/{id}/reserve` | doctor, nurse, admin | Hold a bed for 30 minutes |
| POST | `/beds/{id}/release` | doctor, nurse, admin | Release to cleaning on discharge |
| PATCH | `/beds/{id}/status` | nurse, admin | Manual status override (e.g. maintenance) |

There is no direct `POST /beds/{id}/assign` — assignment only happens as part of
`POST /admissions/arrival`'s transaction, which is a deliberate design choice (see
`docs/04_agent_design.md`): a bed cannot be occupied without an admission document to attach it
to, so the two writes are never exposed as independently callable steps.

### 2.6 Sustainability `/sustainability`
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/sustainability/summary` | any | Energy/water/waste totals plus the Carbon Intelligence Agent's live emissions and sustainability score |
| GET | `/sustainability/energy-history` | any | Hourly energy consumption and source mix, trailing week |
| GET | `/sustainability/water-history` | any | Hourly water consumption and leak probability, trailing week |
| GET | `/sustainability/waste-history` | any | Daily waste generation by category and disposal method |

`/sustainability/summary` runs `CarbonIntelligenceAgent` inline on every call rather than
reading a cached figure — it is pure, deterministic arithmetic with no LLM and no external I/O
of its own (see `app/agents/carbon_agent.py`), so recomputing it per request is correct, not
wasteful.

### 2.7 Agents `/agents`
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/agents/status` | any | Per-agent run count, average latency, fallback/failure rate |
| GET | `/agents/runs` | any | Recent runs, grouped by `run_id` |
| GET | `/agents/runs/{run_id}` | any | Every agent's full reasoning trace for one run |
| GET | `/agents/logs` | admin, manager | Raw, unaggregated `agent_logs` feed |
| POST | `/agents/run-cycle` | admin, manager, sustainability_officer | Runs the full `scheduled_cycle` graph now (disease forecast → medicine → energy → water → waste → carbon → executive synthesis), instead of waiting for the next hourly Celery beat tick |

There is no per-agent `POST /agents/{name}/invoke` — every agent only ever runs as a node inside
one of the three LangGraph branches (`patient_arrival`, `scheduled_cycle`, the ambulance-dispatch
manual trigger), never in isolation, so there is nothing meaningful for a route to invoke alone.
There is also no `/assistant/query` or `/assistant/voice` — the RAG pipeline
(`app/rag/retriever.py`) is consumed today only by the Biomedical Waste Agent internally, not
exposed as a general-purpose Q&A endpoint.

### 2.8 Analytics `/analytics`
| Method | Path | Roles | Purpose |
|--------|------|-------|---------|
| GET | `/analytics/overview` | any | Headline KPI strip (census, occupancy, critical count, agent decisions/24h) |
| GET | `/analytics/patients` | any | Daily admission totals, by-category breakdown, ESI distribution |
| GET | `/analytics/occupancy` | any | Bed occupancy KPIs (same figures as `/beds/occupancy-summary`) |
| GET | `/analytics/medicine` | any | Expiring batches, low-stock/critical SKUs, value at risk |

Energy/water/waste/carbon analytics live under `/sustainability/*` (section 2.6) instead of
`/analytics/*` — they were built there because the Sustainability Dashboard needed the Carbon
Intelligence Agent's live output alongside the raw telemetry, not a plain aggregation. There is
no `/analytics/disease-trends`, `/analytics/ambulance`, `/analytics/performance` or
`/analytics/digital-twin` — see section 3.

---

## 3. Documented in Version 1.0, not shipped in this build

Named here deliberately rather than silently dropped, so a reader of the Phase 1 SRS
(`docs/01_requirements_srs.md`) or architecture doc can see exactly what changed and why:

| Originally planned | Status | Why |
|---|---|---|
| Pharmacy CRUD (`/medicines`, `/inventory` writes, `/inventory/transfers`) | Not built | Medicine data is seeded and read (`/analytics/medicine`, the Medicine Intelligence Agent); no UI or workflow needed direct inventory mutation via the API in this build |
| Ambulance dispatch routes (`/ambulances/*`) | Agent exists, no route | `AmbulanceDispatchAgent` (`app/agents/dispatch_agent.py`) is fully implemented and graph-wired on the `manual` trigger, but no HTTP endpoint constructs an `ambulance_call` today — it is exercised directly in the agent test suite, not from the API |
| `/emergency/overview` | Superseded | The Emergency Dashboard was built on `/beds/occupancy-summary` + `/analytics/overview` instead of a dedicated aggregate route |
| Reports (`POST/GET /reports`) | Not built | `Report`/`ReportType` models exist (`app/models/intelligence.py`) for future PDF/CSV export, but no generation pipeline or route was built this phase |
| Notifications (`/notifications/*`) | Not built | `Notification` model exists; no delivery route or feed endpoint was built — agent escalations currently surface only through `agent_logs`/`/agents/runs`, not a push channel |
| `WS /ws/notifications` | Not built | No WebSocket support in this build at all |
| Simulator control (`/simulator/*`) | Different shape | The simulator runs as a Celery beat tick (`app/simulator/tasks.py`, `SIMULATOR_ENABLED`/`SIMULATOR_TICK_SECONDS` env vars) rather than being started/stopped/queried through the API |
| `/carbon/score`, `/carbon/report`, `/carbon/opportunities`, `/energy/*`, `/water/*`, `/waste/*` | Consolidated | All folded into `/sustainability/summary` and the three `/sustainability/*-history` routes (section 2.6) rather than one route per telemetry stream |
| Rate limiting (10 req/min/IP on `/auth/*` etc.) | Not built | No rate-limiting middleware is installed; this is a real gap for an internet-facing production deployment, not a documentation omission |

---

## 4. Worked Example — Patient Arrival

**Request**
```http
POST /api/v1/admissions/arrival
Authorization: Bearer eyJ...
Content-Type: application/json

{
  "patient": {
    "full_name": "Synthetic Patient 4821",
    "age": 63, "sex": "male",
    "comorbidities": ["diabetes", "hypertension"]
  },
  "source": "ambulance",
  "chief_complaint": "Central chest pain radiating to left arm, 40 minutes",
  "vitals": {
    "heart_rate": 118, "systolic_bp": 96, "diastolic_bp": 62,
    "spo2": 92.0, "temperature_c": 36.8, "respiratory_rate": 26,
    "gcs": 15, "pain_score": 8
  },
  "disease_category": "cardiac"
}
```

**Response `201 Created`** (exact shape of `ArrivalResponse` in `app/schemas/clinical.py`)
```json
{
  "admission_id": "6797f1a2c3d4e5f60718293a",
  "admission_number": "ADM-2026-004821",
  "patient_id": "6797f1a2c3d4e5f607182939",
  "mrn": "MRN-004821",
  "status": "admitted",
  "triage": {
    "esi_level": 2,
    "confidence": 0.91,
    "recommended_department_code": "CARDIO",
    "target_response_minutes": 10,
    "red_flags": [],
    "rationale": "XGBoost triage model assigned ESI 2 (Emergent) with 91% confidence. Contributing observations: SpO2 92.0%, elevated shock index (1.23), age 63.",
    "model_version": "triage_esi_xgb@1.0.0",
    "used_fallback": false
  },
  "bed": {
    "bed_id": "6797f0b1c3d4e5f607182900",
    "bed_number": "CCU-04",
    "type": "icu",
    "predicted_los_days": 4.2,
    "reserved_until": null
  },
  "agent_run_id": "b41d8c9a-2f77-4c0e-9d1a-5e7f3a2b6c88",
  "degraded": false
}
```

**Downstream effects:** exactly two `agent_logs` documents for this `agent_run_id`
(`patient_triage`, `bed_allocation` — see the integration test in
`backend/tests/integration/test_agent_cycle.py`), and the bed's `status` moves to `occupied`
with `current_admission_id` set. Fetch the full reasoning trace with
`GET /agents/runs/{agent_run_id}`.

---

## 5. Generating a Postman/OpenAPI export

The schema is generated live from the running FastAPI app rather than hand-maintained:

```bash
curl http://localhost:8000/openapi.json -o docs/api/openapi.json
```

Import that file directly into Postman, Insomnia, or any OpenAPI-aware client — it is always
in sync with whatever this document's section 2 currently describes, since both are produced
from the same route definitions.
