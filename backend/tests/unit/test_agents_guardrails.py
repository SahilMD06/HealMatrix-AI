"""Guardrail tests: the hard safety constraints from docs/04_agent_design.md
section 4 that neither a trained model nor an LLM may ever override.

- Red-flag vitals always yield ESI 1 (Patient Triage Agent), whether the trained
  model is available or not.
- OT/ICU HVAC setpoints never leave 20-24 C (Energy Optimization Agent), and an
  unsafe candidate is discarded rather than clamped into range.
- Maintenance beds are never assigned (BedService, used by both humans and the
  Bed Allocation Agent).
- Cold-chain medicine transfers require every link in the chain to be capable;
  one missing link excludes the SKU entirely (Medicine Intelligence Agent).
- Waste classification never guesses without grounding evidence above the
  relevance threshold (Biomedical Waste Agent).
"""

from __future__ import annotations

import pytest

from app.agents.energy_agent import EnergyOptimizationAgent
from app.agents.medicine_agent import MedicineIntelligenceAgent
from app.agents.triage_agent import PatientTriageAgent
from app.agents.waste_agent import BiomedicalWasteAgent
from app.core.constants import HVAC_SETPOINT_LIMITS
from app.database.repositories import BedRepository
from app.services.bed_service import BedService

pytestmark = pytest.mark.unit

RED_FLAG_VITALS = {
    "heart_rate": 132, "systolic_bp": 78, "diastolic_bp": 44, "spo2": 86.0,
    "temperature_c": 36.1, "respiratory_rate": 34, "gcs": 11, "pain_score": 6,
}


def red_flag_state() -> dict:
    return {
        "vitals": RED_FLAG_VITALS,
        "age": 71,
        "comorbidities": [],
        "chief_complaint": "Collapsed at home, unresponsive",
        "patient": {"sex": "female"},
    }


class TestTriageRedFlagGuardrail:
    """The guardrail is unconditional per docs/04_agent_design.md 2.1: 'cannot be
    overridden by the model or the LLM.' Both code paths are exercised here."""

    async def test_red_flags_force_esi_one_via_the_trained_model_path(self):
        """With the real XGBoost artifact present (see app/ml/artifacts/), analyse()
        runs the model and the guardrail overrides its prediction unconditionally."""
        agent = PatientTriageAgent()
        result = await agent.run(red_flag_state())
        assert result.output["esi_level"] == 1
        assert result.confidence >= 0.95
        assert result.used_fallback is False, "the override happens inside analyse(), not via fallback"

    async def test_red_flags_force_esi_one_via_the_rule_engine_fallback_path(self, monkeypatch):
        """With the model unavailable, BaseAgent.run() drops to the pure rule engine,
        which enforces the identical guardrail independently."""
        monkeypatch.setattr("app.ml.inference.triage_model_available", lambda: False)
        agent = PatientTriageAgent()
        result = await agent.run(red_flag_state())
        assert result.output["esi_level"] == 1
        assert result.used_fallback is True

    async def test_no_red_flags_lets_the_model_decide(self):
        healthy_state = {
            "vitals": {
                "heart_rate": 76, "systolic_bp": 122, "diastolic_bp": 78, "spo2": 99.0,
                "temperature_c": 36.7, "respiratory_rate": 15, "gcs": 15, "pain_score": 0,
            },
            "age": 30, "comorbidities": [], "chief_complaint": "Routine review",
            "patient": {"sex": "male"},
        }
        agent = PatientTriageAgent()
        result = await agent.run(healthy_state)
        assert result.output["esi_level"] != 1
        assert result.output["red_flags"] == []


class TestHvacGuardrail:
    """docs/04_agent_design.md 2.5: 'recommendations outside HVAC_SETPOINT_LIMITS
    are discarded, not merely warned about.'"""

    @pytest.mark.parametrize("outside_temp", [-10.0, 0.0, 15.0, 22.0, 24.0, 24.1, 30.0, 45.0])
    def test_recommended_setpoints_never_leave_clinical_limits(self, outside_temp):
        recommendations, _discarded = EnergyOptimizationAgent._hvac_recommendations({}, outside_temp)
        for rec in recommendations:
            low, high = HVAC_SETPOINT_LIMITS[rec["zone"]]
            assert low <= rec["recommended_setpoint_c"] <= high

    def test_ot_and_icu_are_hard_clamped_to_20_24(self):
        for outside_temp in (-20.0, 50.0):
            recommendations, _ = EnergyOptimizationAgent._hvac_recommendations({}, outside_temp)
            for rec in recommendations:
                if rec["zone"] in ("ot", "icu"):
                    assert 20.0 <= rec["recommended_setpoint_c"] <= 24.0

    def test_an_unsafe_candidate_is_discarded_not_clamped(self, monkeypatch):
        """Forces the discard branch directly: an inverted (invalid) limits tuple
        can never produce a 'safe' candidate, and the agent must refuse to propose
        anything for that zone rather than clamp to the nearest bound."""
        monkeypatch.setattr(
            "app.agents.energy_agent.HVAC_SETPOINT_LIMITS", {"broken_zone": (26.0, 20.0)}
        )
        recommendations, discarded = EnergyOptimizationAgent._hvac_recommendations({}, 30.0)
        assert discarded == 1
        assert recommendations == []


