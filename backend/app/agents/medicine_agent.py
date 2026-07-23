"""Medicine Intelligence Agent.

Per docs/04_agent_design.md 2.4: per-SKU demand forecast -> expiry-risk scoring ->
reorder-point recomputation -> network transfer optimisation.

Expiry and low-stock detection run against this hospital's own inventory via
``InventoryService`` (tenant-scoped, like every other repository access in this
codebase). Network transfer matching is different in kind: it needs a
cross-hospital view, which the tenant-scoped repository layer deliberately makes
impossible to query by accident (see ``TenantRepository``'s docstring — that
scoping is a structural guarantee, not something an agent should be routing
around). So transfer proposals are computed from ``state["network_inventory_snapshot"]``,
a cross-hospital snapshot the graph orchestrator assembles at the network level
before invoking this agent. With no snapshot supplied — the normal case for a
single-hospital run, or before that network-level query exists — this agent still
produces real expiry/low-stock/demand-forecast output and simply proposes zero
transfers, which is the honest answer, not a stub.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.state import HealMatrixState
from app.core.constants import EXPIRY_ALERT_DAYS, AgentName
from app.services.inventory_service import InventoryService

# A SKU counts as a genuine cold-chain transfer risk only if either endpoint or the
# route itself cannot maintain cold chain — any one failure is enough to block it.
NEAR_EXPIRY_DONOR_DAYS = 30


class MedicineIntelligenceAgent(BaseAgent):
    name = str(AgentName.MEDICINE)
    version = "1.0.0"

    def __init__(self, inventory_service: InventoryService) -> None:
        self.inventory_service = inventory_service

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        expiry_alerts = await self.inventory_service.expiry_alerts(within_days=EXPIRY_ALERT_DAYS[0])
        low_stock_alerts = await self.inventory_service.low_stock_alerts()

        case_mix_growth = self._case_mix_growth_factor(state)
        demand_forecast = self._demand_forecast(low_stock_alerts, case_mix_growth)

        transfer_proposals = self._transfer_proposals(state.get("network_inventory_snapshot"))

        critical_stockouts = [row for row in low_stock_alerts if row.get("is_critical")]
        stockout_risk = "high" if critical_stockouts else ("moderate" if low_stock_alerts else "low")

        avoided_waste_kg = sum(proposal["co2e_avoided_kg"] for proposal in transfer_proposals)

        rationale = (
            f"{len(expiry_alerts)} batch(es) expiring within {EXPIRY_ALERT_DAYS[0]} days, "
            f"{len(low_stock_alerts)} SKU(s) at or below reorder point"
            + (f" ({len(critical_stockouts)} of which are patient-safety-critical)" if critical_stockouts else "")
            + f". Demand forecast applies a {round((case_mix_growth - 1) * 100)}% case-mix growth adjustment "
            f"from the Disease Forecast Agent. "
            + (
                f"{len(transfer_proposals)} network transfer(s) proposed, avoiding an estimated "
                f"{round(avoided_waste_kg, 2)} kgCO2e of waste."
                if transfer_proposals
                else "No network transfer proposals this cycle (no cross-hospital snapshot supplied, "
                "or no viable donor/recipient pairs)."
            )
        )

        messages = [
            emit(
                self.name,
                "stockout_risk",
                {"level": stockout_risk, "critical_skus": [row["sku"] for row in critical_stockouts]},
                to_agent=str(AgentName.EXECUTIVE),
            )
        ]
        if avoided_waste_kg > 0:
            messages.append(
                emit(
                    self.name,
                    "avoided_waste_kg",
                    {"avoided_waste_kg": round(avoided_waste_kg, 2)},
                    to_agent=str(AgentName.CARBON),
                )
            )

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "expiry_alerts": expiry_alerts,
                "low_stock_alerts": low_stock_alerts,
                "demand_forecast": demand_forecast,
                "transfer_proposals": transfer_proposals,
                "stockout_risk": stockout_risk,
            },
            rationale=rationale,
            confidence=0.8,
            messages=messages,
            used_fallback=False,
            status="success",
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "expiry_alerts": [],
                "low_stock_alerts": [],
                "demand_forecast": [],
                "transfer_proposals": [],
                "stockout_risk": "unknown",
            },
            rationale=(
                "Inventory service was unavailable this cycle; no expiry, stock or transfer "
                "assessment could be made. Reported as 'unknown' risk, not 'low' risk."
            ),
            confidence=0.0,
            messages=[],
            used_fallback=True,
            status="success",
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _case_mix_growth_factor(state: HealMatrixState) -> float:
        """Reads the Disease Forecast Agent's output out of shared state, if it has
        already run this cycle, and turns its 14-day forecast into a growth ratio
        against its own baseline. 1.0 (no adjustment) if that agent hasn't run yet."""
        from app.agents.state import result_of

        forecast_result = result_of(state, str(AgentName.DISEASE_FORECAST))
        if not forecast_result:
            return 1.0

        output = forecast_result.get("output", {})
        forecast = output.get("forecast_14d")
        baseline = output.get("baseline_mean")
        if not forecast or not baseline:
            return 1.0

        forecast_mean = sum(forecast) / len(forecast)
        return round(forecast_mean / baseline, 3) if baseline else 1.0

    @staticmethod
    def _demand_forecast(low_stock_alerts: list[dict], case_mix_growth: float) -> list[dict[str, Any]]:
        """Per-SKU forward demand: current consumption pressure (proxied by how far
        below reorder point a SKU sits) scaled by the case-mix growth factor."""
        forecast: list[dict[str, Any]] = []
        for row in low_stock_alerts:
            deficit = max(row.get("reorder_point", 0) - row.get("quantity", 0), 0)
            projected_units_14d = round(deficit * 2 * case_mix_growth, 1)
            forecast.append(
                {
                    "sku": row["sku"],
                    "medicine_name": row.get("medicine_name"),
                    "current_deficit_units": deficit,
                    "projected_units_14d": projected_units_14d,
                }
            )
        return forecast

    @staticmethod
    def _transfer_proposals(snapshot: list[dict] | None) -> list[dict[str, Any]]:
        """Match near-expiry surplus at one hospital against forecast deficit at
        another, for the same SKU, with the cold-chain guardrail applied unconditionally."""
        if not snapshot:
            return []

        by_sku: dict[str, list[dict]] = {}
        for row in snapshot:
            by_sku.setdefault(row["sku"], []).append(row)

        proposals: list[dict[str, Any]] = []
        for sku, rows in by_sku.items():
            donors = sorted(
                (r for r in rows if r.get("days_to_expiry", 999) <= NEAR_EXPIRY_DONOR_DAYS and r.get("surplus_units", 0) > 0),
                key=lambda r: r["days_to_expiry"],
            )
            recipients = sorted(
                (r for r in rows if r.get("deficit_units", 0) > 0),
                key=lambda r: -r["deficit_units"],
            )

            for donor in donors:
                for recipient in recipients:
                    if donor["hospital_id"] == recipient["hospital_id"]:
                        continue

                    is_cold_chain = donor.get("is_cold_chain", False)
                    if is_cold_chain and not (
                        donor.get("hospital_cold_chain_capable", False)
                        and recipient.get("hospital_cold_chain_capable", False)
                        and donor.get("route_cold_chain_capable", False)
                    ):
                        continue  # guardrail: any missing cold-chain link excludes the SKU entirely

                    units = min(donor["surplus_units"], recipient["deficit_units"])
                    if units <= 0:
                        continue

                    unit_cost_paise = donor.get("unit_cost_paise", 0)
                    carbon_kg_per_unit = donor.get("carbon_kg_per_unit", 0.0)

                    proposals.append(
                        {
                            "sku": sku,
                            "medicine_name": donor.get("medicine_name"),
                            "from_hospital_id": donor["hospital_id"],
                            "to_hospital_id": recipient["hospital_id"],
                            "units": units,
                            "units_saved": units,
                            "value_saved_paise": int(units * unit_cost_paise),
                            "co2e_avoided_kg": round(units * carbon_kg_per_unit, 3),
                            "donor_days_to_expiry": donor["days_to_expiry"],
                        }
                    )
                    donor["surplus_units"] -= units
                    recipient["deficit_units"] -= units

        return proposals
