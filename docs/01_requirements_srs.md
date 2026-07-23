# Software Requirements Specification
## HealMatrix AI — Multi-Agent Sustainable Healthcare Intelligence Platform

*Prepared in accordance with IEEE Std 830-1998*

| Field | Value |
|-------|-------|
| Document version | 1.0 |
| Status | Baselined (Phase 1) |
| Classification | Academic / Open Source |

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for **HealMatrix AI**,
an autonomous multi-agent platform that jointly optimises hospital clinical operations and
environmental sustainability across a network of hospitals. The intended audience is the
development team, project evaluators, and future maintainers.

### 1.2 Scope
HealMatrix AI ingests live operational telemetry from a hospital network (admissions, bed
state, pharmacy inventory, energy meters, water meters, waste bins, ambulance GPS) and applies
ten collaborating AI agents to produce ranked, explainable decisions. It delivers:

- Role-based operational dashboards for six personas
- A geospatial **digital twin** of each hospital and the surrounding network
- Predictive analytics for admissions, ICU load, medicine demand, energy, water and waste
- A retrieval-augmented knowledge layer grounded in WHO, CPCB and national health guidance
- Automated PDF reporting and a real-time notification engine

**Out of scope:** electronic medical records authoring, billing/claims, PACS imaging, direct
control of physical building-management hardware (the platform recommends; a human approves).

### 1.3 Definitions, Acronyms and Abbreviations

| Term | Meaning |
|------|---------|
| Agent | An autonomous LLM- or model-backed component with a defined tool set and objective |
| ESI | Emergency Severity Index (triage scale 1–5) |
| LOS | Length of Stay |
| RAG | Retrieval-Augmented Generation |
| Digital Twin | Live virtual representation of hospital physical state |
| BMW | Biomedical Waste |
| Scope 1/2/3 | GHG Protocol emission categories |
| CPCB | Central Pollution Control Board (India), BMW Rules 2016 authority |
| SDG | UN Sustainable Development Goal |

### 1.4 References
1. IEEE Std 830-1998 — Recommended Practice for SRS
2. WHO — *Safe Management of Wastes from Health-Care Activities*, 2nd ed.
3. CPCB — *Bio-Medical Waste Management Rules*, 2016 (as amended 2018)
4. GHG Protocol — *Corporate Accounting and Reporting Standard*
5. Emergency Severity Index (ESI) Implementation Handbook, AHRQ
6. UN — *Transforming our World: the 2030 Agenda for Sustainable Development*

### 1.5 Overview
Section 2 gives the overall product perspective. Section 3 enumerates specific functional
requirements per agent and per subsystem. Section 4 covers external interfaces, and Section 5
non-functional requirements.

---

## 2. Overall Description

### 2.1 Product Perspective
HealMatrix AI is a **self-contained, cloud-deployed web platform**. It sits alongside existing
HIS/EMR systems and consumes their data through REST adapters; for demonstration and academic
evaluation, a built-in **Simulation Engine** synthesises statistically realistic hospital
telemetry so the platform is fully operable without access to protected health data.

```
┌──────────────────────────────────────────────────────────────┐
│                    HealMatrix AI Platform                    │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ React SPA  │◀▶│  FastAPI API │◀▶│ LangGraph Orchestrator│  │
│  └────────────┘  └──────┬───────┘  └──────────┬───────────┘  │
│                         │                     │              │
│              ┌──────────▼─────────┐  ┌────────▼──────────┐   │
│              │  MongoDB Atlas     │  │ FAISS + Gemini    │   │
│              └────────────────────┘  └───────────────────┘   │
└──────────────────────────────────────────────────────────────┘
        ▲                        ▲
   Simulation Engine       External: OSRM, Cloudinary
```

