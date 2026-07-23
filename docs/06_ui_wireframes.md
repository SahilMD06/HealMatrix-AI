# UI Wireframes & Design System
## HealMatrix AI

Version 1.0 · Lineage: Stripe · Linear · Vercel · Notion · Microsoft Fluent

---

## 1. Design System

### 1.1 Colour tokens
Declared once in `frontend/src/styles/index.css` as HSL channels, consumed through Tailwind
semantic classes so a single class works in both themes.

| Token | Light | Dark | Used for |
|-------|-------|------|----------|
| `background` | `210 40% 98%` | `222 47% 7%` | Page canvas |
| `foreground` | `222 47% 11%` | `210 40% 96%` | Body text |
| `card` | `0 0% 100%` | `222 43% 11%` | Surfaces |
| `primary` | `173 80% 36%` | `173 70% 45%` | Teal — brand, primary actions |
| `accent` | `199 89% 48%` | `199 89% 56%` | Sky — data highlights |
| `destructive` | `0 72% 51%` | `0 63% 51%` | Critical alerts |
| `muted-foreground` | `215 16% 47%` | `215 20% 65%` | Secondary text |

**Domain palettes** — triage acuity `triage-1…5` (red → orange → amber → green → cyan) and
sustainability status `sustain-excellent/good/fair/poor`. These are semantic, not decorative:
a triage-2 chip is the same orange everywhere in the product.

### 1.2 Typography
Inter (400/500/600/700/800), JetBrains Mono for metric readouts and IDs.

| Style | Size / weight | Use |
|-------|---------------|-----|
| Display | 48px / 800 / -0.02em | Landing hero |
| H1 | 30px / 700 | Page title |
| H2 | 20px / 600 | Section |
| Body | 14px / 400 / 1.6 | Default |
| Caption | 12px / 500 | Labels, chips |
| Metric | 32px / 700 mono | KPI value |

### 1.3 Spacing, radius, elevation
8-pt grid (4, 8, 12, 16, 24, 32, 48, 64). Radius `--radius: 0.75rem` with `md`/`sm` derived.
Three elevation levels: flat (`border` only), `shadow-elevated` (cards on hover), and
`shadow-glass` (glassmorphic overlays, `backdrop-blur-xl` over a 62–72 % translucent surface).

### 1.4 Component inventory
`Button` (5 variants × 3 sizes) · `Card` · `Badge` · `StatCard` · `DataTable` (sort, filter,
paginate, empty and loading states) · `Modal` · `Drawer` · `Tabs` · `Select` · `Switch` ·
`Tooltip` · `Toast` · `Skeleton` · `EmptyState` · `ErrorState` · `AgentCard` · `TriageChip` ·
`SustainabilityGauge` · `TimeRangePicker` · chart wrappers (`LineChart`, `AreaChart`, `BarChart`,
`DonutChart`, `HeatMap`) · `HospitalMap` · `FloorPlan`.

### 1.5 Accessibility
WCAG 2.1 AA contrast on every token pair. Full keyboard navigation with a visible
`focus-ring`. All icon-only controls carry `aria-label`. Status is never conveyed by colour
alone — every acuity chip also carries its numeral and label. `prefers-reduced-motion` disables
all animation.

### 1.6 Responsive breakpoints
`sm` 640 · `md` 768 · `lg` 1024 · `xl` 1280 · `2xl` 1440 (container max). Below `lg` the sidebar
collapses to a bottom tab bar; data tables become stacked cards; the digital twin switches from
split map/floorplan to a tabbed view.

---

