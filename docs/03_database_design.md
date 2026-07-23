# Database Design Document
## HealMatrix AI — MongoDB Atlas

Version 1.0 · Database: `healmatrix`

---

## 1. Design Principles

1. **Tenant partitioning.** Every operational document carries `hospital_id`. It is the first
   field of nearly every compound index and is injected by the repository layer from the JWT —
   application code cannot omit it.
2. **Embed what is read together, reference what is queried independently.** Vitals embed in
   the patient's triage record; departments are referenced by ObjectId because they are
   queried on their own.
3. **Time-series collections are append-only.** `energy_logs`, `water_logs`, `waste_records`
   and `simulation_data` are never updated in place; corrections are new documents.
4. **Every document carries `created_at` / `updated_at`** in UTC, set by the base repository.
5. **Soft deletion** via `is_active` for master data; hard deletion only for simulation data.
6. **TTL indexes** cap unbounded growth on notifications (90 d) and simulation data (180 d).

Conventions: collection names are plural snake_case; field names snake_case; monetary values
in minor units (paise) as integers; all timestamps UTC ISO-8601.

---

## 2. Entity Relationship Overview

```
hospitals ──1:N── departments ──1:N── rooms ──1:N── beds
    │                                                 │
    ├──1:N── users(staff)                             │
    ├──1:N── patients ──1:N── admissions ─────────────┘
    ├──1:N── ambulances
    ├──1:N── medicines ──1:N── inventory
    ├──1:N── energy_logs / water_logs / waste_records
    ├──1:N── carbon_reports
    ├──1:N── notifications / reports / audit_logs
    └──1:N── agent_logs ──N:1── admissions (optional)

knowledge_base and simulation_data are network-scoped support collections.
```

---

## 3. Collection Specifications

### 3.1 `hospitals`
Network root. *(Added to the base 21 to support the multi-hospital tenancy model.)*

| Field | Type | Notes |
|-------|------|-------|
| `_id` | ObjectId | PK |
| `code` | string | Unique short code, e.g. `HM-BLR-01` |
| `name` | string | |
| `type` | enum | `tertiary` \| `secondary` \| `primary` \| `specialty` |
| `location` | GeoJSON Point | `{type:"Point", coordinates:[lng,lat]}` |
| `address` | object | line1, city, state, pincode |
| `capacity` | object | `total_beds`, `icu_beds`, `emergency_beds`, `ot_count` |
| `capabilities` | string[] | `cardiac`, `trauma`, `neonatal`, `burns`, `stroke`, `dialysis` |
| `sustainability` | object | `roof_area_sqm`, `solar_kwp`, `rainwater_capacity_l` |
| `grid_emission_factor` | float | kgCO₂e/kWh, region specific |
| `is_active` | bool | |

**Indexes:** `{code:1}` unique · `{location:"2dsphere"}` · `{capabilities:1, is_active:1}`

---

### 3.2 `users`

| Field | Type | Notes |
|-------|------|-------|
| `_id` | ObjectId | |
| `hospital_id` | ObjectId | null for network-level admin |
| `email` | string | lowercase, unique |
| `password_hash` | string | bcrypt, never serialised |
| `full_name` | string | |
| `role` | enum | `admin`,`doctor`,`nurse`,`pharmacist`,`manager`,`sustainability_officer` |
| `department_id` | ObjectId | nullable |
| `phone` | string | |
| `avatar_url` | string | Cloudinary |
| `preferences` | object | `theme`, `notification_channels[]`, `default_dashboard` |
| `last_login_at` | datetime | |
| `failed_login_count` | int | lockout after 5 |
| `is_active` | bool | |

**Indexes:** `{email:1}` unique · `{hospital_id:1, role:1}` · `{hospital_id:1, is_active:1}`

---

### 3.3 `staff`
Clinical roster; separates employment/scheduling data from login identity.

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `user_id` | ObjectId | nullable — not all staff have accounts |
| `employee_code` | string | unique per hospital |
| `full_name`, `designation` | string | |
| `department_id` | ObjectId | |
| `specialisation` | string[] | |
| `shift` | enum | `morning` \| `evening` \| `night` |
| `roster` | object[] | `{date, shift, status}` |
| `on_duty` | bool | |

