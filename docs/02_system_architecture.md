# System Architecture & Design Document
## HealMatrix AI

Version 1.0 · Phase 1 baseline

---

## 1. Architectural Goals & Drivers

| Driver | Architectural response |
|--------|------------------------|
| Agents must genuinely collaborate, not chain LLM calls | Shared typed state object in LangGraph with conditional edges, fan-out/fan-in, and a conflict-resolution node |
| Must run on free-tier infrastructure | Async I/O throughout, small model artefacts, aggressive caching, lazy FAISS load |
| Sustainability metrics must be auditable | Versioned emission factors, immutable `agent_logs`, reproducible seeds |
| Multi-hospital network | `hospital_id` partition key on every collection, enforced at the repository layer |
| LLM outages must not break the product | Every agent has a deterministic fallback strategy |
| Evaluator must see the reasoning | Every decision persists its inputs, outputs, model version and rationale |

---

## 2. Logical Architecture — Layered View

```
┌───────────────────────────────────────────────────────────────────────┐
│ L1  PRESENTATION — React 18 SPA (Vite)                                │
│     Pages · Layout shell · Recharts · Leaflet twin · Framer Motion    │
│     Context: Auth, Theme, Notifications, Hospital                     │
└──────────────────────────────┬────────────────────────────────────────┘
                     HTTPS/JSON + WebSocket
┌──────────────────────────────▼────────────────────────────────────────┐
│ L2  API — FastAPI                                                     │
│     Routers /api/v1/*  ·  JWT middleware  ·  RBAC dependency          │
│     Pydantic v2 request/response schemas  ·  Exception handlers       │
└──────────────────────────────┬────────────────────────────────────────┘
┌──────────────────────────────▼────────────────────────────────────────┐
│ L3  SERVICE / DOMAIN                                                  │
│     PatientService · BedService · InventoryService · EnergyService    │
│     WaterService · WasteService · CarbonService · DispatchService     │
│     ReportService · NotificationService · AnalyticsService            │
└───────┬──────────────────────────────┬────────────────────────────────┘
        │                              │
┌───────▼────────────────┐  ┌──────────▼─────────────────────────────────┐
│ L4a  AGENT LAYER       │  │ L4b  DATA ACCESS                           │
│  LangGraph orchestrator│  │  Repositories (Motor) · Index bootstrap    │
│  10 agents + tools     │  │  Aggregation pipelines                     │
│  CrewAI executive crew │  └──────────┬─────────────────────────────────┘
│  RAG retriever (FAISS) │             │
│  ML model registry     │  ┌──────────▼─────────────────────────────────┐
└───────┬────────────────┘  │ L5  PERSISTENCE                            │
        │                   │  MongoDB Atlas · Redis · FAISS · Cloudinary│
┌───────▼────────────────┐  └────────────────────────────────────────────┘
│ L4c  ASYNC WORKERS     │
│  Celery: simulator tick, forecasts, report render, index refresh      │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.1 Layer responsibilities

**L1 Presentation.** Renders state; holds no business rules. All server communication goes
through a single Axios instance with interceptors for token refresh and error normalisation.

**L2 API.** Thin. Validates, authorises, delegates. A router function should rarely exceed
15 lines. Cross-cutting concerns (auth, tenancy, correlation ID, timing) are FastAPI
dependencies.

**L3 Service.** Owns business rules and transactions. Services never touch `motor` directly —
they call repositories. Services are where "a bed cannot be assigned if it is under
maintenance" lives.

**L4a Agent layer.** Agents are services with an LLM and a tool belt. Each agent exposes
`async def run(state) -> AgentResult`. Agents call *services*, not repositories, so business
invariants are enforced identically whether the actor is a human or an agent.

**L4b Data access.** One repository per collection. Generic `BaseRepository` supplies CRUD
with mandatory `hospital_id` scoping.

**L5 Persistence.** MongoDB for operational state, Redis for broker/cache/deny-list, FAISS for
vectors, Cloudinary for rendered PDFs and images.

---

## 3. Multi-Agent Design

### 3.1 Why LangGraph rather than a chain

A chain gives you `A → B → C`. Hospital operations are not a chain: bed allocation depends on
both triage severity *and* the disease forecast; the carbon agent needs energy *and* waste;
and the executive agent must reconcile a pharmacist's cost-saving proposal against a
sustainability officer's carbon proposal. That requires a **graph with shared state, parallel
branches, conditional routing and a reconciliation node** — which is exactly LangGraph's model.

### 3.2 Shared state

```python
class HealMatrixState(TypedDict, total=False):
    # --- context ---
    run_id: str
    hospital_id: str
    triggered_by: Literal["patient_arrival", "scheduled_cycle", "manual", "scenario"]
    timestamp: datetime
    snapshot: HospitalSnapshot          # live metrics read once, shared by all agents

    # --- agent outputs ---
    triage: TriageResult | None
    disease_forecast: DiseaseForecastResult | None
    bed_allocation: BedAllocationResult | None
    medicine: MedicineResult | None
    energy: EnergyResult | None
    water: WaterResult | None
    waste: WasteResult | None
    carbon: CarbonResult | None
    dispatch: DispatchResult | None
    executive: ExecutiveResult | None

    # --- coordination ---
    messages: Annotated[list[AgentMessage], operator.add]   # inter-agent bus
    conflicts: list[Conflict]
    errors: list[AgentError]
    degraded: bool                       # true when any agent used its fallback
