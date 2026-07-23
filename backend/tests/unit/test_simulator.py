"""Unit tests for the simulation engine.

Reproducibility is the property that matters most here: the report claims the
training data can be regenerated from a seed, and these tests hold that claim honest.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.simulator.generators import (
    HospitalSimulator,
    SimulationConfig,
    apply_scenario,
)

pytestmark = pytest.mark.unit

MOMENT = datetime(2026, 7, 21, 19, 0, tzinfo=timezone.utc)


def simulator(seed: int = 42) -> HospitalSimulator:
    return HospitalSimulator(SimulationConfig(seed=seed, total_beds=400, icu_beds=48))


class TestReproducibility:
    def test_same_seed_produces_identical_arrivals(self):
        assert simulator(7).generate_arrival(MOMENT) == simulator(7).generate_arrival(MOMENT)

    def test_different_seeds_diverge(self):
        assert simulator(1).generate_arrival(MOMENT) != simulator(2).generate_arrival(MOMENT)

    def test_energy_series_is_reproducible(self):
        first = [simulator(11).energy_log(MOMENT, 0.8) for _ in range(1)]
        second = [simulator(11).energy_log(MOMENT, 0.8) for _ in range(1)]
        assert first == second


class TestArrivalPatterns:
    def test_evening_is_busier_than_pre_dawn(self):
        """The generator must reproduce the well-known evening ED peak."""
        evening = datetime(2026, 7, 21, 19, 0, tzinfo=timezone.utc)
        pre_dawn = datetime(2026, 7, 21, 4, 0, tzinfo=timezone.utc)

        sim = simulator()
        evening_total = sum(sim.arrivals_for_hour(evening) for _ in range(200))
        pre_dawn_total = sum(sim.arrivals_for_hour(pre_dawn) for _ in range(200))
        assert evening_total > pre_dawn_total

    def test_arrival_payload_is_complete(self):
        arrival = simulator().generate_arrival(MOMENT)
        assert set(arrival) == {"patient", "disease_category", "chief_complaint", "vitals", "source"}
        assert arrival["patient"]["is_synthetic"] is True

    def test_monsoon_shifts_the_disease_mix(self):
        """Infectious disease should dominate more in August than in January."""
        sim = simulator()
        august = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
        january = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

        august_infectious = sum(sim.disease_category(august) == "infectious" for _ in range(500))
        january_infectious = sum(sim.disease_category(january) == "infectious" for _ in range(500))
        assert august_infectious > january_infectious


class TestVitalsGeneration:
    def test_vitals_stay_within_model_bounds(self):
        """Generated vitals must always satisfy the Pydantic ranges."""
        from app.models.clinical import Vitals

        sim = simulator()
        for _ in range(300):
            arrival = sim.generate_arrival(MOMENT)
            Vitals(**arrival["vitals"])  # raises if out of range

    def test_respiratory_cases_are_more_hypoxaemic(self):
        sim = simulator()
        respiratory = [sim.generate_vitals("respiratory", 50)["spo2"] for _ in range(200)]
        other = [sim.generate_vitals("other", 50)["spo2"] for _ in range(200)]
        assert sum(respiratory) / len(respiratory) < sum(other) / len(other)

    def test_elderly_patients_decompensate_further(self):
        sim = simulator()
        young = [sim.generate_vitals("cardiac", 30)["spo2"] for _ in range(200)]
        elderly = [sim.generate_vitals("cardiac", 80)["spo2"] for _ in range(200)]
        assert sum(elderly) / len(elderly) < sum(young) / len(young)


class TestSustainabilityStreams:
    def test_energy_decomposition_is_coherent(self):
        log = simulator().energy_log(MOMENT, occupancy_ratio=0.85)
        mix = log["source_mix"]
        total_mix = mix["grid_kwh"] + mix["solar_kwh"] + mix["dg_kwh"]
        assert abs(total_mix - log["consumption_kwh"]) < 0.5
        assert log["emission_kg"] > 0

    def test_solar_only_generates_in_daylight(self):
        sim = simulator()
        night = datetime(2026, 7, 21, 23, 0, tzinfo=timezone.utc)
        noon = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
        assert sim.energy_log(night, 0.8)["source_mix"]["solar_kwh"] == 0.0
        assert sim.energy_log(noon, 0.8)["source_mix"]["solar_kwh"] > 0.0

    def test_higher_occupancy_raises_consumption(self):
        sim = simulator()
        low = sim.energy_log(MOMENT, 0.4)["consumption_kwh"]
        high = sim.energy_log(MOMENT, 0.95)["consumption_kwh"]
        assert high > low

    def test_leak_raises_night_minimum_flow(self):
        """Night minimum flow is the leak signal the water agent depends on."""
        sim = simulator()
        night = datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc)
        sound = sim.water_log(night, 0.8, leak_active=False)["night_min_flow_lpm"]
        leaking = sim.water_log(night, 0.8, leak_active=True)["night_min_flow_lpm"]
        assert leaking > sound

    def test_waste_covers_every_cpcb_category(self):
        records = simulator().waste_records(MOMENT.date(), occupancy_ratio=0.8)
        assert {r["category"] for r in records} == {"yellow", "red", "white", "blue", "general"}
        assert all(r["weight_kg"] > 0 for r in records)

    def test_recycling_is_credited_as_avoided_emissions(self):
        records = {r["category"]: r for r in simulator().waste_records(MOMENT.date(), 0.8)}
        assert records["blue"]["emission_kg"] < 0
        assert records["yellow"]["emission_kg"] > 0

    def test_occupancy_stays_within_plausible_bounds(self):
        """Sampled across a full year, occupancy must never leave the clamped band."""
        sim = simulator()
        start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        for day in range(0, 365, 7):
            assert 0.42 <= sim.occupancy_ratio(start + timedelta(days=day)) <= 0.99


class TestScenarios:
    def test_mass_casualty_multiplies_arrivals(self):
        baseline = simulator()
        surge = HospitalSimulator(apply_scenario(SimulationConfig(seed=42), "mass_casualty"))

        moment = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)
        normal = sum(baseline.arrivals_for_hour(moment) for _ in range(120))
        elevated = sum(surge.arrivals_for_hour(moment) for _ in range(120))
        assert elevated > normal * 2

    def test_power_failure_cuts_consumption(self):
        baseline = simulator().energy_log(MOMENT, 0.8)["consumption_kwh"]
        failed = HospitalSimulator(
            apply_scenario(SimulationConfig(seed=42), "power_failure")
        ).energy_log(MOMENT, 0.8)["consumption_kwh"]
        assert failed < baseline

    def test_unknown_scenario_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown scenario"):
            apply_scenario(SimulationConfig(), "alien_invasion")