class TestMaintenanceBedGuardrail:
    """docs/04_agent_design.md 2.3: BedAllocationAgent 'never selects maintenance
    or already-reserved beds' — enforced in BedService, used by agents and humans
    alike, so this is checked at that shared layer directly."""

    @pytest.mark.integration
    @pytest.mark.parametrize("esi_level", [1, 2, 3, 4, 5])
    async def test_maintenance_bed_is_never_recommended(self, seeded, esi_level):
        beds = BedRepository(seeded["hospital_id"])
        service = BedService(beds)

        recommendation = await service.recommend(esi_level=esi_level)
        assert recommendation["bed"]["bed_number"] != "MAINT-999"
        assert all(alt["bed_number"] != "MAINT-999" for alt in recommendation["alternatives"])


class TestColdChainGuardrail:
    """docs/04_agent_design.md 2.4: 'cold-chain SKUs are excluded unless both sites
    and the route are cold-chain capable' — any single missing link blocks the SKU."""

    BASE_DONOR = {
        "sku": "COLD-001", "medicine_name": "Insulin", "hospital_id": "hosp-a",
        "days_to_expiry": 10, "surplus_units": 50, "unit_cost_paise": 5000,
        "carbon_kg_per_unit": 0.02, "is_cold_chain": True,
    }
    BASE_RECIPIENT = {
        "sku": "COLD-001", "medicine_name": "Insulin", "hospital_id": "hosp-b",
        "deficit_units": 30,
    }

    def test_missing_donor_capability_blocks_the_transfer(self):
        donor = {**self.BASE_DONOR, "hospital_cold_chain_capable": False, "route_cold_chain_capable": True}
        recipient = {**self.BASE_RECIPIENT, "hospital_cold_chain_capable": True}
        proposals = MedicineIntelligenceAgent._transfer_proposals([donor, recipient])
        assert proposals == []

    def test_missing_route_capability_blocks_the_transfer(self):
        donor = {**self.BASE_DONOR, "hospital_cold_chain_capable": True, "route_cold_chain_capable": False}
        recipient = {**self.BASE_RECIPIENT, "hospital_cold_chain_capable": True}
        proposals = MedicineIntelligenceAgent._transfer_proposals([donor, recipient])
        assert proposals == []

    def test_missing_recipient_capability_blocks_the_transfer(self):
        donor = {**self.BASE_DONOR, "hospital_cold_chain_capable": True, "route_cold_chain_capable": True}
        recipient = {**self.BASE_RECIPIENT, "hospital_cold_chain_capable": False}
        proposals = MedicineIntelligenceAgent._transfer_proposals([donor, recipient])
        assert proposals == []

    def test_every_link_present_allows_the_transfer(self):
        donor = {**self.BASE_DONOR, "hospital_cold_chain_capable": True, "route_cold_chain_capable": True}
        recipient = {**self.BASE_RECIPIENT, "hospital_cold_chain_capable": True}
        proposals = MedicineIntelligenceAgent._transfer_proposals([donor, recipient])
        assert len(proposals) == 1
        assert proposals[0]["units"] == 30

    def test_non_cold_chain_sku_is_unaffected_by_the_guardrail(self):
        donor = {**self.BASE_DONOR, "is_cold_chain": False}
        recipient = self.BASE_RECIPIENT
        proposals = MedicineIntelligenceAgent._transfer_proposals([donor, recipient])
        assert len(proposals) == 1


class TestWasteGroundingGuardrail:
    """docs/04_agent_design.md 2.7: an unsupported classification is reported as
    'requires manual review', never guessed."""

    async def test_no_supporting_evidence_yields_manual_review(self, monkeypatch):
        async def _no_chunks(*args, **kwargs):
            return []

        monkeypatch.setattr("app.agents.waste_agent.retrieve", _no_chunks)
        agent = BiomedicalWasteAgent()
        state = {"waste_description": "strange unknown item of unclear origin", "waste_history": []}
        result = await agent.run(state)
        assert result.output["classification"] == "requires_manual_review"
        assert result.confidence == 0.0
        assert result.output["citations"] == []

    async def test_grounded_description_is_classified_with_citations(self, monkeypatch):
        async def _chunks(*args, **kwargs):
            return [
                {
                    "content": "Used needles and scalpel blades are white category sharps.",
                    "relevance_score": 0.9,
                    "source_document": "cpcb_biomedical_waste_rules_2016.md",
                    "section": "2.3",
                    "chunk_id": "chunk-1",
                }
            ]

        monkeypatch.setattr("app.agents.waste_agent.retrieve", _chunks)
        agent = BiomedicalWasteAgent()
        state = {"waste_description": "Used needle from ward 3", "waste_history": []}
        result = await agent.run(state)
        assert result.output["classification"] == "white"
        assert len(result.output["citations"]) == 1