```

`messages` uses an additive reducer so parallel branches can append without clobbering — this
is the inter-agent communication bus. An agent that needs a peer's finding reads
`state["messages"]` rather than re-deriving it.

### 3.3 Graph topology

```
                         ┌──────────────┐
                         │    START     │
                         └──────┬───────┘
                                ▼
                        ┌───────────────┐
                        │ snapshot_node │  single DB read → shared context
                        └───────┬───────┘
                                ▼
                        ┌───────────────┐
                        │  triage_agent │  (skipped on scheduled_cycle)
                        └───────┬───────┘
                                ▼
                     ┌──────────────────────┐
                     │ disease_forecast     │
                     └──────────┬───────────┘
                                ▼
                     ┌──────────────────────┐
                     │  bed_allocation      │◀── reads triage + forecast
                     └──────────┬───────────┘
                                ▼
        ╔═══════════════ PARALLEL FAN-OUT ═══════════════╗
        ║   medicine    energy    water    waste    dispatch  ║
        ╚═══════════════════════┬════════════════════════╝
                                ▼
                     ┌──────────────────────┐
                     │  carbon_intelligence │◀── consumes energy+waste+water
                     └──────────┬───────────┘
                                ▼
                     ┌──────────────────────┐
                     │  conflict_resolver   │  conditional edge
                     └──────────┬───────────┘
                                ▼
                     ┌──────────────────────┐
                     │  executive_decision  │  CrewAI crew
                     └──────────┬───────────┘
                                ▼
                     ┌──────────────────────┐
                     │  persist_and_notify  │
                     └──────────┬───────────┘
                                ▼
                              END
```

**Conditional edges**
- `triage_agent → bed_allocation` is taken only when `triggered_by == "patient_arrival"`.
- `bed_allocation → escalate_icu` when ICU occupancy ≥ 90 %, otherwise straight to fan-out.
- `conflict_resolver → renegotiate` loops back to the affected agents at most twice before
  handing the unresolved conflict to the executive agent as an explicit decision item.

### 3.4 Division of labour: LangGraph vs CrewAI

| Concern | Framework | Reason |
|---------|-----------|--------|
| Deterministic operational workflow, state passing, retries | **LangGraph** | Explicit, inspectable, testable graph |
| Open-ended strategic synthesis (the executive review) | **CrewAI** | Role-playing crew — Analyst, Sustainability Auditor, Operations Strategist, Chief of Staff — produces richer deliberation than a single prompt |

The CrewAI executive crew is invoked *inside* the `executive_decision` LangGraph node, so the
graph remains the single orchestrator.

### 3.5 Agent anatomy

Every agent implements `BaseAgent`:

```python
class BaseAgent(ABC):
    name: str
    version: str

    @abstractmethod
    async def analyse(self, state: HealMatrixState) -> AgentResult: ...

    @abstractmethod
    def fallback(self, state: HealMatrixState) -> AgentResult: ...

    async def run(self, state: HealMatrixState) -> AgentResult:
        # timing, retry, fallback, agent_logs persistence, message emission