### 2.2 Product Functions (summary)
- F1 Multi-hospital tenancy and role-based access control
- F2 Patient intake, triage and department routing
- F3 Bed & ICU allocation with discharge prediction
- F4 Pharmacy inventory intelligence and inter-hospital redistribution
- F5 Energy, water and waste monitoring and optimisation
- F6 Carbon accounting and sustainability scoring
- F7 Ambulance dispatch and route optimisation
- F8 Epidemiological forecasting
- F9 Executive synthesis, reporting and notification
- F10 Conversational + voice knowledge assistant over the RAG corpus
- F11 Digital twin visualisation
- F12 Continuous hospital simulation

### 2.3 User Classes and Characteristics

| Role | Technical skill | Primary needs | Key screens |
|------|-----------------|---------------|-------------|
| **Admin** | High | Tenant setup, users, audit, agent configuration | Admin Dashboard, Audit Log |
| **Doctor** | Medium | Triage queue, patient state, bed status, clinical Q&A | Doctor Dashboard, Voice Assistant |
| **Nurse** | Medium | Ward occupancy, admissions, waste segregation, alerts | Emergency + Ward views |
| **Pharmacist** | Medium | Stock levels, expiry risk, demand forecast, transfers | Inventory Dashboard |
| **Hospital Manager** | Medium | Throughput, occupancy, staffing, performance KPIs | Executive Dashboard |
| **Sustainability Officer** | Medium | Energy, water, waste, carbon, SDG reporting | Sustainability Dashboard |

### 2.4 Operating Environment
- **Client:** Chrome/Edge/Firefox/Safari, last two major versions; ≥360 px viewport
- **Server:** Linux container, Python 3.11, 1 vCPU / 2 GB minimum
- **Database:** MongoDB Atlas M0+ (replica set), Redis 7 (Upstash)
- **Network:** HTTPS only; outbound access to Gemini API and OSRM

### 2.5 Design and Implementation Constraints
- C1 — Backend **must** be Python; Node/Express backends are prohibited.
- C2 — Frontend **must** be ≥95 % JavaScript; TypeScript permitted only in config files.
- C3 — LLM provider is Google Gemini; all prompts must degrade gracefully on API failure.
- C4 — No real patient data; all demonstration data is synthetic.
- C5 — Agent decisions affecting patients are **advisory**; a human role must confirm.
- C6 — Free-tier deployment targets (Render, Vercel, Atlas M0, Upstash) impose cold starts
  and a 512 MB memory ceiling; ML artefacts must stay under 50 MB combined.

### 2.6 Assumptions and Dependencies
- A1 — Gemini API quota is available; a deterministic fallback path exists for every agent.
- A2 — The simulator's distributions are calibrated to published Indian tertiary-hospital
  averages and are adequate for demonstration, not for clinical inference.
- A3 — OSRM public routing is reachable; Haversine fallback otherwise.

---

## 3. Specific Requirements — Functional

Requirement IDs follow `FR-<subsystem>-<n>`. Priority: **H**igh / **M**edium / **L**ow.

### 3.1 Authentication & Tenancy

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-AUTH-1 | The system shall register users with email, password, role and hospital_id. | H |
| FR-AUTH-2 | The system shall authenticate via JWT access (60 min) + refresh (7 d) tokens. | H |
| FR-AUTH-3 | The system shall hash passwords with bcrypt (cost ≥ 12) and never return them. | H |
| FR-AUTH-4 | The system shall enforce role-based authorisation on every protected endpoint. | H |
| FR-AUTH-5 | The system shall scope every query by `hospital_id` unless the caller is a network admin. | H |
| FR-AUTH-6 | The system shall write an `audit_logs` entry for every write operation. | M |
| FR-AUTH-7 | The system shall support token revocation via a Redis deny-list on logout. | M |

### 3.2 Patient Triage Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-TRI-1 | Shall accept vitals (HR, BP, SpO₂, temp, RR), age, sex, chief complaint and comorbidities. | H |
| FR-TRI-2 | Shall output an ESI level 1–5 with a calibrated confidence score. | H |
| FR-TRI-3 | Shall recommend a destination department from the hospital's active department list. | H |
| FR-TRI-4 | Shall produce a natural-language clinical rationale citing the driving features. | H |
| FR-TRI-5 | Shall complete within 3 s at P95 and fall back to a deterministic ESI rule set if the LLM is unavailable. | H |
| FR-TRI-6 | Shall flag red-flag vital combinations (e.g. SpO₂ < 90 % with RR > 30) as ESI 1 regardless of model output. | H |
| FR-TRI-7 | Shall persist every triage decision to `agent_logs` with inputs, outputs and model version. | M |

