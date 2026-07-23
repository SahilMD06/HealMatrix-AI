<h1 align="center">HealMatrix AI</h1>
<p align="center"><b>Multi-Agent Sustainable Healthcare Intelligence Platform</b></p>
<p align="center"><i>"Empowering Sustainable Hospitals Through Collaborative Agentic AI."</i></p>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="fastapi" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white">
  <img alt="react" src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black">
  <img alt="mongodb" src="https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white">
  <img alt="langgraph" src="https://img.shields.io/badge/LangGraph-Multi--Agent-1C3C3C">
  <img alt="license" src="https://img.shields.io/badge/License-MIT-blue">
</p>

---

## 1. What is HealMatrix AI?

HealMatrix AI is **not** a Hospital Management System with a chatbot bolted on. It is an
**agentic operations layer** for a network of hospitals. Ten specialised AI agents observe the
live state of the hospital, reason over it, negotiate with one another through a shared
LangGraph state object, and emit **executable decisions** — bed assignments, redistribution
orders, HVAC setpoints, waste pickup schedules and board-level sustainability actions.

The platform ties clinical efficiency to environmental performance: every operational decision
is scored for its carbon, energy, water and waste consequence, so a hospital can improve
patient outcomes *and* its sustainability rating from the same control plane.

## 2. UN Sustainable Development Goals

| SDG | Goal | How HealMatrix contributes |
|-----|------|----------------------------|
| **3** *(primary)* | Good Health & Well-Being | AI triage, ICU demand forecasting, ambulance routing, outbreak early-warning |
| **7** | Affordable & Clean Energy | Load forecasting, HVAC optimisation, renewable-shift recommendations |
| **9** | Industry, Innovation & Infrastructure | Agentic AI applied to critical public infrastructure |
| **11** | Sustainable Cities & Communities | Hospital-network digital twin, city-scale emergency routing |
| **12** | Responsible Consumption & Production | Medicine expiry prevention, inter-hospital redistribution, waste segregation |
| **13** | Climate Action | Scope 1/2/3 carbon accounting and reduction planning |

## 3. The Agent Roster

| # | Agent | Responsibility | Intelligence |
|---|-------|----------------|--------------|
| 1 | Patient Triage | Severity classification, ESI level, department routing | XGBoost classifier + Gemini rationale |
| 2 | Disease Forecast | Seasonal outbreak & admission forecasting | SARIMA / XGBoost regressor |
| 3 | Bed Allocation | Bed & ICU assignment, discharge prediction | Constraint solver + LOS regressor |
| 4 | Medicine Intelligence | Demand forecast, expiry risk, inter-hospital transfer | XGBoost + optimisation heuristic |
| 5 | Energy Optimization | Load forecast, HVAC setpoints, renewable shift | Gradient-boosted regressor |
| 6 | Water Conservation | Leak detection, usage forecast, harvesting analytics | IsolationForest anomaly detection |
| 7 | Biomedical Waste | Category classification, generation forecast, pickup scheduling | Rules + CPCB knowledge base (RAG) |
| 8 | Carbon Intelligence | Emission accounting, sustainability score | Emission-factor engine |
| 9 | Ambulance Dispatch | Nearest-suitable-hospital routing, priority queueing | Haversine + OSRM road routing |
| 10 | **Executive Decision** | Synthesises all agents into an executive action plan | Gemini + CrewAI executive crew |

## 4. Architecture at a Glance

```
React (Vite) ──axios──▶ FastAPI ──▶ LangGraph Orchestrator ──▶ 10 Agents
     │                     │                 │                    │
  Recharts             Motor/Async        Shared State       FAISS RAG
  Leaflet twin         MongoDB Atlas      (HealMatrixState)   Gemini API
                       Celery + Redis                         ML artefacts
```

Full detail: [`docs/02_system_architecture.md`](docs/02_system_architecture.md)

## 5. Tech Stack

**Frontend** — React 18, JavaScript, Vite, Tailwind CSS, shadcn/ui, React Router, Axios,
Framer Motion, Recharts, Leaflet, React Icons.

**Backend** — Python 3.11, FastAPI, Pydantic v2, Motor, Celery, Redis, JWT (python-jose).

