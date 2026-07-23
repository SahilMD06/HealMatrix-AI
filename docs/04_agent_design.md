# Agent Design Specification
## HealMatrix AI — 10 Agents, LangGraph Orchestration, CrewAI Synthesis

Version 1.0

---

## 1. Agent Contract

Every agent implements the same interface, so the orchestrator treats them uniformly and
observability is free:

```python
class BaseAgent(ABC):
    name: str          # e.g. "patient_triage"
    version: str       # e.g. "1.0.0" - persisted with every decision

    @abstractmethod
    async def analyse(self, state: HealMatrixState) -> AgentResult:
        """Primary path. May call ML models, RAG and Gemini."""

    @abstractmethod
    def fallback(self, state: HealMatrixState) -> AgentResult:
        """Deterministic path. Must never raise and must never call the network."""

    async def run(self, state: HealMatrixState) -> AgentResult:
        """Template method: timing, retry, fallback, logging, message emission."""
```

`AgentResult` is uniform:

```python
class AgentResult(BaseModel):
    agent: str
    version: str
    output: dict            # agent-specific, schema-validated
    rationale: str          # human-readable explanation
    confidence: float       # 0.0 - 1.0
    messages: list[AgentMessage]   # what this agent tells its peers
    used_fallback: bool
    duration_ms: int
    status: Literal["success", "degraded", "failed"]
```

**Design rule:** agents call *services*, never repositories. A bed cannot be double-booked by an
agent because the same `BedService.reserve()` invariant applies to agents and humans alike.

---

## 2. Per-Agent Specification

### 2.1 Patient Triage Agent
- **Trigger:** `patient_arrival`
- **Inputs:** vitals, age, sex, chief complaint, comorbidities, active department list
- **Pipeline:** red-flag rule pass → XGBoost `triage_esi` → Gemini rationale → department mapping
- **Output:** `{esi_level, confidence, recommended_department_code, rationale, red_flags[], target_response_minutes}`
- **Guardrail:** red flags (SpO₂ < 90 % with RR > 30; GCS ≤ 8; SBP < 90 with HR > 120) force ESI 1
  and cannot be overridden by the model or the LLM.
- **Messages emitted:** `→ bed_allocation {esi, department}`, `→ disease_forecast {disease_category}`

### 2.2 Disease Forecast Agent
- **Trigger:** every cycle
- **Inputs:** 90 days of admissions by category, seasonal calendar, current census
- **Pipeline:** lag/seasonality feature build → XGBoost `admissions_14d` → ICU demand derivation →
  outbreak test (> 2σ over baseline for 3 consecutive days)
- **Output:** `{forecast_14d[], icu_demand{p50,p80}, outbreak_warnings[], recommended_preallocation}`
- **Messages emitted:** `→ bed_allocation {icu_demand}`, `→ medicine_intelligence {expected_case_mix}`,
  `broadcast {outbreak_warning}`

### 2.3 Bed Allocation Agent
- **Trigger:** `patient_arrival`, plus every cycle for occupancy optimisation
- **Inputs:** triage result, ICU forecast, live bed inventory, isolation and sex-ward rules
- **Pipeline:** candidate filter → weighted scoring (severity fit 0.35, department match 0.25,
  proximity 0.15, expected-discharge headroom 0.15, isolation compliance 0.10) → LOS prediction →
  30-minute reservation
- **Output:** `{recommended_bed_id, alternatives[], predicted_los_days, occupancy_rate, expected_discharges_24h, escalation}`
- **Guardrail:** never selects `maintenance` or already-reserved beds; ICU ≥ 90 % triggers overflow protocol
- **Messages emitted:** `→ carbon_intelligence {census_delta}`, `→ executive {capacity_risk}`

### 2.4 Medicine Intelligence Agent
- **Trigger:** daily scan and every cycle
- **Inputs:** inventory across the network, consumption history, case-mix forecast, cold-chain flags
- **Pipeline:** per-SKU demand forecast → expiry-risk scoring → reorder-point recomputation →
  network transfer optimisation (donor near-expiry surplus matched to recipient forecast demand)
- **Output:** `{expiry_alerts[], low_stock_alerts[], demand_forecast[], transfer_proposals[]}`
  where each proposal carries `units_saved`, `value_saved_paise`, `co2e_avoided_kg`
- **Guardrail:** cold-chain SKUs are excluded unless both sites and the route are cold-chain capable
- **Messages emitted:** `→ carbon_intelligence {avoided_waste_kg}`, `→ executive {stockout_risk}`

### 2.5 Energy Optimization Agent
- **Inputs:** 30 days of hourly consumption by zone, outside temperature, occupancy, equipment state
- **Pipeline:** 24 h load forecast → per-zone HVAC setpoint optimisation under clinical limits →
  idle-draw anomaly scan → solar shift and payback calculation
- **Output:** `{forecast_24h[], hvac_recommendations[], anomalies[], renewable_potential, projected_savings_kwh}`
- **Guardrail:** OT and ICU setpoints are hard-clamped to 20–24 °C; recommendations outside
  `HVAC_SETPOINT_LIMITS` are discarded, not merely warned about