**Indexes:** `{hospital_id:1, employee_code:1}` unique · `{hospital_id:1, department_id:1, on_duty:1}`

---

### 3.4 `departments`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `code` | string | `ED`, `ICU`, `GEN-MED`, `CARDIO`, `ORTHO`, `PEDS`, `OBG`, `ONCO` |
| `name` | string | |
| `floor` | int | |
| `bed_count` | int | denormalised counter |
| `head_staff_id` | ObjectId | |
| `hvac_zone` | string | links to energy zones |
| `waste_profile` | object | expected kg/bed-day per CPCB colour |
| `is_active` | bool | |

**Indexes:** `{hospital_id:1, code:1}` unique

---

### 3.5 `rooms`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id`, `department_id` | ObjectId | |
| `room_number` | string | |
| `type` | enum | `general`,`private`,`icu`,`isolation`,`ot`,`emergency` |
| `capacity` | int | beds in room |
| `floor` | int | |
| `coordinates` | object | `{x, y}` normalised 0–1 for digital-twin floorplan |
| `equipment_ids` | ObjectId[] | |

**Indexes:** `{hospital_id:1, room_number:1}` unique · `{hospital_id:1, type:1}`

---

### 3.6 `beds`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id`, `department_id`, `room_id` | ObjectId | |
| `bed_number` | string | |
| `type` | enum | `general`,`icu`,`hdu`,`emergency`,`isolation`,`pediatric`,`maternity` |
| `status` | enum | `available`,`occupied`,`cleaning`,`maintenance`,`reserved` |
| `current_admission_id` | ObjectId | nullable |
| `reserved_until` | datetime | nullable; 30-min hold |
| `features` | string[] | `ventilator`, `monitor`, `oxygen`, `negative_pressure` |
| `last_cleaned_at` | datetime | |
| `occupancy_history` | object[] | capped list of last 20 `{admission_id, from, to}` |

**Indexes:** `{hospital_id:1, status:1, type:1}` · `{hospital_id:1, department_id:1, status:1}` ·
`{hospital_id:1, bed_number:1}` unique · `{current_admission_id:1}` sparse

---

### 3.7 `patients`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `mrn` | string | Medical record number, unique per hospital |
| `full_name`, `age`, `sex` | | |
| `blood_group` | enum | |
| `contact` | object | phone, email, address |
| `emergency_contact` | object | |
| `comorbidities` | string[] | diabetes, hypertension, CKD, COPD … |
| `allergies` | string[] | |
| `is_synthetic` | bool | **always true** in this build |

**Indexes:** `{hospital_id:1, mrn:1}` unique · `{hospital_id:1, full_name:"text"}`

---