### 3.3 Bed Allocation Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-BED-1 | Shall maintain real-time status per bed: available, occupied, cleaning, maintenance, reserved. | H |
| FR-BED-2 | Shall recommend a specific bed given ESI level, department, isolation need and sex-ward rules. | H |
| FR-BED-3 | Shall predict remaining LOS per admitted patient and surface expected discharges over 24/48 h. | H |
| FR-BED-4 | Shall escalate to ICU-overflow protocol when ICU occupancy ≥ 90 %. | H |
| FR-BED-5 | Shall report occupancy rate, average LOS and bed-turnover interval per ward. | M |
| FR-BED-6 | Shall never assign a bed marked `maintenance` or one already reserved within 30 minutes. | H |

### 3.4 Medicine Intelligence Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-MED-1 | Shall forecast 7/14/30-day demand per SKU per hospital. | H |
| FR-MED-2 | Shall raise an expiry alert at 90, 30 and 7 days before expiry date. | H |
| FR-MED-3 | Shall compute reorder point from lead time and demand variance, and raise low-stock alerts. | H |
| FR-MED-4 | Shall propose inter-hospital transfers where a donor hospital holds near-expiry stock that a recipient will consume before expiry. | H |
| FR-MED-5 | Shall quantify each transfer proposal in units saved, currency saved and kg CO₂e avoided. | M |
| FR-MED-6 | Shall respect cold-chain constraints when proposing transfers. | M |

### 3.5 Biomedical Waste Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-WST-1 | Shall classify waste into CPCB colour categories: yellow, red, white (translucent), blue. | H |
| FR-WST-2 | Shall forecast daily waste generation per category per department. | H |
| FR-WST-3 | Shall schedule pickups so no yellow-category waste is stored beyond 48 h. | H |
| FR-WST-4 | Shall detect segregation anomalies (e.g. red-bag weight exceeding plausible ratio). | M |
| FR-WST-5 | Shall recommend recyclable recovery opportunities with estimated diversion rate. | M |
| FR-WST-6 | Shall ground all classification guidance in the indexed CPBC BMW Rules 2016 corpus and cite the source. | H |

### 3.6 Energy Optimization Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-ENR-1 | Shall forecast hourly electricity demand 24 h ahead per hospital. | H |
| FR-ENR-2 | Shall recommend HVAC setpoints per zone using occupancy, outside temperature and clinical constraints. | H |
| FR-ENR-3 | Shall identify equipment with abnormal idle-power draw. | M |
| FR-ENR-4 | Shall compute renewable-shift potential and payback period for proposed solar capacity. | M |
| FR-ENR-5 | Shall never recommend an OT or ICU zone setpoint outside 20–24 °C. | H |

### 3.7 Water Conservation Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-WTR-1 | Shall forecast daily water consumption per hospital. | H |
| FR-WTR-2 | Shall detect leaks via anomaly detection on night-time minimum flow. | H |
| FR-WTR-3 | Shall raise a critical alert when leak probability > 0.8, with estimated litres/day lost. | H |
| FR-WTR-4 | Shall compute rainwater harvesting yield from roof area and local rainfall. | M |
| FR-WTR-5 | Shall rank water-saving interventions by litres saved per rupee invested. | M |

### 3.8 Ambulance Dispatch Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-AMB-1 | Shall maintain live ambulance status: idle, dispatched, en-route, at-scene, returning, maintenance. | H |
| FR-AMB-2 | Shall select the nearest *suitable* hospital — capability-matched **and** with capacity — not merely the nearest. | H |
| FR-AMB-3 | Shall compute a route with ETA and re-compute on significant deviation. | H |
| FR-AMB-4 | Shall pre-empt a lower-priority assignment when a higher-priority call arrives. | H |
| FR-AMB-5 | Shall report response-time distribution and fleet utilisation. | M |