## 2. Application Shell

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ┌──────────┐  Search (⌘K)          [Hospital ▾] [🔔 3] [☀/🌙] [Avatar ▾]  │ 64px
│ │HealMatrix│──────────────────────────────────────────────────────────────│
│ │    AI    │                                                              │
│ ├──────────┤   ┌────────────────────────────────────────────────────────┐ │
│ │ Overview │   │                                                        │ │
│ │ Patients │   │                                                        │ │
│ │ Beds     │   │                  PAGE CONTENT                          │ │
│ │ Inventory│   │              max-width 1440, 24px gutter                │ │
│ │ Emergency│   │                                                        │ │
│ │ Sustain. │   │                                                        │ │
│ │ Twin     │   │                                                        │ │
│ │ Agents   │   │                                                        │ │
│ │ Analytics│   │                                                        │ │
│ │ Reports  │   │                                                        │ │
│ ├──────────┤   │                                                        │ │
│ │ Assistant│   │                                                        │ │
│ │ Settings │   └────────────────────────────────────────────────────────┘ │
│ └──────────┘                                                              │
│   240px                                                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

Sidebar items are filtered by role — a pharmacist never sees a nav item they cannot open.
The header hospital switcher only appears for network-level admins and managers.

---

## 3. Landing Page *(public)*

```
┌────────────────────────────────────────────────────────────────────────┐
│  HealMatrix AI      Product  Agents  SDGs  Docs      [Sign in] [Demo]  │
├────────────────────────────────────────────────────────────────────────┤
│                      ░ grid backdrop, radial mask ░                    │
│               ┌─────────────────────────────────────┐                  │
│               │  ✦ 10 collaborating AI agents       │  ← eyebrow chip  │
│               └─────────────────────────────────────┘                  │
│                                                                        │
│            Empowering Sustainable Hospitals Through                    │
│                  Collaborative Agentic AI                              │
│                       (gradient headline)                              │
│                                                                        │
│      Autonomous agents that cut waiting times and carbon at once.      │
│                                                                        │
│              [ Explore the platform ]   [ Watch demo ▸ ]               │
│                                                                        │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │      glassmorphic product screenshot, subtle 3D tilt         │     │
│   └──────────────────────────────────────────────────────────────┘     │
├────────────────────────────────────────────────────────────────────────┤
│   38% ↓ triage time  │  22% ↓ energy  │  31% ↓ waste  │  6 SDGs        │
├────────────────────────────────────────────────────────────────────────┤
│  THE AGENT NETWORK — animated LangGraph topology, nodes pulse on hover  │
├────────────────────────────────────────────────────────────────────────┤
│  HOW IT WORKS — 4 steps: Observe → Reason → Reconcile → Recommend      │
├────────────────────────────────────────────────────────────────────────┤
│  SDG ALIGNMENT — 6 cards, SDG 3 featured full-width                    │
├────────────────────────────────────────────────────────────────────────┤
│  ARCHITECTURE — interactive layer diagram                              │
├────────────────────────────────────────────────────────────────────────┤
│  Footer: product · docs · GitHub · academic disclaimer                 │
└────────────────────────────────────────────────────────────────────────┘
```

Motion: hero fades and rises 12px on mount; sections reveal at 20 % viewport intersection;
the agent topology animates message flow along edges on a 4 s loop.

---

## 4. Authentication

```
┌───────────────────────────┬────────────────────────────────────────┐
│                           │                                        │
│   ░ animated gradient ░   │        Welcome back                    │
│                           │        Sign in to HealMatrix AI        │
│   "Empowering             │                                        │
│    Sustainable            │   Email     [_________________]        │
│    Hospitals Through      │   Password  [_________________] 👁      │
│    Collaborative          │                                        │
│    Agentic AI."           │   ☐ Remember me      Forgot password?  │
│                           │                                        │
│   ● ● ○  rotating         │        [      Sign in      ]           │
│         testimonials      │                                        │
│                           │   ── Demo accounts ──                  │
│                           │   [Admin] [Doctor] [Nurse]             │
│                           │   [Pharmacist] [Manager] [Sustain.]    │
│                           │                                        │
└───────────────────────────┴────────────────────────────────────────┘
```

