"""Synthetic hospital telemetry generators.

Every generator is driven by a single seeded ``numpy`` Generator, so a given seed
reproduces an identical hospital history — which is what makes the ML training
results in the report reproducible.

The distributions are calibrated to published Indian tertiary-hospital averages.
They are adequate for demonstration and model training; they are not a clinical model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np

# --------------------------------------------------------------- calibration
# Relative arrival intensity by hour. Evening ED peak, small post-midnight tail.
HOURLY_ARRIVAL_PROFILE = np.array(
    [0.35, 0.28, 0.22, 0.20, 0.22, 0.30, 0.48, 0.72, 0.95, 1.10, 1.18, 1.15,
     1.05, 0.98, 0.95, 1.00, 1.12, 1.32, 1.48, 1.42, 1.18, 0.92, 0.68, 0.48]
)

# Monday is the heaviest day in most public hospitals.
WEEKDAY_MULTIPLIER = np.array([1.18, 1.06, 1.00, 0.98, 1.02, 0.92, 0.86])

# Seasonal disease mix by month (1-12). Monsoon dengue, winter respiratory.
SEASONAL_DISEASE_WEIGHTS: dict[int, dict[str, float]] = {
    1:  {"respiratory": 0.30, "cardiac": 0.18, "trauma": 0.14, "infectious": 0.12, "gi": 0.10, "neuro": 0.06, "obstetric": 0.05, "other": 0.05},
    2:  {"respiratory": 0.27, "cardiac": 0.18, "trauma": 0.15, "infectious": 0.12, "gi": 0.11, "neuro": 0.06, "obstetric": 0.06, "other": 0.05},
    3:  {"respiratory": 0.20, "cardiac": 0.17, "trauma": 0.18, "infectious": 0.14, "gi": 0.13, "neuro": 0.06, "obstetric": 0.06, "other": 0.06},
    4:  {"respiratory": 0.16, "cardiac": 0.17, "trauma": 0.20, "infectious": 0.15, "gi": 0.14, "neuro": 0.06, "obstetric": 0.06, "other": 0.06},
    5:  {"respiratory": 0.14, "cardiac": 0.18, "trauma": 0.21, "infectious": 0.16, "gi": 0.14, "neuro": 0.06, "obstetric": 0.05, "other": 0.06},
    6:  {"respiratory": 0.16, "cardiac": 0.16, "trauma": 0.17, "infectious": 0.22, "gi": 0.16, "neuro": 0.05, "obstetric": 0.05, "other": 0.03},
    7:  {"respiratory": 0.18, "cardiac": 0.15, "trauma": 0.14, "infectious": 0.28, "gi": 0.14, "neuro": 0.05, "obstetric": 0.03, "other": 0.03},
    8:  {"respiratory": 0.18, "cardiac": 0.15, "trauma": 0.14, "infectious": 0.30, "gi": 0.13, "neuro": 0.04, "obstetric": 0.03, "other": 0.03},
    9:  {"respiratory": 0.19, "cardiac": 0.16, "trauma": 0.15, "infectious": 0.26, "gi": 0.13, "neuro": 0.04, "obstetric": 0.04, "other": 0.03},
    10: {"respiratory": 0.22, "cardiac": 0.17, "trauma": 0.16, "infectious": 0.19, "gi": 0.12, "neuro": 0.05, "obstetric": 0.05, "other": 0.04},
    11: {"respiratory": 0.27, "cardiac": 0.18, "trauma": 0.15, "infectious": 0.14, "gi": 0.11, "neuro": 0.05, "obstetric": 0.05, "other": 0.05},
    12: {"respiratory": 0.31, "cardiac": 0.19, "trauma": 0.14, "infectious": 0.11, "gi": 0.10, "neuro": 0.05, "obstetric": 0.05, "other": 0.05},
}

COMPLAINTS_BY_CATEGORY: dict[str, list[str]] = {
    "respiratory": ["Breathlessness worsening over 2 days", "Persistent cough with fever",
                    "Wheeze and chest tightness", "Acute asthma exacerbation"],
    "cardiac": ["Central chest pain radiating to left arm", "Palpitations with dizziness",
                "Chest heaviness on exertion", "Sudden onset chest pain with sweating"],
    "trauma": ["Road traffic accident, multiple abrasions", "Fall from height, leg pain",
               "Deep laceration to forearm", "Suspected fracture of the wrist"],
    "infectious": ["High fever with chills for 3 days", "Fever with severe body ache",
                   "Fever with rash and joint pain", "Fever, headache and retro-orbital pain"],
    "gi": ["Severe abdominal pain and vomiting", "Loose stools with dehydration",
           "Upper abdominal pain after meals", "Persistent nausea and vomiting"],
    "neuro": ["Sudden weakness of the right side", "Seizure episode witnessed at home",
              "Severe headache of sudden onset", "Dizziness with unsteady gait"],
    "obstetric": ["Labour pains at term", "Reduced fetal movements",
                  "Bleeding per vaginum in third trimester", "Severe headache in pregnancy"],
    "other": ["Generalised weakness and fatigue", "Routine review with worsening symptoms",
              "Swelling of both legs", "Unexplained weight loss"],
}

COMORBIDITY_POOL = ["diabetes", "hypertension", "CKD", "COPD", "ischaemic heart disease",
                    "asthma", "hypothyroidism", "obesity"]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya", "Rohan",
               "Meera", "Arjun", "Saanvi", "Kabir", "Riya", "Neha", "Vikram", "Priya",
               "Rahul", "Sneha", "Karthik", "Divya", "Aniket", "Pooja", "Manish", "Lakshmi"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Reddy", "Nair", "Patel", "Singh", "Gupta",
              "Rao", "Menon", "Chowdhury", "Kulkarni", "Desai", "Bose", "Pillai", "Joshi"]


@dataclass
class SimulationConfig:
    """Tunable parameters for one hospital's simulation."""

    seed: int = 42
    base_arrivals_per_day: float = 180.0
    total_beds: int = 400
    icu_beds: int = 48
    staff_count: int = 260
    roof_area_sqm: float = 4200.0
    solar_kwp: float = 120.0
    scenario: str | None = None
    scenario_multipliers: dict[str, float] = field(default_factory=dict)