- **Messages emitted:** `→ carbon_intelligence {projected_kwh, source_mix}`

### 2.6 Water Conservation Agent
- **Inputs:** hourly consumption, night minimum flow, occupancy, roof area, rainfall
- **Pipeline:** IsolationForest on night-flow features → leak probability → loss estimation →
  harvesting yield → intervention ranking by litres saved per rupee
- **Output:** `{forecast_daily[], leak_signals[], harvesting_potential_l, recommendations[]}`
- **Escalation:** leak probability > 0.8 emits a `critical` notification immediately, without
  waiting for the executive cycle
- **Messages emitted:** `→ carbon_intelligence {water_kl}`

### 2.7 Biomedical Waste Agent
- **Inputs:** waste records by department and category, department waste profiles, CPCB corpus
- **Pipeline:** RAG-grounded category classification → generation forecast → segregation anomaly
  detection → pickup scheduling within the 48 h yellow-category limit → recyclable recovery estimate
- **Output:** `{classification, forecast_kg[], segregation_anomalies[], pickup_schedule[], diversion_rate, citations[]}`
- **Guardrail:** every classification response cites the CPCB rule chunk it relied on; unsupported
  classifications are returned as "requires manual review"
- **Messages emitted:** `→ carbon_intelligence {waste_by_method}`

### 2.8 Carbon Intelligence Agent
- **Deterministic by design** — no LLM in the calculation path, so figures are reproducible.
- **Inputs:** energy source mix, water volume, waste by disposal method, ambulance fuel, anaesthetic gas usage
- **Pipeline:** apply versioned emission factors → aggregate Scope 1/2/3 → normalise per bed-day →
  weighted sustainability score → rank reduction levers by tCO₂e per rupee
- **Output:** `{scope1, scope2, scope3, total_kg, per_bed_day_kg, sustainability_score{...,grade}, reduction_opportunities[]}`
- **Messages emitted:** `→ executive {sustainability_score, top_levers}`

### 2.9 Ambulance Dispatch Agent
- **Inputs:** live fleet positions and status, call location and priority, hospital capabilities and capacity
- **Pipeline:** capability filter → capacity filter → OSRM route per candidate → ETA ranking →
  pre-emption check against lower-priority active assignments
- **Output:** `{assigned_ambulance_id, destination_hospital_id, eta_minutes, distance_km, route_polyline, preempted_call_id}`
- **Key distinction:** selects the nearest *suitable* hospital, not the nearest hospital — a cardiac
  call is not routed to a site without a cath lab
- **Messages emitted:** `→ bed_allocation {inbound_patient_eta}`, `→ carbon_intelligence {fuel_litres}`

### 2.10 Executive Decision Agent
- **Framework:** CrewAI crew invoked inside a LangGraph node
- **Crew roles:**
  | Role | Goal |
  |------|------|
  | Operations Analyst | Extract the operational picture from all nine agent outputs |
  | Sustainability Auditor | Assess environmental consequence and regulatory exposure |
  | Risk Officer | Surface patient-safety and continuity risks |
  | Chief of Staff | Produce the final ranked action plan |
- **Conflict resolution order:** patient safety → regulatory compliance → cost → sustainability.
  A conflict is any pair of recommendations whose execution is mutually exclusive (e.g. energy
  proposes reducing ICU HVAC load while bed allocation is opening ICU overflow).
- **Output:** `{executive_summary, action_plan[{action, owner_role, horizon, source_agent, impact}], risk_register[], sustainability_recommendations[], conflicts_resolved[]}`

---

## 3. Prompt Engineering Strategy

1. **Structured output only.** Every LLM call requests JSON conforming to a Pydantic schema and is
   parsed with a validating parser; a parse failure triggers one repair attempt, then the fallback.
2. **Numbers come from models, not the LLM.** Gemini receives computed figures and explains them.
   It is never asked to forecast, sum or score.
3. **Grounding.** Waste, storage and protocol questions include retrieved corpus chunks; the prompt
   instructs the model to answer only from the provided evidence and to say so when it cannot.
4. **Temperature 0.2** for all operational agents; 0.4 for the executive crew where synthesis
   benefits from a little breadth.
5. **Token discipline.** Snapshots are summarised before prompting — the executive agent receives
   agent outputs, not raw telemetry.

---

## 4. Testing Strategy for Agents

| Test class | What it proves |
|------------|----------------|
| Fallback unit tests | Each `fallback()` returns a valid `AgentResult` with the LLM fully disabled |
| Guardrail tests | Red-flag vitals always yield ESI 1; OT setpoints never leave 20–24 °C; maintenance beds are never assigned |
| Contract tests | Every agent's output validates against its Pydantic schema |
| Graph tests | Conditional edges route correctly for each trigger type; the conflict loop terminates after two iterations |
| Determinism tests | Carbon calculations are byte-identical for identical inputs and factor version |
| Integration test | A full `patient_arrival` cycle writes exactly one `agent_logs` document per executed agent |