### 3.8 `admissions`
Central clinical event record; embeds triage since the two are always read together.

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id`, `patient_id` | ObjectId | |
| `admission_number` | string | unique |
| `source` | enum | `walk_in`,`ambulance`,`referral`,`transfer` |
| `chief_complaint` | string | |
| `vitals` | object | `heart_rate`,`systolic_bp`,`diastolic_bp`,`spo2`,`temperature_c`,`respiratory_rate`,`gcs` |
| `triage` | object | `esi_level`(1–5), `confidence`, `recommended_department_id`, `rationale`, `red_flags[]`, `model_version`, `agent_run_id` |
| `department_id`, `bed_id` | ObjectId | assigned |
| `attending_staff_id` | ObjectId | |
| `diagnosis` | object[] | `{icd_code, description, is_primary}` |
| `disease_category` | enum | `respiratory`,`cardiac`,`trauma`,`infectious`,`gi`,`neuro`,`obstetric`,`other` |
| `status` | enum | `triaged`,`admitted`,`in_treatment`,`discharged`,`transferred`,`deceased` |
| `admitted_at`, `discharged_at` | datetime | |
| `predicted_los_days`, `actual_los_days` | float | |
| `medicines_administered` | object[] | `{medicine_id, quantity, at}` |
| `outcome` | enum | `recovered`,`referred`,`lama`,`expired` |

**Indexes:** `{hospital_id:1, status:1, admitted_at:-1}` · `{patient_id:1, admitted_at:-1}` ·
`{hospital_id:1, department_id:1, status:1}` · `{hospital_id:1, disease_category:1, admitted_at:-1}` ·
`{hospital_id:1, "triage.esi_level":1, status:1}` · `{admission_number:1}` unique

---

### 3.9 `ambulances`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | home base |
| `vehicle_number` | string | unique |
| `type` | enum | `bls`,`als`,`neonatal`,`mortuary` |
| `status` | enum | `idle`,`dispatched`,`en_route_scene`,`at_scene`,`en_route_hospital`,`returning`,`maintenance` |
| `current_location` | GeoJSON Point | |
| `crew` | object[] | `{staff_id, role}` |
| `active_call` | object | `{call_id, priority(1–5), pickup:GeoJSON, destination_hospital_id, eta_minutes, distance_km, route_polyline, dispatched_at}` |
| `fuel_type` | enum | `diesel`,`petrol`,`cng`,`electric` — feeds Scope 1 carbon |
| `odometer_km` | float | |

**Indexes:** `{current_location:"2dsphere"}` · `{hospital_id:1, status:1}` ·
`{vehicle_number:1}` unique · `{"active_call.priority":-1}` sparse

---

### 3.10 `medicines`
Catalogue (network-wide master).

| Field | Type | Notes |
|-------|------|-------|
| `sku` | string | unique |
| `name`, `generic_name`, `manufacturer` | string | |
| `category` | enum | `antibiotic`,`analgesic`,`cardiac`,`emergency`,`vaccine`,`iv_fluid`,`anaesthetic`,`other` |
| `form` | enum | `tablet`,`capsule`,`injection`,`syrup`,`iv`,`inhaler` |
| `unit_price_paise` | int | |
| `storage` | object | `{min_temp_c, max_temp_c, cold_chain:bool, light_sensitive:bool}` |
| `is_critical` | bool | stock-out is a patient-safety event |
| `carbon_kg_per_unit` | float | embodied emissions for Scope 3 |

**Indexes:** `{sku:1}` unique · `{category:1}` · `{name:"text", generic_name:"text"}`

---

### 3.11 `inventory`
Batch-level stock, per hospital.

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id`, `medicine_id` | ObjectId | |
| `batch_number` | string | |
| `quantity`, `reserved_quantity` | int | |
| `expiry_date`, `received_date` | date | |
| `unit_cost_paise` | int | |
| `reorder_point`, `max_stock` | int | computed by agent |
| `storage_location` | string | |
| `status` | enum | `active`,`quarantined`,`expired`,`transferred_out`,`consumed` |
| `transfer_history` | object[] | `{to_hospital_id, quantity, at, agent_run_id}` |

**Indexes:** `{hospital_id:1, medicine_id:1, expiry_date:1}` · `{hospital_id:1, expiry_date:1, status:1}` ·
`{hospital_id:1, quantity:1}` · `{medicine_id:1, expiry_date:1}` (network transfer search)

---

### 3.12 `energy_logs`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `timestamp` | datetime | hourly granularity |
| `zone` | string | HVAC/department zone |
| `consumption_kwh` | float | |
| `source_mix` | object | `{grid_kwh, solar_kwh, dg_kwh}` |
| `hvac_kwh`, `equipment_kwh`, `lighting_kwh` | float | |
| `outside_temp_c`, `setpoint_c`, `occupancy_ratio` | float | |
| `cost_paise` | int | |
| `emission_kg` | float | derived: grid_kwh × factor + dg_kwh × dg_factor |

**Indexes:** `{hospital_id:1, timestamp:-1}` · `{hospital_id:1, zone:1, timestamp:-1}`

---

### 3.13 `water_logs`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `timestamp` | datetime | |
| `zone` | string | |
| `consumption_litres` | float | |
| `night_min_flow_lpm` | float | leak indicator |
| `source` | object | `{municipal_l, borewell_l, rainwater_l, recycled_l}` |
| `leak_probability` | float | 0–1, agent-written |
| `leak_estimated_loss_lpd` | float | |
| `occupancy_ratio` | float | |

**Indexes:** `{hospital_id:1, timestamp:-1}` · `{hospital_id:1, leak_probability:-1}`

---