The six demo-account buttons one-click populate credentials — essential for a viva or hackathon
demo where switching roles quickly matters. Errors appear inline under the field, never as a
bare toast. On success the user lands on their role's home route from `ROLE_HOME`.

---

## 5. Dashboards

### 5.1 Admin Dashboard
```
Row 1  [Total Users 60] [Active Agents 10/10] [Cycles Today 24] [Fallback Rate 3%]
Row 2  ┌── Agent Health Matrix (10 tiles) ────────┬── System Status ──────────┐
       │ each tile: name, last run, p95 latency,  │ MongoDB      ● up 42ms    │
       │ fallback %, sparkline of 24h runs        │ Redis        ● up  8ms    │
       │ colour = green/amber/red by fallback rate│ Gemini       ● configured │
       │                                          │ Celery       ● 2 workers  │
       │                                          │ FAISS        ● 1,284 chunks│
       └──────────────────────────────────────────┴───────────────────────────┘
Row 3  ┌── Recent Agent Runs (DataTable) ─────────┬── Audit Trail ────────────┐
       │ run_id · trigger · agents · duration ·   │ user · action · resource  │
       │ status · [View reasoning →]              │ · time                    │
       └──────────────────────────────────────────┴───────────────────────────┘
Row 4  Simulator control: [▶ Start] [■ Stop] tick 1,482 · seed 42
       Inject scenario: [Mass casualty][Outbreak][Power failure][Water main]
```

### 5.2 Doctor Dashboard
```
Row 1  [My Patients 12] [Critical 2] [Awaiting Review 5] [Avg Wait 14m]
Row 2  ┌── Triage Queue (live, ESI-ordered) ──────────────────────────────────┐
       │ ▊1  Patient 4821 · 63M · chest pain     · CARDIO · 00:02 · [Open]   │
       │ ▊2  Patient 4822 · 41F · breathlessness · PULMO  · 00:07 · [Open]   │
       │ ▊3  Patient 4823 · 28M · laceration     · ORTHO  · 00:21 · [Open]   │
       │ left bar colour = triage-1..5, row pulses when past target minutes  │
       └─────────────────────────────────────────────────────────────────────┘
Row 3  ┌── Agent Rationale panel ──────────┬── My Ward Occupancy ────────────┐
       │ "Shock index 1.23 with            │  donut: 34 occupied / 40        │
       │  hypotension and hypoxaemia…"     │  expected discharges 24h: 6     │
       │  confidence 0.91 · triage_esi@1.0 │                                 │
       │  ⚠ Advisory only — confirm before │                                 │
       │    acting                          │                                │
       └───────────────────────────────────┴─────────────────────────────────┘
Row 4  Voice assistant dock (bottom-right FAB, expands to a query panel)
```

### 5.3 Emergency Dashboard
```
Row 1  [Active Calls 4] [Ambulances Idle 3/12] [Avg Response 9.4m] [ED Load 82%]
Row 2  ┌── Live Map (Leaflet, 60% width) ─────────┬── Dispatch Queue ─────────┐
       │  hospital pins sized by capacity          │ P1 · Cardiac · 2.4km     │
       │  ambulance markers with heading + pulse   │    → AMB-07 ETA 6m       │
       │  active routes drawn as polylines         │ P2 · RTA · 5.1km         │
       │  call markers colour-coded by priority    │    → AMB-03 ETA 11m      │
       └───────────────────────────────────────────┴──────────────────────────┘
Row 3  ┌── Response Time Distribution ─────┬── Nearest Suitable Hospital ─────┐
       │ histogram + P50/P90 markers       │ ranked list with capability match│
       │                                   │ and live capacity, not just km   │
       └───────────────────────────────────┴──────────────────────────────────┘
```

