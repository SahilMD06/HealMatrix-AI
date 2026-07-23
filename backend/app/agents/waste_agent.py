"""Biomedical Waste Agent.

Per docs/04_agent_design.md 2.7: RAG-grounded category classification -> generation
forecast -> segregation anomaly detection -> pickup scheduling within the 48h
yellow-category limit -> recyclable recovery estimate.

The guardrail here is the RAG grounding requirement itself: every classification
this agent returns cites the corpus chunk(s) it relied on
(``app/rag/retriever.py``, backed by ``knowledge_base/cpcb_biomedical_waste_rules_2016.md``).
If retrieval doesn't surface anything above ``settings.rag_score_threshold``, the
agent returns ``"requires_manual_review"`` rather than guessing — an unsupported
category assignment is a compliance and patient-safety risk, not a minor miss (see
section 7 of the corpus document itself, which states this explicitly).
"""

from __future__ import annotations

import statistics

from pydantic import BaseModel, Field

from app.agents.base import AgentResult, BaseAgent, emit
from app.agents.llm import llm_ready, structured_call
from app.agents.state import HealMatrixState
from app.core.config import settings
from app.core.constants import (
    MAX_STORAGE_HOURS,
    WASTE_CATEGORY_DESCRIPTION,
    AgentName,
    WasteCategory,
)
from app.rag.retriever import retrieve

SEGREGATION_ANOMALY_THRESHOLD = 0.65

# Distinctive nouns each category is actually defined by (see the CPCB corpus,
# section 2) — deliberately narrow, so the deterministic fallback path only ever
# fires on real category-defining vocabulary, not on incidental word overlap with
# a category's prose description (which is generic enough to false-match almost
# anything). Anything that doesn't hit one of these is "requires_manual_review",
# which is the safe direction to fail in.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "yellow": ("anatomical", "tissue", "organ", "soiled", "dressing", "plaster",
               "expired medicine", "expired drug", "chemical waste", "microbiology",
               "biotechnology", "placenta", "body part"),
    "red": ("tubing", "iv set", "catheter", "urine bag", "syringe without needle",
            "glove", "cannula", "suction"),
    "white": ("needle", "scalpel", "blade", "sharp", "lancet", "syringe with",
              "trocar"),
    "blue": ("glass", "glassware", "vial", "ampoule", "metallic implant",
              "body implant"),
    "general": ("kitchen", "packaging", "office waste", "food waste"),
}


class _WasteClassification(BaseModel):
    category: str = Field(description="One of: yellow, red, white, blue, general")
    reasoning: str = Field(description="1-3 sentences, grounded only in the provided evidence.")