### 3.9 Carbon Intelligence Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-CRB-1 | Shall compute Scope 1 (fuel, anaesthetic gases), Scope 2 (grid electricity) and partial Scope 3 (waste, procurement) emissions. | H |
| FR-CRB-2 | Shall normalise emissions per bed-day for cross-hospital comparison. | H |
| FR-CRB-3 | Shall produce a 0–100 sustainability score from weighted energy, water, waste and carbon sub-scores. | H |
| FR-CRB-4 | Shall rank reduction levers by tCO₂e abated per unit cost. | M |
| FR-CRB-5 | Shall version emission factors so historical reports remain reproducible. | M |

### 3.10 Disease Forecast Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-DIS-1 | Shall forecast 14-day admissions per disease category using seasonality and recent trend. | H |
| FR-DIS-2 | Shall forecast ICU bed demand with an 80 % prediction interval. | H |
| FR-DIS-3 | Shall raise an outbreak warning when observed cases exceed the seasonal baseline by > 2σ for 3 consecutive days. | H |
| FR-DIS-4 | Shall translate forecasts into resource pre-allocation recommendations (beds, staff, key medicines). | M |

### 3.11 Executive Decision Agent

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-EXE-1 | Shall consume the outputs of all nine upstream agents from the shared graph state. | H |
| FR-EXE-2 | Shall detect and resolve conflicting recommendations under an explicit priority order: patient safety > regulatory compliance > cost > sustainability. | H |
| FR-EXE-3 | Shall emit an executive summary, a ranked action plan with owner and horizon, and a risk register. | H |
| FR-EXE-4 | Shall attribute every action to the originating agent for traceability. | H |
| FR-EXE-5 | Shall complete a full network cycle within 45 s at P95. | M |

### 3.12 Simulation Engine

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-SIM-1 | Shall generate seedable, reproducible synthetic data for all 13 entity streams. | H |
| FR-SIM-2 | Shall model diurnal, weekly and seasonal patterns (e.g. evening ED peak, monsoon dengue). | H |
| FR-SIM-3 | Shall emit events continuously on a configurable tick and persist them to MongoDB. | H |
| FR-SIM-4 | Shall support scenario injection: mass-casualty, outbreak surge, power failure, water main break. | M |
| FR-SIM-5 | Shall be disableable via `SIMULATOR_ENABLED` so real adapters can take over. | H |

### 3.13 RAG Knowledge Base

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-RAG-1 | Shall ingest, chunk and embed the eight guidance corpora into a FAISS index. | H |
| FR-RAG-2 | Shall return top-k passages with source document, section and similarity score. | H |
| FR-RAG-3 | Shall refuse to answer beyond retrieved evidence and say so explicitly. | H |
| FR-RAG-4 | Shall support incremental re-indexing without full rebuild. | M |

### 3.14 Reports, Notifications & Voice

| ID | Requirement | Pri |
|----|-------------|-----|
| FR-RPT-1 | Shall generate seven PDF report types with charts, branding and a generation timestamp. | H |
| FR-RPT-2 | Shall run report generation asynchronously via Celery and notify on completion. | M |
| FR-NOT-1 | Shall deliver notifications for the seven defined alert classes with severity and acknowledgement state. | H |
| FR-NOT-2 | Shall push notifications over WebSocket to connected clients within 2 s. | M |
| FR-VOI-1 | Shall accept voice queries via the browser Web Speech API and route them through the RAG + tool layer. | M |
| FR-VOI-2 | Shall render both a spoken and a visual answer, with the underlying data table when applicable. | L |

---

## 4. External Interface Requirements

### 4.1 User Interfaces
Premium SaaS aesthetic (Stripe / Linear / Vercel lineage): glassmorphic surfaces, 8-pt spacing
grid, Inter typeface, full dark/light theming, WCAG 2.1 AA contrast, keyboard-navigable, and
responsive from 360 px to 2560 px. Detailed in `docs/06_ui_wireframes.md`.

