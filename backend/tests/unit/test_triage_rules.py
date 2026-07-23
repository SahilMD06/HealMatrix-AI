"""Unit tests for the deterministic triage engine.

These run with no database, no network and no API key — which is precisely the point:
the fallback path must work when everything else is unavailable.
"""

from __future__ import annotations

import pytest

from app.models.clinical import Vitals
from app.services.triage_rules import (
    detect_red_flags,
    score_severity,
    score_to_esi,
    suggest_department,
    triage,
)

pytestmark = pytest.mark.unit


def vitals(**overrides) -> Vitals:
    """A healthy adult, overridden field by field."""
    baseline = {
        "heart_rate": 76, "systolic_bp": 122, "diastolic_bp": 78, "spo2": 99.0,
        "temperature_c": 36.7, "respiratory_rate": 15, "gcs": 15, "pain_score": 0,
    }
    return Vitals(**{**baseline, **overrides})


class TestRedFlags:
    def test_healthy_patient_has_no_red_flags(self):
        assert detect_red_flags(vitals()) == []

    def test_hypoxaemia_with_tachypnoea(self):
        assert "spo2_critical" in detect_red_flags(vitals(spo2=86.0, respiratory_rate=34))

    def test_low_spo2_alone_is_not_a_red_flag(self):
        """SpO2 alone is concerning but not a resuscitation trigger without tachypnoea."""
        assert "spo2_critical" not in detect_red_flags(vitals(spo2=86.0, respiratory_rate=16))

    def test_depressed_consciousness(self):
        assert "gcs_depressed" in detect_red_flags(vitals(gcs=7))

    def test_shock_requires_both_hypotension_and_tachycardia(self):
        assert "shock" in detect_red_flags(vitals(systolic_bp=82, heart_rate=134))
        assert "shock" not in detect_red_flags(vitals(systolic_bp=82, heart_rate=80))

    def test_severe_bradycardia(self):
        assert "bradycardia_severe" in detect_red_flags(vitals(heart_rate=36))

    def test_hypertensive_crisis(self):
        assert "hypertensive_crisis" in detect_red_flags(vitals(systolic_bp=210))

    def test_hypothermia(self):
        assert "hypothermia" in detect_red_flags(vitals(temperature_c=34.2))


class TestGuardrail:
    def test_red_flags_always_force_esi_one(self):
        """The guardrail must override the score, however benign the score is."""
        assert score_to_esi(0.0, ["shock"]) == 1
        assert score_to_esi(99.0, []) == 2

    def test_red_flag_case_end_to_end(self):
        result = triage(
            vitals(spo2=86.0, respiratory_rate=34, systolic_bp=78, heart_rate=132, gcs=11),
            "Collapsed at home",
            age=71,
        )
        assert result["esi_level"] == 1
        assert result["confidence"] >= 0.95
        assert len(result["red_flags"]) >= 2
        assert result["target_response_minutes"] == 0
        assert result["recommended_department_code"] == "ED"


class TestSeverityScoring:
    def test_healthy_young_adult_scores_near_zero(self):
        assert score_severity(vitals(), age=24, comorbidity_count=0) < 1.0

    def test_spo2_of_92_is_scored_as_hypoxaemic(self):
        """Regression: 92% previously fell into the mildest band and under-triaged."""
        hypoxaemic = score_severity(vitals(spo2=92.0), age=40, comorbidity_count=0)
        normal = score_severity(vitals(spo2=99.0), age=40, comorbidity_count=0)
        assert hypoxaemic - normal >= 2.0

    def test_score_increases_with_age(self):
        young = score_severity(vitals(), age=30, comorbidity_count=0)
        elderly = score_severity(vitals(), age=80, comorbidity_count=0)
        assert elderly > young

    def test_score_increases_with_comorbidity_burden(self):
        none = score_severity(vitals(), age=50, comorbidity_count=0)
        several = score_severity(vitals(), age=50, comorbidity_count=3)
        assert several > none

    def test_comorbidity_contribution_is_capped(self):
        four = score_severity(vitals(), age=50, comorbidity_count=4)
        twenty = score_severity(vitals(), age=50, comorbidity_count=20)
        assert four == twenty


class TestEsiBanding:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [(0.0, 5), (1.9, 5), (2.0, 4), (4.4, 4), (4.5, 3), (7.4, 3), (7.5, 2), (20.0, 2)],
    )
    def test_band_boundaries(self, score, expected):
        assert score_to_esi(score, []) == expected

    def test_cardiac_case_is_emergent_not_urgent(self):
        """Regression: this presentation was under-triaged to ESI 3."""
        result = triage(
            vitals(heart_rate=118, systolic_bp=96, diastolic_bp=62, spo2=92.0,
                   respiratory_rate=26, pain_score=8),
            "Central chest pain radiating to left arm",
            age=63,
            comorbidities=["diabetes", "hypertension"],
        )
        assert result["esi_level"] == 2
        assert result["target_response_minutes"] == 10

    def test_minor_injury_is_low_acuity(self):
        result = triage(vitals(pain_score=3), "Deep laceration to forearm", age=24)
        assert result["esi_level"] in (4, 5)


class TestDepartmentRouting:
    @pytest.mark.parametrize(
        ("complaint", "expected"),
        [
            ("Central chest pain radiating to left arm", "CARDIO"),
            ("Breathlessness worsening over 2 days", "PULMO"),
            ("Suspected fracture of the wrist", "ORTHO"),
            ("Sudden weakness of the right side", "NEURO"),
            ("Severe abdominal pain and vomiting", "GEN-MED"),
            ("Labour pains at term", "OBG"),
        ],
    )
    def test_complaint_maps_to_department(self, complaint, expected):
        assert suggest_department(complaint, esi_level=3) == expected

    def test_resuscitation_always_goes_to_emergency(self):
        assert suggest_department("Central chest pain radiating to left arm", esi_level=1) == "ED"

    def test_unrecognised_complaint_falls_back_safely(self):
        assert suggest_department("Feeling generally unwell", esi_level=2) == "ED"
        assert suggest_department("Feeling generally unwell", esi_level=4) == "GEN-MED"


class TestOutputContract:
    def test_result_carries_every_required_field(self):
        result = triage(vitals(), "Routine review", age=40)
        for field in (
            "esi_level", "confidence", "recommended_department_code",
            "target_response_minutes", "red_flags", "rationale",
            "acuity_score", "model_version", "used_fallback",
        ):
            assert field in result, f"missing {field}"

    def test_rationale_is_substantive(self):
        result = triage(vitals(spo2=91.0, respiratory_rate=28), "Breathless", age=68)
        assert len(result["rationale"]) > 60
        assert "ESI" in result["rationale"]

    def test_confidence_is_a_probability(self):
        for age in (1, 35, 90):
            result = triage(vitals(), "Routine review", age=age)
            assert 0.0 <= result["confidence"] <= 1.0

    def test_is_deterministic(self):
        """Same input, same output — required for reproducible evaluation."""
        first = triage(vitals(spo2=93.0), "Chest pain", age=55, comorbidities=["diabetes"])
        second = triage(vitals(spo2=93.0), "Chest pain", age=55, comorbidities=["diabetes"])
        assert first == second
