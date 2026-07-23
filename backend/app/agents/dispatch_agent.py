"""Ambulance Dispatch Agent.

Per docs/04_agent_design.md 2.9: capability filter -> capacity filter -> OSRM route
per candidate -> ETA ranking -> pre-emption check. The key distinction the spec
calls out explicitly: this selects the nearest *suitable* hospital, not the
nearest hospital — a cardiac call must not be routed to a site without a cath lab
just because it is five minutes closer, which is why the capability filter runs
before any distance/ETA computation, not after.

Routing goes through the public OSRM demo server (``settings.osrm_base_url``) when
reachable. That server has no uptime guarantee, so every route request has a
deterministic haversine-distance fallback with an assumed average urban ambulance
speed — this is not a lesser "fallback path" in the BaseAgent sense (it doesn't set
``used_fallback``), it is simply what a real dispatch system does when a routing
provider times out: estimate from geometry rather than block a 999 call.
"""

from __future__ import annotations

import math

import httpx

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.state import HealMatrixState
from app.core.config import settings
from app.core.constants import AgentName
from app.database.repositories import AmbulanceRepository, HospitalRepository

ASSUMED_URBAN_SPEED_KMPH = 32.0  # ambulance average with priority lane assist, city traffic
EARTH_RADIUS_KM = 6371.0


class AmbulanceDispatchAgent(BaseAgent):
    name = str(AgentName.DISPATCH)
    version = "1.0.0"

    def __init__(self, hospitals: HospitalRepository, ambulances: AmbulanceRepository) -> None:
        self.hospitals = hospitals
        self.ambulances = ambulances

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        call = state.get("ambulance_call")
        if not call:
            raise RuntimeError("No ambulance_call in state.")

        candidates = await self.hospitals.find_nearest_capable(
            longitude=call["longitude"],
            latitude=call["latitude"],
            capability=call.get("required_capability"),
            limit=5,
        )
        # Capacity filter: never propose a hospital reporting zero available beds
        # of the relevant type for this call, if that figure was supplied.
        candidates = [
            h for h in candidates
            if call.get("available_capacity_by_hospital", {}).get(str(h["_id"]), 1) > 0
        ]
        if not candidates:
            raise RuntimeError("No capable hospital with reported capacity for this call.")

        available_ambulances: list[dict] = state.get("available_ambulances") or []
        active_assignments: list[dict] = state.get("active_assignments") or []

        ambulance, preempted_call_id = self._select_ambulance(
            available_ambulances, active_assignments, call["priority"]
        )
        if ambulance is None:
            raise RuntimeError("No idle or pre-emptable ambulance available for this priority.")

        ranked = []
        for hospital in candidates:
            eta_minutes, distance_km, polyline = await self._route(
                ambulance["current_location"], hospital["location"]
            )
            ranked.append((eta_minutes, distance_km, polyline, hospital))
        ranked.sort(key=lambda row: row[0])
        eta_minutes, distance_km, polyline, destination = ranked[0]

        fuel_litres = round(distance_km / max(ambulance.get("fuel_efficiency_kmpl", 8.0), 0.1), 2)

        rationale = (
            f"Assigned {ambulance['vehicle_number']} to a priority-{call['priority']} call, "
            f"routed to {destination['name']} ({round(eta_minutes, 1)} min, {round(distance_km, 1)} km) "
            f"— the nearest hospital with the required capability "
            f"({call.get('required_capability') or 'general'}) and reported capacity, not simply "
            f"the nearest hospital overall."
        )
        if preempted_call_id:
            rationale += (
                f" This required pre-empting lower-priority call {preempted_call_id}, "
                "which should be reassigned to the next available unit."
            )

        messages = [
            emit(
                self.name,
                "inbound_patient_eta",
                {"eta_minutes": round(eta_minutes, 1), "destination_hospital_id": str(destination["_id"])},
                to_agent=str(AgentName.BED_ALLOCATION),
            ),
            emit(
                self.name,
                "fuel_litres",
                {"fuel_litres": fuel_litres},
                to_agent=str(AgentName.CARBON),
            ),
        ]

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "assigned_ambulance_id": str(ambulance["_id"]),
                "destination_hospital_id": str(destination["_id"]),
                "destination_hospital_name": destination["name"],
                "eta_minutes": round(eta_minutes, 1),
                "distance_km": round(distance_km, 1),
                "route_polyline": polyline,
                "preempted_call_id": preempted_call_id,
                "fuel_litres": fuel_litres,
                "alternatives_considered": len(ranked),
            },
            rationale=rationale,
            confidence=0.85 if not preempted_call_id else 0.6,
            messages=messages,
            used_fallback=False,
            status="success",
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "assigned_ambulance_id": None,
                "destination_hospital_id": None,
                "eta_minutes": None,
                "distance_km": None,
                "route_polyline": None,
                "preempted_call_id": None,
                "escalation": "manual_dispatch_required",
            },
            rationale=(
                "Automated dispatch could not complete (no suitable hospital, no available "
                "ambulance, or a service error). Escalated for manual dispatch by the control room."
            ),
            confidence=0.0,
            messages=[],
            used_fallback=True,
            status="success",
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _select_ambulance(
        available: list[dict], active_assignments: list[dict], call_priority: int
    ) -> tuple[dict | None, str | None]:
        idle = [a for a in available if a.get("status") == "idle" and a.get("is_active", True)]
        if idle:
            return idle[0], None

        # Pre-emption: only a strictly lower-priority (numerically higher, since 1
        # is most urgent) active assignment may be bumped, and only one at a time.
        preemptable = [
            a for a in active_assignments
            if a.get("active_call", {}).get("priority", 0) > call_priority
        ]
        if preemptable:
            preemptable.sort(key=lambda a: -a["active_call"]["priority"])
            chosen = preemptable[0]
            return chosen, chosen["active_call"]["call_id"]

        return None, None

    async def _route(
        self, origin: dict, destination: dict
    ) -> tuple[float, float, str | None]:
        """(eta_minutes, distance_km, polyline). Tries OSRM, falls back to haversine."""
        origin_coords = origin["coordinates"]  # [lon, lat]
        dest_coords = destination["coordinates"]

        try:
            url = (
                f"{settings.osrm_base_url}/route/v1/driving/"
                f"{origin_coords[0]},{origin_coords[1]};{dest_coords[0]},{dest_coords[1]}"
                "?overview=simplified"
            )
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            route = data["routes"][0]
            distance_km = route["distance"] / 1000.0
            eta_minutes = (route["duration"] / 60.0) * settings.routing_detour_factor
            polyline = route.get("geometry")
            return eta_minutes, distance_km, polyline
        except Exception:
            distance_km = self._haversine_km(origin_coords, dest_coords) * settings.routing_detour_factor
            eta_minutes = (distance_km / ASSUMED_URBAN_SPEED_KMPH) * 60.0
            return eta_minutes, distance_km, None

    @staticmethod
    def _haversine_km(a: list[float], b: list[float]) -> float:
        lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
