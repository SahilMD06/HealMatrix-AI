"""The agent contract every one of the ten agents implements.

See ``docs/04_agent_design.md`` section 1 — this module is that contract's runtime
form. The template method in ``BaseAgent.run`` is what makes every agent behave
identically from the orchestrator's point of view: timing, a hard timeout, a single
retry on a transient failure, an automatic drop to the deterministic ``fallback()``
on anything else, and — critically — logging that happens whether the agent
succeeded, degraded or failed, so the audit trail (``AgentLog`` / ``/agents/runs``)
never has a gap.

Design rule from the spec, worth repeating here because it is easy to violate by
accident: agents call *services*, never repositories, and never mutate persisted
state directly. A bed cannot be double-booked by an agent because the same
``BedService.reserve()`` invariant applies to agents and humans alike.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.intelligence import AgentMessage
from app.agents.state import HealMatrixState

logger = get_logger(__name__)

AgentStatusLiteral = Literal["success", "degraded", "failed"]


class AgentResult(BaseModel):
    """Uniform output every agent produces, whichever path (analyse/fallback) ran."""

    agent: str
    version: str
    output: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    messages: list[AgentMessage] = Field(default_factory=list)
    used_fallback: bool = False
    duration_ms: int = 0
    status: AgentStatusLiteral = "success"
    llm_model: str | None = None
    error: str | None = None


class BaseAgent(ABC):
    """Base class for all ten HealMatrix agents."""

    name: str
    version: str = "1.0.0"

    @abstractmethod
    async def analyse(self, state: HealMatrixState) -> AgentResult:
        """Primary path. May call a trained model, RAG and/or Gemini.

        Must raise (not return a degraded result) on any failure it cannot recover
        from itself — the template method in ``run()`` is what decides whether that
        becomes a retry or a drop to ``fallback()``.
        """

    @abstractmethod
    def fallback(self, state: HealMatrixState) -> AgentResult:
        """Deterministic path. Must never raise and must never touch the network.

        This is what runs with zero API keys configured, and it is also what a
        guardrail test calls directly to prove the agent has a safe floor.
        """

    async def run(self, state: HealMatrixState) -> AgentResult:
        """Template method: timing, one retry, guaranteed fallback, uniform logging."""
        started = time.perf_counter()

        for attempt in range(settings.agent_max_retries):
            try:
                result = await asyncio.wait_for(
                    self.analyse(state), timeout=settings.agent_timeout_seconds
                )
                result.duration_ms = self._elapsed_ms(started)
                return result
            except asyncio.TimeoutError:
                logger.warning(
                    "agent.analyse_timeout", agent=self.name, attempt=attempt + 1
                )
            except Exception as exc:  # noqa: BLE001 - any agent-internal failure falls back
                logger.warning(
                    "agent.analyse_failed",
                    agent=self.name,
                    attempt=attempt + 1,
                    error=str(exc),
                )

        # Every retry failed (or attempts == 0, e.g. no LLM configured at all).
        # The deterministic floor must never raise; if it somehow does, that is a
        # genuine bug and is allowed to propagate rather than be hidden.
        fallback_result = self.fallback(state)
        fallback_result.agent = self.name
        fallback_result.version = self.version
        fallback_result.used_fallback = True
        fallback_result.duration_ms = self._elapsed_ms(started)
        if fallback_result.status == "success":
            fallback_result.status = "degraded"
        return fallback_result

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)


def emit(from_agent: str, intent: str, payload: dict[str, Any], to_agent: str | None = None) -> AgentMessage:
    """Convenience constructor for the inter-agent bus messages listed per-agent in the spec."""
    return AgentMessage(from_agent=from_agent, to_agent=to_agent, intent=intent, payload=payload)