### 3.14 `waste_records`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id`, `department_id` | ObjectId | |
| `date` | date | |
| `category` | enum | `yellow`,`red`,`white`,`blue`,`general` (CPCB) |
| `weight_kg` | float | |
| `segregation_score` | float | 0–1, anomaly-detector output |
| `disposal_method` | enum | `incineration`,`autoclave`,`microwave`,`deep_burial`,`recycling`,`landfill` |
| `treatment_facility` | string | CBWTF name |
| `pickup` | object | `{scheduled_at, collected_at, status, vendor}` |
| `emission_kg` | float | method-specific factor × weight |
| `recyclable_recovered_kg` | float | |

**Indexes:** `{hospital_id:1, date:-1, category:1}` · `{hospital_id:1, "pickup.status":1}` ·
`{hospital_id:1, department_id:1, date:-1}`

---

### 3.15 `carbon_reports`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `period` | object | `{start, end, granularity}` |
| `scope1_kg` | object | `{diesel_generator, ambulance_fuel, anaesthetic_gases, total}` |
| `scope2_kg` | object | `{grid_electricity, total}` |
| `scope3_kg` | object | `{waste_treatment, water, procurement, staff_commute, total}` |
| `total_kg`, `per_bed_day_kg` | float | |
| `sustainability_score` | object | `{energy, water, waste, carbon, overall}` each 0–100 |
| `reduction_opportunities` | object[] | `{lever, tco2e_abated, cost_paise, payback_months, priority}` |
| `emission_factor_version` | string | reproducibility |
| `generated_by_agent_run_id` | ObjectId | |

**Indexes:** `{hospital_id:1, "period.end":-1}` · `{hospital_id:1, "sustainability_score.overall":-1}`

---

### 3.16 `agent_logs`
The audit trail of machine reasoning — the collection that makes the project defensible.

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `run_id` | UUID | groups all agents in one graph execution |
| `agent_name` | string | |
| `agent_version` | string | |
| `triggered_by` | enum | `patient_arrival`,`scheduled_cycle`,`manual`,`scenario` |
| `input_summary` | object | redacted inputs |
| `output` | object | the agent's structured result |
| `rationale` | string | natural-language explanation |
| `confidence` | float | |
| `messages_emitted` | object[] | inter-agent messages |
| `used_fallback` | bool | |
| `llm` | object | `{model, prompt_tokens, completion_tokens, latency_ms}` |
| `duration_ms` | int | |
| `status` | enum | `success`,`degraded`,`failed` |
| `error` | object | nullable |
| `correlation_id` | string | ties back to the HTTP request |

**Indexes:** `{hospital_id:1, created_at:-1}` · `{run_id:1}` · `{agent_name:1, created_at:-1}` ·
`{hospital_id:1, status:1, created_at:-1}`

---

### 3.17 `simulation_data`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `tick` | int | monotonically increasing |
| `stream` | enum | one of the 13 generators |
| `payload` | object | generated event |
| `scenario` | string | nullable, e.g. `outbreak_surge` |
| `seed` | int | reproducibility |
| `created_at` | datetime | **TTL 180 days** |

**Indexes:** `{hospital_id:1, tick:-1}` · `{stream:1, created_at:-1}` ·
`{created_at:1}` TTL 15552000 s

---

### 3.18 `knowledge_base`
Chunk registry mirroring the FAISS index (FAISS stores vectors; Mongo stores text + metadata).

| Field | Type | Notes |
|-------|------|-------|
| `doc_id`, `chunk_id` | string | `chunk_id` unique |
| `faiss_index_position` | int | row in the FAISS matrix |
| `source_document`, `section` | string | |
| `category` | enum | `who`,`bmw_rules`,`sop`,`emergency`,`policy`,`medicine_storage`,`energy`,`water` |
| `content` | string | chunk text |
| `token_count` | int | |
| `embedding_model`, `index_version` | string | |

**Indexes:** `{chunk_id:1}` unique · `{category:1}` · `{faiss_index_position:1}` · `{content:"text"}`

---