class BiomedicalWasteAgent(BaseAgent):
    name = str(AgentName.WASTE)
    version = "1.0.0"

    async def analyse(self, state: HealMatrixState) -> AgentResult:
        description = state.get("waste_description")
        if not description:
            raise RuntimeError("No waste_description provided for classification this cycle.")

        chunks = await retrieve(description, category="biomedical_waste")
        supporting_chunks = [c for c in chunks if c.get("relevance_score", 0.0) >= settings.rag_score_threshold]

        classification: str | None = None
        reasoning: str | None = None
        llm_model_used: str | None = None

        if supporting_chunks:
            evidence = "\n\n".join(
                f"[{i + 1}] {c.get('section') or c.get('doc_id')}: {c['content']}"
                for i, c in enumerate(supporting_chunks)
            )
            if llm_ready():
                try:
                    structured = await structured_call(
                        system_prompt=(
                            "You classify biomedical waste into CPCB colour categories "
                            "(yellow, red, white, blue, general) using ONLY the evidence "
                            "provided. If the evidence does not clearly support one category, "
                            "respond with category 'requires_manual_review' rather than guessing."
                        ),
                        user_prompt=f"Waste description: {description}\n\nEvidence:\n{evidence}",
                        schema=_WasteClassification,
                        temperature=settings.gemini_temperature,
                    )
                    classification = structured.category
                    reasoning = structured.reasoning
                    llm_model_used = settings.gemini_model
                except Exception:
                    classification = None

            if classification is None:
                classification, reasoning = self._keyword_classification(description, supporting_chunks)

        if classification is None:
            classification = "requires_manual_review"
            reasoning = (
                "No corpus evidence scored above the relevance threshold "
                f"({settings.rag_score_threshold}) for this description; classification "
                "withheld rather than guessed."
            )

        citations = [
            {
                "source_document": c.get("source_document"),
                "section": c.get("section"),
                "chunk_id": c.get("chunk_id"),
                "relevance_score": round(c.get("relevance_score", 0.0), 3),
            }
            for c in supporting_chunks
        ]

        history = state.get("waste_history") or []
        forecast_kg = self._generation_forecast(history)
        segregation_anomalies = self._segregation_anomalies(history)
        pickup_schedule = self._pickup_schedule(history)
        diversion_rate, recyclable_recovered_kg = self._diversion_metrics(history)

        rationale = (
            f"Classification: {classification}"
            + (f" — {reasoning}" if reasoning else "")
            + f" ({len(citations)} supporting citation(s)). "
            f"7-day generation forecast averages {round(statistics.fmean(forecast_kg), 1) if forecast_kg else 0} kg/day. "
            f"{len(segregation_anomalies)} segregation anomal{'y' if len(segregation_anomalies) == 1 else 'ies'} flagged. "
            f"Current diversion rate {round(diversion_rate * 100, 1)}%."
        )

        messages = [
            emit(
                self.name,
                "waste_by_method",
                {"diversion_rate": diversion_rate, "recyclable_recovered_kg": recyclable_recovered_kg},
                to_agent=str(AgentName.CARBON),
            )
        ]

        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "classification": classification,
                "citations": citations,
                "forecast_kg": forecast_kg,
                "segregation_anomalies": segregation_anomalies,
                "pickup_schedule": pickup_schedule,
                "diversion_rate": diversion_rate,
                "recyclable_recovered_kg": recyclable_recovered_kg,
            },
            rationale=rationale,
            confidence=0.85 if citations else 0.0,
            messages=messages,
            used_fallback=False,
            status="success",
            llm_model=llm_model_used,
        )

    def fallback(self, state: HealMatrixState) -> AgentResult:
        return AgentResult(
            agent=self.name,
            version=self.version,
            output={
                "classification": "requires_manual_review",
                "citations": [],
                "forecast_kg": [],
                "segregation_anomalies": [],
                "pickup_schedule": [],
                "diversion_rate": 0.0,
                "recyclable_recovered_kg": 0.0,
            },
            rationale=(
                "The retrieval/classification pipeline was unavailable this cycle. Reported as "
                "'requires manual review' — never guessed a category without it."
            ),
            confidence=0.0,
            messages=[],
            used_fallback=True,
            status="success",
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _keyword_classification(description: str, chunks: list[dict]) -> tuple[str, str]:
        """Deterministic classification when the LLM path is unavailable: match
        against each category's distinctive defining vocabulary (``CATEGORY_KEYWORDS``),
        never against the generic prose description — see that constant's docstring
        for why the distinction matters for this guardrail."""
        text = description.lower()
        for category in WasteCategory:
            keywords = CATEGORY_KEYWORDS.get(str(category), ())
            matched = [keyword for keyword in keywords if keyword in text]
            if matched:
                return str(category), (
                    f"Matched category-defining term(s) {matched} for CPCB "
                    f"{category.value} ({WASTE_CATEGORY_DESCRIPTION[category]}), "
                    f"corroborated by {len(chunks)} retrieved corpus chunk(s)."
                )
        return "requires_manual_review", "No category-defining keyword matched in the description."

    @staticmethod
    def _generation_forecast(history: list[dict]) -> list[float]:
        if not history:
            return []
        by_weekday: dict[int, list[float]] = {i: [] for i in range(7)}
        for row in history:
            weekday = row.get("weekday")
            if weekday is not None:
                by_weekday[weekday].append(row.get("weight_kg", 0.0))
        if not any(by_weekday.values()):
            recent = [row.get("weight_kg", 0.0) for row in history[-7:]]
            avg = statistics.fmean(recent) if recent else 0.0
            return [round(avg, 1)] * 7
        return [round(statistics.fmean(v), 1) if v else 0.0 for v in by_weekday.values()]

    @staticmethod
    def _segregation_anomalies(history: list[dict]) -> list[dict]:
        return [
            {
                "date": str(row.get("date")),
                "category": row.get("category"),
                "segregation_score": row.get("segregation_score"),
            }
            for row in history
            if row.get("segregation_score", 1.0) < SEGREGATION_ANOMALY_THRESHOLD
        ]

    @staticmethod
    def _pickup_schedule(history: list[dict]) -> list[dict]:
        """Any record still pending pickup gets a scheduled-by time from
        ``MAX_STORAGE_HOURS`` for its category — the hard compliance ceiling, not a
        target to aim close to."""
        schedule = []
        for row in history:
            pickup = row.get("pickup") or {}
            if pickup.get("status") == "pending":
                category = row.get("category")
                limit_hours = MAX_STORAGE_HOURS.get(category, 24)
                schedule.append(
                    {
                        "category": category,
                        "weight_kg": row.get("weight_kg"),
                        "must_collect_within_hours": limit_hours,
                        "date": str(row.get("date")),
                    }
                )
        return schedule

    @staticmethod
    def _diversion_metrics(history: list[dict]) -> tuple[float, float]:
        """Diversion rate = share of waste NOT sent to landfill or incineration."""
        if not history:
            return 0.0, 0.0
        total = sum(row.get("weight_kg", 0.0) for row in history)
        if total == 0:
            return 0.0, 0.0
        diverted = sum(
            row.get("weight_kg", 0.0)
            for row in history
            if row.get("disposal_method") not in ("landfill", "incineration")
        )
        recyclable_recovered = sum(row.get("recyclable_recovered_kg", 0.0) for row in history)
        return round(diverted / total, 3), round(recyclable_recovered, 2)