```

The base class owns observability so individual agents contain only domain logic.

### 3.6 Fallback matrix

| Agent | Primary | Fallback when Gemini/model unavailable |
|-------|---------|----------------------------------------|
| Triage | XGBoost + Gemini rationale | ESI decision table on vitals |
| Disease Forecast | XGBoost + seasonal features | 4-week moving average |
| Bed Allocation | Scoring solver + LOS model | First-fit by ward and severity |
| Medicine | Demand model + optimiser | Reorder point from mean consumption |
| Energy | GBR forecast | Same-hour-last-week persistence |
| Water | IsolationForest | Fixed-threshold night-flow rule |
| Waste | RAG-grounded classifier | CPCB colour lookup table |
| Carbon | Factor engine (no LLM) | — deterministic by design |
| Dispatch | OSRM route | Haversine distance × 1.35 detour factor |
| Executive | CrewAI + Gemini | Templated summary from ranked agent outputs |

---

## 4. Machine Learning Design

| Model | Task | Algorithm | Features | Metric | Target |
|-------|------|-----------|----------|--------|--------|
| `triage_esi` | 5-class | XGBoost classifier | vitals, age, comorbidity count, complaint embedding | macro-F1 | ≥ 0.82 |
| `los_days` | regression | XGBoost regressor | ESI, dept, age, comorbidities, admission hour | MAE (days) | ≤ 1.2 |
| `admissions_14d` | time series | XGBoost + lag/seasonal features | lags 1–14, DOW, month, holiday, weather proxy | MAPE | ≤ 12 % |
| `medicine_demand` | time series | XGBoost per SKU-cluster | lags, admissions, seasonality, dept mix | MAPE | ≤ 15 % |
| `energy_load` | regression | Gradient boosting | hour, DOW, occupancy, OAT, equipment count | RMSE (kWh) | ≤ 8 % of mean |
| `water_anomaly` | anomaly | IsolationForest | night-min flow, flow variance, occupancy ratio | precision@alerts | ≥ 0.75 |

**Training pipeline.** `scripts/train_models.py` pulls 18 simulated months from Mongo, builds
features via `app/ml/features.py`, trains with time-series cross-validation, writes metrics to
`app/ml/artifacts/metrics.json` and joblib artefacts to `app/ml/artifacts/`. A `ModelRegistry`
singleton lazy-loads artefacts and exposes `predict()` with graceful degradation when an
artefact is missing.

---

## 5. RAG Design

```
knowledge_base/*.md ──▶ Loader ──▶ RecursiveCharacterTextSplitter
                                    (chunk 800, overlap 120)
                                          │
                                          ▼
                          all-MiniLM-L6-v2 (384-dim, CPU)
                                          │
                                          ▼
                            FAISS IndexFlatIP (cosine)
                                          │
                          metadata sidecar: {source, section, category}
                                          │
   query ──▶ embed ──▶ top-k=5 ──▶ score filter (≥0.35) ──▶ Gemini with citations
```

Corpora: WHO waste management, CPCB BMW Rules 2016, hospital SOPs, emergency protocols,
national health policy, medicine storage guidance, energy optimisation guidance, water
conservation guidance. Index is built by `scripts/build_index.py` and refreshed nightly by a
Celery beat task.

If no chunk clears the score threshold, the assistant states that the knowledge base does not
cover the question rather than inventing an answer.

---

## 6. Simulation Engine

Thirteen generators driven by a seeded `numpy.random.Generator`:

| Stream | Model |
|--------|-------|
| Patient arrivals | Non-homogeneous Poisson; diurnal peak 18:00–22:00, weekly Monday peak |
| Disease mix | Season-dependent categorical; dengue/monsoon, respiratory/winter |
| Admissions & LOS | Log-normal LOS conditioned on ESI and department |
| ICU occupancy | Derived from admissions × ICU-conversion rate by severity |
| Ambulance calls | Poisson with rush-hour intensity; geo-sampled around hospital coordinates |
| Medicine consumption | Per-SKU rate proportional to department census + noise |
| Biomedical waste | kg/bed-day per CPCB category × occupancy |
| Electricity | Base load + HVAC term (function of synthetic outside temperature) + OT schedule |
| Water | Per-bed-day baseline + laundry/kitchen cycles + optional injected leak |
| Carbon | Computed, not sampled — derived from energy, waste and transport |
| Equipment utilisation | Markov chain over idle/active/maintenance |
| Staff rosters | Three-shift rotation with skill mix |
| Outbreaks | Injectable SIR-style surge overlay |

Scenario injection (`POST /api/v1/simulator/scenario`) supports `mass_casualty`,
`outbreak_surge`, `power_failure`, `water_main_break`, `supply_disruption` — the demo lever
that shows agents reacting under stress.

---

## 7. Deployment Architecture

Two deployment paths are actually configured in this repository, not just described here —
see `docs/00_phase3_verification.md` for what was verified about each.

### 7.1 Cloud path: Vercel + Render + managed data services

```
        Vercel (frontend)                    Render (backend + worker + beat)
  ┌─────────────────────────┐        ┌───────────────────────────────────┐
  │  React SPA (static)     │  HTTPS │  FastAPI web service              │
  │  Edge CDN               │───────▶│  Celery worker + Celery beat      │
  └─────────────────────────┘        └───────┬───────────────┬───────────┘
                                             │               │
                              ┌──────────────▼──┐   ┌────────▼─────────┐
                              │ MongoDB Atlas   │   │ Upstash Redis    │
                              └─────────────────┘   └──────────────────┘
                                             │
                              ┌──────────────▼──┐   ┌──────────────────┐
                              │ Cloudinary      │   │ Google Gemini    │
                              └─────────────────┘   └──────────────────┘
```

Configuration lives in the repository, not only in provider dashboards:
- `deployment/render/render.yaml` — a Render Blueprint defining all three backend services
  (`healmatrix-api` web service, `healmatrix-worker`, `healmatrix-beat`), all built from the
  same `docker/backend.Dockerfile` with `INSTALL_AI=true`, sharing secrets via Render's
  `fromService` env-var references so the worker/beat never duplicate the API's own secret
  values.
- `deployment/vercel/vercel.json` + `deployment/vercel/README.md` — SPA rewrite rule (so a
  direct link to `/dashboard/executive` resolves instead of 404ing) and the required
  `VITE_API_BASE_URL` environment variable, since Vite bakes that value in at build time, not
  at request time.

### 7.2 Self-hosted path: Docker Compose, on one machine

For a hospital that wants the whole stack on its own infrastructure rather than a cloud
provider — a real requirement for data-residency-sensitive deployments, not a fallback:

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up --build -d
```

This builds the frontend's `prod` stage (`docker/frontend.Dockerfile`, nginx serving the
static build) rather than the dev stage (Vite's dev server) that `docker-compose.yml` runs
locally, runs `mongo`/`redis` as containers instead of managed services, and sets
`restart: always` throughout. nginx proxies `/api/` to the backend container
(`frontend/nginx.conf`), which is what lets the same relative `VITE_API_BASE_URL` default work
unmodified in this path.

### 7.3 Verifying either path

```bash
python scripts/smoke_test.py --base-url <api-url> --frontend-url <frontend-url>
```

checks liveness, readiness (including whether `GOOGLE_API_KEY` is configured), the OpenAPI
schema is served, and the frontend returns its SPA shell — see the script's own docstring for
the full check list and exit-code contract.

Environments: `development` (docker compose), `production` (either path above).
Configuration is entirely environment-variable driven; no environment-specific code paths.

---

## 8. Cross-Cutting Concerns

Table entries are marked with what actually backs them today — several items from this
document's original draft (rate limiting, a metrics endpoint, response caching) were not built
in this project's scope, and are named here rather than silently dropped so a reader can see
the gap rather than assume the mechanism exists.

| Concern | Mechanism | Status |
|---------|-----------|--------|
| Authentication | JWT access/refresh, bcrypt password hashing | Built |
| Authorisation | `require_roles(...)` FastAPI dependency, checked per route | Built |
| Tenancy | `hospital_id` injected from token claims into every scoped repository call | Built |
| Validation | Pydantic v2 models on every request/response boundary | Built |
| Errors | Domain exception hierarchy → structured JSON `{code, message, details, correlation_id}` | Built |
| Logging | structlog JSON lines with a correlation ID propagated from request to agent run | Built |
| Token revocation | Access tokens simply expire (`ACCESS_TOKEN_EXPIRE_MINUTES`); there is no `/auth/logout` and no Redis deny-list | **Not built** — acceptable for this build's threat model, a real gap for a stricter one |
| Rate limiting | — | **Not built** — no `slowapi` or equivalent; a real gap before this API is exposed to the public internet unauthenticated |
| Response caching | — | **Not built** — every dashboard read hits MongoDB directly; fine at this data volume, would need revisiting at network scale |
| Observability / metrics | Structured request logs (method, path, status, duration) on every request | **Partial** — no `/metrics` Prometheus endpoint or agent-latency histograms; per-agent latency is available via `GET /agents/status`'s `avg_duration_ms`, just not exported in Prometheus format |

---

## 9. Key Design Decisions (ADR summary)

| ID | Decision | Alternatives considered | Rationale |
|----|----------|-------------------------|-----------|
| ADR-1 | MongoDB over PostgreSQL | Postgres + TimescaleDB | Heterogeneous, schema-evolving telemetry; agent outputs are naturally documents |
| ADR-2 | LangGraph as primary orchestrator, CrewAI nested | CrewAI only; LangChain agents only | Needed deterministic, testable control flow with a role-play island for synthesis |
| ADR-3 | FAISS over a hosted vector DB | Pinecone, Chroma | Zero cost, no network hop, index is small (< 20 MB) and static |
| ADR-4 | Trained ML models rather than LLM-only prediction | Gemini-only numeric estimates | Reproducible, measurable, defensible; LLM used for explanation, not arithmetic |
| ADR-5 | Advisory-only agent actions | Autonomous execution | Clinical safety and academic-ethics posture |
| ADR-6 | JavaScript frontend, no TypeScript | TS + React | Explicit project constraint |
| ADR-7 | Simulator in-repo rather than a static dataset | CSV fixtures | Enables live, continuous, scenario-driven demonstration |