**AI** — LangGraph, CrewAI, LangChain, Google Gemini, Sentence-Transformers, FAISS,
scikit-learn, XGBoost.

**Data & Infra** — MongoDB Atlas, Upstash Redis, Cloudinary, Docker Compose, GitHub Actions,
Render (API), Vercel (UI).

## 6. Repository Layout

```
HealMatrix-AI/
├── backend/            FastAPI service, agents, simulator, RAG, ML, reports
├── frontend/           React + Vite single-page application
├── knowledge_base/     Source documents indexed into FAISS
├── datasets/           Generated & sample datasets
├── docs/               SRS, architecture, DB design, API spec, diagrams, manuals
├── deployment/         Render + Vercel configuration
├── docker/             Dockerfiles
├── ppt/ lean_canvas/ project_report/ poster/ concept_note/ demo_script/
└── .github/workflows/  CI/CD pipelines
```

## 7. Quick Start

### Option A — Docker (recommended)

```bash
git clone https://github.com/<you>/HealMatrix-AI.git
cd HealMatrix-AI
cp .env.example .env          # fill in GOOGLE_API_KEY at minimum
docker compose up --build
```

- API → http://localhost:8000/docs
- UI  → http://localhost:5173

### Option B — Local

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## 8. Documentation Index

| Document | Path |
|----------|------|
| Software Requirements Specification (IEEE 830) | `docs/01_requirements_srs.md` |
| System Architecture & Design | `docs/02_system_architecture.md` |
| Database Design | `docs/03_database_design.md` |
| Agent & LangGraph Design | `docs/04_agent_design.md` |
| API Specification | `docs/05_api_specification.md` |
| UI Wireframes & Design System | `docs/06_ui_wireframes.md` |
| Phase 1 Verification Report | `docs/00_phase1_verification.md` |
| Phase 2 Verification Report | `docs/00_phase2_verification.md` |
| Phase 3–6 Verification Report | `docs/00_phase3_verification.md` |
| UML / DFD Diagram Sources | `docs/diagrams/` |

## 9. Running the Tests

```bash
# Backend — 188 tests (unit, guardrail, contract, determinism, graph and
# integration suites for the agents, plus auth/clinical/analytics API tests),
# in-memory MongoDB (mongomock-motor), no external services needed.
cd backend
pip install -r requirements-dev.txt
pytest -q
ruff check app tests

# Frontend — component, hook and page-level tests (Vitest + Testing Library).
cd frontend
npm install
npm test
npm run lint
```

**Post-deploy smoke test** (hits a real running stack, not an in-memory one):

```bash
python scripts/smoke_test.py --base-url https://healmatrix-api.onrender.com
python scripts/smoke_test.py --frontend-url https://healmatrix.vercel.app
```

## 10. Deployment

Two supported paths (full detail: `docs/02_system_architecture.md` section 7):

| Path | Frontend | Backend | Database / broker | Config |
|------|----------|---------|--------------------|--------|
| Cloud | Vercel (static build) | Render (API + worker + beat, Docker) | MongoDB Atlas + Upstash Redis | `deployment/vercel/`, `deployment/render/render.yaml` |
| Self-hosted | nginx (Docker) | Docker Compose | MongoDB + Redis containers | `docker-compose.prod.yml` |

```bash
# Self-hosted, on one machine:
cp .env.example .env    # fill in every value, especially JWT_SECRET_KEY and GOOGLE_API_KEY
docker compose -f docker-compose.prod.yml up --build -d
python scripts/smoke_test.py --frontend-url http://localhost
```

## 11. Build Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Requirements, architecture, DB design, wireframes, scaffold | ✅ Complete |
| 2 | Backend APIs, auth, MongoDB integration, simulator | ✅ Complete |
| 3 | Agents, LangGraph orchestration, CrewAI, RAG | ✅ Complete |
| 4 | Frontend implementation | ✅ Complete |
| 5 | Analytics, dashboards, reports, notifications | ✅ Complete |
| 6 | Testing, Docker, CI/CD, deployment | ✅ Complete |
| 7 | Documentation suite | ✅ Complete |
| 8 | PPT, Lean Canvas, concept note, poster, demo script | ✅ Complete |

## 12. License

MIT — see `LICENSE`.