class HospitalSimulator:
    """Generates a coherent, seeded stream of hospital telemetry.

    Coherent matters: energy, water and waste are all derived from the same occupancy
    figure, so the carbon numbers the dashboards show actually reconcile.
    """

    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self.rng = np.random.default_rng(self.config.seed)

    # ------------------------------------------------------------- primitives
    def _outside_temperature(self, moment: datetime) -> float:
        """Bengaluru-like annual and diurnal temperature curve."""
        day_of_year = moment.timetuple().tm_yday
        seasonal = 24.5 + 4.0 * math.sin(2 * math.pi * (day_of_year - 100) / 365)
        diurnal = 5.5 * math.sin(2 * math.pi * (moment.hour - 9) / 24)
        return round(seasonal + diurnal + self.rng.normal(0, 0.8), 1)

    def _rainfall_mm(self, moment: datetime) -> float:
        """Monsoon-weighted daily rainfall."""
        month = moment.month
        monsoon = {6: 8.0, 7: 11.0, 8: 10.0, 9: 8.5, 10: 6.0}.get(month, 1.2)
        return round(max(0.0, self.rng.gamma(shape=1.4, scale=monsoon)), 1)

    def _scenario_factor(self, stream: str) -> float:
        return self.config.scenario_multipliers.get(stream, 1.0)

    # -------------------------------------------------------------- arrivals
    def arrivals_for_hour(self, moment: datetime) -> int:
        """Non-homogeneous Poisson arrival count for a single hour."""
        hourly_mean = self.config.base_arrivals_per_day / 24.0
        intensity = (
            hourly_mean
            * HOURLY_ARRIVAL_PROFILE[moment.hour]
            * WEEKDAY_MULTIPLIER[moment.weekday()]
            * self._scenario_factor("arrivals")
        )
        return int(self.rng.poisson(max(intensity, 0.01)))

    def disease_category(self, moment: datetime) -> str:
        weights = SEASONAL_DISEASE_WEIGHTS[moment.month]
        categories = list(weights)
        probabilities = np.array([weights[c] for c in categories], dtype=float)
        probabilities /= probabilities.sum()
        return str(self.rng.choice(categories, p=probabilities))

    def generate_patient(self, moment: datetime) -> dict:
        """A synthetic patient with age-correlated comorbidities."""
        age = int(np.clip(self.rng.normal(46, 21), 0, 96))
        comorbidity_count = int(self.rng.poisson(max(0.2, (age - 25) / 28)))
        comorbidities = (
            list(self.rng.choice(COMORBIDITY_POOL, size=min(comorbidity_count, 4), replace=False))
            if comorbidity_count > 0
            else []
        )
        return {
            "full_name": f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}",
            "age": age,
            "sex": str(self.rng.choice(["male", "female"], p=[0.52, 0.48])),
            "blood_group": str(
                self.rng.choice(
                    ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"],
                    p=[0.36, 0.22, 0.30, 0.06, 0.02, 0.015, 0.02, 0.005],
                )
            ),
            "comorbidities": comorbidities,
            "allergies": ["penicillin"] if self.rng.random() < 0.06 else [],
            "is_synthetic": True,
        }

    def generate_vitals(self, category: str, age: int) -> dict:
        """Vitals correlated with the presenting category, so triage has real signal."""
        heart_rate = self.rng.normal(84, 14)
        systolic = self.rng.normal(126, 18)
        diastolic = self.rng.normal(79, 11)
        spo2 = self.rng.normal(97.2, 1.8)
        temperature = self.rng.normal(36.9, 0.5)
        respiratory = self.rng.normal(17, 3.5)
        gcs = 15
        pain = int(np.clip(self.rng.normal(4, 2.4), 0, 10))

        if category == "respiratory":
            spo2 -= abs(self.rng.normal(4.5, 2.6))
            respiratory += abs(self.rng.normal(7, 4))
            heart_rate += abs(self.rng.normal(10, 6))
        elif category == "cardiac":
            heart_rate += self.rng.normal(16, 12)
            systolic -= abs(self.rng.normal(12, 14))
            pain = int(np.clip(self.rng.normal(7, 2), 0, 10))
        elif category == "trauma":
            systolic -= abs(self.rng.normal(10, 12))
            heart_rate += abs(self.rng.normal(14, 9))
            pain = int(np.clip(self.rng.normal(7.5, 2), 0, 10))
            if self.rng.random() < 0.10:
                gcs = int(self.rng.integers(6, 14))
        elif category == "infectious":
            temperature += abs(self.rng.normal(1.9, 0.7))
            heart_rate += abs(self.rng.normal(12, 7))
        elif category == "neuro":
            if self.rng.random() < 0.28:
                gcs = int(self.rng.integers(5, 14))
            systolic += self.rng.normal(14, 16)

        # Older patients decompensate further.
        if age > 68:
            spo2 -= abs(self.rng.normal(1.4, 1.0))
            systolic -= abs(self.rng.normal(4, 5))

        return {
            "heart_rate": int(np.clip(heart_rate, 35, 190)),
            "systolic_bp": int(np.clip(systolic, 62, 225)),
            "diastolic_bp": int(np.clip(diastolic, 38, 135)),
            "spo2": round(float(np.clip(spo2, 72, 100)), 1),
            "temperature_c": round(float(np.clip(temperature, 34.5, 41.5)), 1),
            "respiratory_rate": int(np.clip(respiratory, 8, 46)),
            "gcs": int(gcs),
            "pain_score": int(pain),
        }

    def generate_arrival(self, moment: datetime) -> dict:
        """A complete arrival payload: patient, complaint and vitals."""
        category = self.disease_category(moment)
        patient = self.generate_patient(moment)
        return {
            "patient": patient,
            "disease_category": category,
            "chief_complaint": str(self.rng.choice(COMPLAINTS_BY_CATEGORY[category])),
            "vitals": self.generate_vitals(category, patient["age"]),
            "source": str(
                self.rng.choice(
                    ["walk_in", "ambulance", "referral"], p=[0.62, 0.26, 0.12]
                )
            ),
        }

    # --------------------------------------------------------------- energy
    def energy_log(self, moment: datetime, occupancy_ratio: float, zone: str = "whole_site") -> dict:
        """Hourly electricity, decomposed so the agent has something to optimise."""
        outside_temp = self._outside_temperature(moment)
        base_load = 210.0 + 90.0 * occupancy_ratio

        cooling_demand = max(0.0, outside_temp - 24.0)
        hvac = (55.0 + 26.0 * cooling_demand) * (0.55 + 0.45 * occupancy_ratio)

        # Operating theatres run mornings on weekdays.
        ot_active = 8 <= moment.hour <= 16 and moment.weekday() < 5
        equipment = 95.0 * (0.6 + 0.4 * occupancy_ratio) + (58.0 if ot_active else 0.0)
        lighting = 40.0 * (0.45 if 7 <= moment.hour <= 18 else 0.95)

        total = (base_load + hvac + equipment + lighting) * self._scenario_factor("energy")
        total *= float(self.rng.normal(1.0, 0.045))
        total = max(total, 60.0)

        # Solar only during daylight, derated by cloud cover.
        solar_capacity = self.config.solar_kwp
        if 7 <= moment.hour <= 17:
            solar_curve = math.sin(math.pi * (moment.hour - 7) / 10)
            solar = solar_capacity * solar_curve * float(self.rng.uniform(0.55, 0.92))
        else:
            solar = 0.0
        solar = min(solar, total * 0.7)

        dg = total * 0.04 if self.rng.random() < 0.03 else 0.0
        grid = max(total - solar - dg, 0.0)

        return {
            "timestamp": moment,
            "zone": zone,
            "consumption_kwh": round(total, 2),
            "source_mix": {
                "grid_kwh": round(grid, 2),
                "solar_kwh": round(solar, 2),
                "dg_kwh": round(dg, 2),
            },
            "hvac_kwh": round(hvac, 2),
            "equipment_kwh": round(equipment, 2),
            "lighting_kwh": round(lighting, 2),
            "outside_temp_c": outside_temp,
            "setpoint_c": 23.0,
            "occupancy_ratio": round(occupancy_ratio, 3),
            "cost_paise": int(total * 780),
            "emission_kg": round(grid * 0.71 + dg * 0.85 + solar * 0.048, 2),
        }

    # ---------------------------------------------------------------- water
    def water_log(
        self, moment: datetime, occupancy_ratio: float, leak_active: bool = False
    ) -> dict:
        """Hourly water draw, with an optional injected leak."""
        per_bed_hourly = 18.5
        occupied = self.config.total_beds * occupancy_ratio
        base = occupied * per_bed_hourly

        # Laundry and kitchen cycles.
        if moment.hour in (6, 7, 11, 12, 18, 19):
            base *= 1.32

        leak_loss = 0.0
        if leak_active:
            leak_loss = float(self.rng.uniform(180, 620))

        total = (base + leak_loss) * float(self.rng.normal(1.0, 0.05))
        total *= self._scenario_factor("water")

        # Night minimum flow is the leak signal: it should approach zero when sound.
        is_night = moment.hour in (2, 3, 4)
        night_min = (
            (leak_loss / 60.0 + float(self.rng.uniform(0.4, 2.2)))
            if is_night
            else float(self.rng.uniform(3.0, 9.0))
        )

        rainfall = self._rainfall_mm(moment)
        harvested = min(
            rainfall * self.config.roof_area_sqm * 0.8 / 24.0,
            self.config.roof_area_sqm * 2.0,
        )

        recycled = total * 0.18
        borewell = total * 0.22
        municipal = max(total - harvested - recycled - borewell, 0.0)

        return {
            "timestamp": moment,
            "zone": "whole_site",
            "consumption_litres": round(total, 1),
            "night_min_flow_lpm": round(night_min, 2),
            "source": {
                "municipal_l": round(municipal, 1),
                "borewell_l": round(borewell, 1),
                "rainwater_l": round(harvested, 1),
                "recycled_l": round(recycled, 1),
            },
            "leak_probability": 0.0,
            "leak_estimated_loss_lpd": round(leak_loss * 24, 1) if leak_active else 0.0,
            "occupancy_ratio": round(occupancy_ratio, 3),
            "emission_kg": round(total / 1000 * 0.34, 3),
        }

    # ---------------------------------------------------------------- waste
    def waste_records(self, day: date, occupancy_ratio: float) -> list[dict]:
        """Daily biomedical waste by CPCB colour category."""
        occupied_beds = self.config.total_beds * occupancy_ratio

        # kg per bed-day, and the disposal route each category takes.
        profile = {
            "yellow": (0.252, "incineration", 1.10),
            "red": (0.181, "autoclave", 0.28),
            "white": (0.038, "autoclave", 0.28),
            "blue": (0.029, "recycling", -0.42),
            "general": (0.856, "landfill", 0.58),
        }

        records: list[dict] = []
        for category, (rate, method, factor) in profile.items():
            weight = occupied_beds * rate * float(self.rng.normal(1.0, 0.11))
            weight = max(weight, 0.1) * self._scenario_factor("waste")

            # Segregation quality drifts; occasional genuinely poor days.
            segregation = float(np.clip(self.rng.normal(0.91, 0.07), 0.45, 1.0))

            records.append(
                {
                    "date": day,
                    "category": category,
                    "weight_kg": round(weight, 2),
                    "segregation_score": round(segregation, 3),
                    "disposal_method": method,
                    "treatment_facility": "CBWTF-Bengaluru-03",
                    "pickup": {
                        "scheduled_at": None,
                        "collected_at": None,
                        "status": "pending",
                        "vendor": "Maridi Eco Industries",
                    },
                    "emission_kg": round(weight * factor, 3),
                    "recyclable_recovered_kg": round(weight * 0.62, 2)
                    if category == "blue"
                    else 0.0,
                    "anomaly_flag": segregation < 0.65,
                }
            )
        return records

    # ------------------------------------------------------------- occupancy
    def occupancy_ratio(self, moment: datetime) -> float:
        """Smooth occupancy curve with weekly seasonality, clamped to a plausible band."""
        day_of_year = moment.timetuple().tm_yday
        seasonal = 0.78 + 0.09 * math.sin(2 * math.pi * (day_of_year - 200) / 365)
        weekly = 0.03 * math.sin(2 * math.pi * moment.weekday() / 7)
        noise = float(self.rng.normal(0, 0.025))
        ratio = seasonal + weekly + noise
        ratio *= self._scenario_factor("occupancy")
        return float(np.clip(ratio, 0.42, 0.99))


def apply_scenario(config: SimulationConfig, scenario: str) -> SimulationConfig:
    """Return a config with the named stress scenario applied."""
    multipliers = {
        "mass_casualty": {"arrivals": 3.4, "waste": 1.6, "occupancy": 1.12},
        "outbreak_surge": {"arrivals": 2.1, "waste": 1.45, "occupancy": 1.15, "water": 1.2},
        "power_failure": {"energy": 0.35},
        "water_main_break": {"water": 2.8},
        "supply_disruption": {},
    }
    if scenario not in multipliers:
        raise ValueError(
            f"Unknown scenario '{scenario}'. Choose from: {', '.join(multipliers)}"
        )

    config.scenario = scenario
    config.scenario_multipliers = multipliers[scenario]
    return config


def utc(moment: datetime) -> datetime:
    """Ensure a datetime carries UTC, as Mongo stores naive datetimes as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def hours_between(start: datetime, end: datetime) -> list[datetime]:
    """Inclusive hourly range, used when backfilling history."""
    current = utc(start)
    stop = utc(end)
    output: list[datetime] = []
    while current <= stop:
        output.append(current)
        current += timedelta(hours=1)
    return output