### 5.4 Inventory Dashboard
```
Row 1  [SKUs 180] [Expiring ≤30d 14] [Below Reorder 9] [Value at Risk ₹4.2L]
Row 2  ┌── Expiry Risk Heatmap ────────────┬── Demand Forecast ──────────────┐
       │ SKU × weeks-to-expiry, cell shade │ actual vs 30d forecast, with     │
       │ = units at risk                   │ 80% prediction band              │
       └───────────────────────────────────┴──────────────────────────────────┘
Row 3  ┌── Inter-Hospital Transfer Proposals ────────────────────────────────┐
       │ Amoxicillin 500mg · HM-BLR-02 → HM-BLR-01 · 1,200 units             │
       │ expires in 24d · recipient consumes in 18d                          │
       │ saves ₹38,400 · avoids 62 kg CO₂e   [Reject] [Approve transfer]     │
       └─────────────────────────────────────────────────────────────────────┘
Row 4  Full inventory DataTable — search, category filter, expiry sort
```

### 5.5 Sustainability Dashboard
```
Row 1  ┌── Sustainability Score ─────┬─────────────────────────────────────────┐
       │      ╭───────╮              │  Energy  ████████░░ 78                  │
       │      │  74   │  Grade B     │  Water   ██████░░░░ 65                  │
       │      │ /100  │  ▲ 6 vs LM   │  Waste   ███████░░░ 71                  │
       │      ╰───────╯              │  Carbon  ████████░░ 80                  │
       └─────────────────────────────┴─────────────────────────────────────────┘
Row 2  [Energy 12.4 MWh ▼8%] [Water 486 kL ▼4%] [Waste 1.9 t ▼11%] [CO₂e 9.1 t ▼7%]
Row 3  ┌── Energy: consumption vs forecast ─┬── Source mix over time ──────────┐
       │ line + dashed forecast, HVAC band  │ stacked area grid/solar/DG       │
       └────────────────────────────────────┴──────────────────────────────────┘
Row 4  ┌── Waste by CPCB category ──────────┬── Water & leak signals ──────────┐
       │ stacked bars, yellow/red/white/blue│ usage line + leak-probability     │
       │ + diversion rate line              │ markers, critical flagged red     │
       └────────────────────────────────────┴──────────────────────────────────┘
Row 5  ┌── Reduction Opportunities (ranked by tCO₂e per ₹) ───────────────────┐
       │ 1. Shift OT HVAC schedule    · 14.2 tCO₂e · ₹0 · payback immediate   │
       │ 2. 120 kWp rooftop solar     · 96.0 tCO₂e · ₹48L · 61 months         │
       │ 3. Autoclave over incinerate · 22.8 tCO₂e · ₹6L · 19 months          │
       └─────────────────────────────────────────────────────────────────────┘
```

### 5.6 Executive Dashboard
```
Row 1  ┌── Executive Summary (agent-generated prose, 3 short paragraphs) ─────┐
       │ generated 08:00 · run b41d8c9a · [Regenerate] [Export PDF]           │
       └─────────────────────────────────────────────────────────────────────┘
Row 2  [Occupancy 84%] [Avg LOS 4.2d] [Sustainability 74] [Cost/Bed-day ₹3,180]
Row 3  ┌── Action Plan ──────────────────────────────────────────────────────┐
       │ ▲ HIGH  Open 4 ICU overflow beds by 14:00                           │
       │         owner: Manager · source: bed_allocation · impact: −18% risk │
       │ ▲ HIGH  Approve amoxicillin transfer from HM-BLR-02                 │
       │         owner: Pharmacist · source: medicine_intelligence           │
       │ ◆ MED   Shift OT HVAC pre-cool to 05:30                             │
       │         owner: Sustainability Officer · source: energy_optimization │
       └─────────────────────────────────────────────────────────────────────┘
Row 4  ┌── Conflicts Resolved ─────────────┬── Risk Register ────────────────┐
       │ energy wanted ICU HVAC setback;   │ ICU capacity     ▲▲▲ high        │
       │ bed_allocation opening overflow.  │ Dengue surge     ▲▲  medium      │
       │ Resolved: patient safety > cost.  │ Amoxicillin      ▲▲  medium      │
       └───────────────────────────────────┴─────────────────────────────────┘
Row 5  Hospital comparison table across the network (occupancy, score, cost)
```