### 3.19 `notifications`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `type` | enum | `medicine_expiry`,`emergency_alert`,`waste_pickup`,`bed_availability`,`water_leak`,`high_energy`,`outbreak_warning` |
| `severity` | enum | `info`,`warning`,`critical` |
| `title`, `message` | string | |
| `target_roles` | string[] | fan-out by role |
| `target_user_ids` | ObjectId[] | optional direct targeting |
| `entity_ref` | object | `{collection, id}` deep link |
| `source_agent`, `agent_run_id` | | provenance |
| `action_url` | string | |
| `read_by` | object[] | `{user_id, read_at}` |
| `acknowledged_by` | object | `{user_id, at, note}` |
| `expires_at` | datetime | **TTL 90 days** |

**Indexes:** `{hospital_id:1, created_at:-1}` · `{hospital_id:1, target_roles:1, severity:1}` ·
`{expires_at:1}` TTL 0

---

### 3.20 `reports`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id` | ObjectId | |
| `type` | enum | `hospital_performance`,`sustainability`,`carbon`,`energy`,`waste`,`water`,`executive_summary` |
| `period` | object | `{start, end}` |
| `status` | enum | `queued`,`generating`,`ready`,`failed` |
| `file_url` | string | Cloudinary secure URL |
| `file_size_bytes`, `page_count` | int | |
| `summary` | object | headline KPIs rendered on the card |
| `generated_by` | ObjectId | user |
| `celery_task_id` | string | |

**Indexes:** `{hospital_id:1, type:1, "period.end":-1}` · `{status:1}` · `{celery_task_id:1}` sparse

---

### 3.21 `audit_logs`

| Field | Type | Notes |
|-------|------|-------|
| `hospital_id`, `user_id` | ObjectId | |
| `action` | enum | `create`,`update`,`delete`,`login`,`logout`,`export`,`agent_override` |
| `resource` | object | `{collection, id}` |
| `changes` | object | `{before, after}` — diff only |
| `ip_address`, `user_agent` | string | |
| `correlation_id` | string | |
| `created_at` | datetime | append-only, 365-day retention |

**Indexes:** `{hospital_id:1, created_at:-1}` · `{user_id:1, created_at:-1}` ·
`{"resource.collection":1, "resource.id":1}`

---

## 4. Representative Aggregation Pipelines

**Live bed occupancy by department**
```js
db.beds.aggregate([
  { $match: { hospital_id: HID } },
  { $group: { _id: { dept: "$department_id", status: "$status" }, n: { $sum: 1 } } },
  { $group: { _id: "$_id.dept",
              breakdown: { $push: { k: "$_id.status", v: "$n" } },
              total: { $sum: "$n" } } },
  { $lookup: { from: "departments", localField: "_id", foreignField: "_id", as: "d" } },
  { $project: { department: { $first: "$d.name" }, total: 1,
                breakdown: { $arrayToObject: "$breakdown" } } }
])
```

**Near-expiry stock transferable across the network**
```js
db.inventory.aggregate([
  { $match: { status: "active",
              expiry_date: { $lte: ISODate(<today+90d>) },
              quantity: { $gt: 0 } } },
  { $group: { _id: { med: "$medicine_id", hosp: "$hospital_id" },
              qty: { $sum: "$quantity" },
              earliest_expiry: { $min: "$expiry_date" } } },
  { $group: { _id: "$_id.med",
              holdings: { $push: { hospital_id: "$_id.hosp", qty: "$qty",
                                   expiry: "$earliest_expiry" } } } },
  { $match: { "holdings.1": { $exists: true } } }   // ≥2 hospitals ⇒ transfer candidate
])
```

**14-day admissions trend by disease category**
```js
db.admissions.aggregate([
  { $match: { hospital_id: HID, admitted_at: { $gte: ISODate(<today-14d>) } } },
  { $group: { _id: { d: { $dateToString: { format: "%Y-%m-%d", date: "$admitted_at" } },
                     c: "$disease_category" },
              n: { $sum: 1 } } },
  { $sort: { "_id.d": 1 } }
])
```

---

## 5. Seeding & Migration

`scripts/seed_database.py` creates: 4 hospitals, 8 departments each, ~120 rooms, ~400 beds,
60 users across all six roles, 180 medicine SKUs, 12 ambulances, and 18 months of backfilled
energy/water/waste/admission history for model training. It is idempotent and gated behind
`--force` when the database is non-empty.

Index creation runs at application startup in `app/database/indexes.py`, which is safe to
re-run — `create_index` is idempotent in MongoDB.