### 4.2 Software Interfaces

| Interface | Protocol | Purpose | Failure mode |
|-----------|----------|---------|--------------|
| Google Gemini | HTTPS/REST | Agent reasoning & synthesis | Deterministic rule fallback |
| MongoDB Atlas | MongoDB wire | Primary datastore | Fail fast, 503 |
| Redis (Upstash) | RESP | Celery broker, cache, token deny-list | Degrade to synchronous execution |
| Cloudinary | HTTPS/REST | Report & asset storage | Local filesystem fallback |
| OSRM | HTTPS/REST | Road routing | Haversine straight-line estimate |

### 4.3 Communication Interfaces
REST/JSON over HTTPS under `/api/v1`; WebSocket at `/ws/notifications`; JWT bearer
authentication; CORS restricted to configured origins.

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement |
|----|-------------|
| NFR-PERF-1 | Read API endpoints shall respond in < 300 ms at P95 (excluding cold start). |
| NFR-PERF-2 | Single-agent invocation shall complete in < 3 s at P95. |
| NFR-PERF-3 | Full LangGraph network cycle shall complete in < 45 s at P95. |
| NFR-PERF-4 | Dashboard first contentful paint shall be < 2 s on a 4G connection. |
| NFR-PERF-5 | The system shall support 200 concurrent authenticated users on the reference deployment. |

### 5.2 Security

| ID | Requirement |
|----|-------------|
| NFR-SEC-1 | All transport shall be TLS 1.2+. |
| NFR-SEC-2 | Passwords shall be bcrypt-hashed; secrets shall come from environment variables only. |
| NFR-SEC-3 | All input shall be validated by Pydantic models; unvalidated input shall be rejected with 422. |
| NFR-SEC-4 | Rate limiting shall cap authentication endpoints at 10 requests/minute/IP. |
| NFR-SEC-5 | Audit logs shall be append-only and retained for 365 days. |
| NFR-SEC-6 | Cross-tenant data access shall be structurally impossible via the repository layer. |

### 5.3 Reliability & Availability
- NFR-REL-1 — Target availability 99.5 % monthly.
- NFR-REL-2 — Every external dependency shall have a defined degraded-mode behaviour.
- NFR-REL-3 — Celery tasks shall retry with exponential backoff, max 3 attempts.
- NFR-REL-4 — `/health` and `/health/ready` endpoints shall report dependency status.

### 5.4 Maintainability & Portability
- NFR-MNT-1 — Layered architecture: routes → services → repositories → database.
- NFR-MNT-2 — Test coverage ≥ 70 % on `app/services` and `app/agents`.
- NFR-MNT-3 — Lint gate (ruff, eslint) must pass before merge.
- NFR-MNT-4 — The entire stack shall run from `docker compose up` with no host dependencies.

### 5.5 Ethical & Regulatory
- NFR-ETH-1 — Every agent output shall be labelled advisory and carry a confidence value.
- NFR-ETH-2 — Clinical recommendations shall be explainable, naming the features that drove them.
- NFR-ETH-3 — No real PHI shall enter the system; synthetic data shall be clearly marked.
- NFR-ETH-4 — Human confirmation shall be required before any patient-affecting action is executed.

---

## 6. Traceability — Requirements to SDG

| SDG | Supporting requirements |
|-----|-------------------------|
| 3 | FR-TRI-*, FR-BED-*, FR-AMB-*, FR-DIS-* |
| 7 | FR-ENR-* |
| 9 | FR-EXE-*, FR-SIM-*, FR-RAG-* |
| 11 | FR-AMB-2, FR-AMB-3, digital twin |
| 12 | FR-MED-4, FR-MED-5, FR-WST-* |
| 13 | FR-CRB-* |

---

## 7. Acceptance Criteria (Phase Gate)

A phase is accepted when: all High-priority requirements in scope are demonstrable end-to-end,
CI is green, no placeholder or TODO code remains, and the corresponding documentation section
is updated.
