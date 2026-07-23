"""Energy, water, waste and carbon documents."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field, computed_field

from app.core.constants import DisposalMethod, WasteCategory
from app.models.base import (
    DateRange,
    HealMatrixModel,
    ObjectIdField,
    TenantDocumentModel,
)


# -------------------------------------------------------------------- energy
class EnergySourceMix(HealMatrixModel):
    grid_kwh: float = Field(default=0.0, ge=0)
    solar_kwh: float = Field(default=0.0, ge=0)
    dg_kwh: float = Field(default=0.0, ge=0, description="diesel generator")

    @computed_field
    @property
    def renewable_share(self) -> float:
        total = self.grid_kwh + self.solar_kwh + self.dg_kwh
        return round(self.solar_kwh / total, 4) if total else 0.0


class EnergyLog(TenantDocumentModel):
    timestamp: datetime
    zone: str
    consumption_kwh: float = Field(ge=0)
    source_mix: EnergySourceMix = Field(default_factory=EnergySourceMix)
    hvac_kwh: float = Field(default=0.0, ge=0)
    equipment_kwh: float = Field(default=0.0, ge=0)
    lighting_kwh: float = Field(default=0.0, ge=0)
    outside_temp_c: float | None = None
    setpoint_c: float | None = None
    occupancy_ratio: float = Field(default=0.0, ge=0, le=1)
    cost_paise: int = Field(default=0, ge=0)
    emission_kg: float = Field(default=0.0, ge=0)


# --------------------------------------------------------------------- water
class WaterSourceMix(HealMatrixModel):
    municipal_l: float = Field(default=0.0, ge=0)
    borewell_l: float = Field(default=0.0, ge=0)
    rainwater_l: float = Field(default=0.0, ge=0)
    recycled_l: float = Field(default=0.0, ge=0)


class WaterLog(TenantDocumentModel):
    timestamp: datetime
    zone: str
    consumption_litres: float = Field(ge=0)
    night_min_flow_lpm: float = Field(
        default=0.0, ge=0, description="Minimum night flow, the primary leak indicator"
    )
    source: WaterSourceMix = Field(default_factory=WaterSourceMix)
    leak_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    leak_estimated_loss_lpd: float = Field(default=0.0, ge=0)
    occupancy_ratio: float = Field(default=0.0, ge=0, le=1)
    emission_kg: float = Field(default=0.0, ge=0)


# --------------------------------------------------------------------- waste
class PickupInfo(HealMatrixModel):
    scheduled_at: datetime | None = None
    collected_at: datetime | None = None
    status: str = "pending"
    vendor: str | None = None


class WasteRecord(TenantDocumentModel):
    department_id: ObjectIdField
    date: date
    category: WasteCategory
    weight_kg: float = Field(ge=0)
    segregation_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="1.0 means fully compliant segregation"
    )
    disposal_method: DisposalMethod = DisposalMethod.INCINERATION
    treatment_facility: str | None = None
    pickup: PickupInfo = Field(default_factory=PickupInfo)
    emission_kg: float = Field(default=0.0)
    recyclable_recovered_kg: float = Field(default=0.0, ge=0)
    anomaly_flag: bool = False


# -------------------------------------------------------------------- carbon
class Scope1Emissions(HealMatrixModel):
    diesel_generator: float = 0.0
    ambulance_fuel: float = 0.0
    anaesthetic_gases: float = 0.0
    total: float = 0.0


class Scope2Emissions(HealMatrixModel):
    grid_electricity: float = 0.0
    total: float = 0.0


class Scope3Emissions(HealMatrixModel):
    waste_treatment: float = 0.0
    water: float = 0.0
    procurement: float = 0.0
    staff_commute: float = 0.0
    total: float = 0.0


class SustainabilityScore(HealMatrixModel):
    """Composite 0-100 score with its four weighted sub-scores."""

    energy: float = Field(ge=0, le=100)
    water: float = Field(ge=0, le=100)
    waste: float = Field(ge=0, le=100)
    carbon: float = Field(ge=0, le=100)
    overall: float = Field(ge=0, le=100)

    @computed_field
    @property
    def grade(self) -> str:
        thresholds = ((85, "A+"), (75, "A"), (65, "B"), (55, "C"), (45, "D"))
        for cutoff, label in thresholds:
            if self.overall >= cutoff:
                return label
        return "E"


class ReductionOpportunity(HealMatrixModel):
    lever: str
    description: str
    tco2e_abated: float = Field(ge=0)
    cost_paise: int = Field(ge=0)
    payback_months: float | None = None
    priority: int = Field(default=3, ge=1, le=5)


class CarbonReport(TenantDocumentModel):
    period: DateRange
    scope1_kg: Scope1Emissions = Field(default_factory=Scope1Emissions)
    scope2_kg: Scope2Emissions = Field(default_factory=Scope2Emissions)
    scope3_kg: Scope3Emissions = Field(default_factory=Scope3Emissions)
    total_kg: float = Field(default=0.0, ge=0)
    per_bed_day_kg: float = Field(default=0.0, ge=0)
    sustainability_score: SustainabilityScore
    reduction_opportunities: list[ReductionOpportunity] = Field(default_factory=list)
    emission_factor_version: str
    generated_by_agent_run_id: str | None = None