---

## 6. Digital Twin

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Layers: [Beds ✓][ICU ✓][Emergency ✓][Ambulances ✓][Waste][Energy][Water]│
├──────────────────────────────────┬──────────────────────────────────────┤
│  NETWORK MAP (Leaflet)           │  FLOOR PLAN (SVG, floor selector)    │
│                                  │   ┌────┬────┬────┬────┐              │
│   ◉ HM-BLR-01  84% ▲             │   │▓▓░░│▓▓▓▓│░░░░│▓░░░│  Floor 3     │
│   ◉ HM-BLR-02  61%               │   ├────┼────┼────┼────┤              │
│   ◉ HM-BLR-03  92% ▲▲            │   │▓▓▓░│░░░░│▓▓░░│▓▓▓▓│  Floor 2     │
│   🚑 AMB-07 ──▶ route            │   └────┴────┴────┴────┘              │
│                                  │   ▓ occupied  ░ available            │
│  pin size = capacity             │   hover a bed → patient, ESI, LOS    │
│  pin colour = occupancy band     │   click → admission detail drawer    │
├──────────────────────────────────┴──────────────────────────────────────┤
│  Live strip: Energy 512 kW · Water 18.4 L/min · Waste bins 3 due · 4 OT  │
└─────────────────────────────────────────────────────────────────────────┘
```

Overlay layers recolour the floorplan: Energy tints rooms by kWh intensity, Water flags zones
with a leak signal, Waste marks bins approaching their storage limit.

---

## 7. Voice Assistant

A floating action button, bottom-right on every authenticated page. Expanding it opens a
480px panel:

```
┌── HealMatrix Assistant ───────────────────────┐
│  🎙  "Which ICU beds are available?"          │
│      ▁▃▅▇▅▃▁  listening…                      │
├───────────────────────────────────────────────┤
│  4 ICU beds are available: CCU-02, CCU-05,    │
│  MICU-08 and MICU-11. Two more are expected   │
│  to free up before 18:00.                     │
│                                               │
│  ┌─ Supporting data ──────────────────────┐   │
│  │ Bed      Ward   Features               │   │
│  │ CCU-02   CCU    ventilator, monitor    │   │
│  │ …                                       │   │
│  └────────────────────────────────────────┘   │
│  Source: live bed inventory · 2s ago          │
├───────────────────────────────────────────────┤
│  Try: "Which medicines expire this week?"     │
│       "Show carbon emissions"                 │
│       "Generate sustainability report"        │
└───────────────────────────────────────────────┘
```

Answers grounded in the knowledge base cite the source document and section. When retrieval
finds nothing above the score threshold, the assistant says the knowledge base does not cover
the question rather than improvising.

---

## 8. State Patterns

Every data view implements four states, in this order of implementation:

| State | Treatment |
|-------|-----------|
| **Loading** | Skeleton matching the final layout's shape — never a centred spinner |
| **Empty** | Illustration, one-line explanation, and the primary action that resolves it |
| **Error** | Error code, plain-language message, correlation ID, and a Retry button |
| **Success** | The data |

Toasts (`sonner`) are reserved for the outcome of user-initiated actions. Agent-generated
alerts go to the notification centre, and only `critical` severity also raises a toast.

---

## 9. Motion Guidelines

| Interaction | Duration | Easing |
|-------------|----------|--------|
| Hover / focus | 150ms | ease-out |
| Card entrance | 300ms, 40ms stagger | ease-out |
| Page transition | 250ms fade + 8px rise | ease-in-out |
| Drawer / modal | 200ms | spring, damping 25 |
| Chart draw-in | 600ms | ease-out |
| Agent-active pulse | 1.8s loop | cubic-bezier(.24,0,.38,1) |

All of it is suppressed under `prefers-reduced-motion`.
