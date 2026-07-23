"""Gemini access for agent rationale generation.

Per ``docs/04_agent_design.md`` section 3: numbers come from models, not the LLM.
Gemini is only ever asked to explain figures that were already computed by a rule
engine, an XGBoost model or a deterministic aggregation — never to forecast, sum or
score anything itself. Every call requests JSON conforming to a Pydantic schema; a
parse failure gets exactly one repair attempt before the caller's own
``BaseAgent.fallback()`` takes over.

If ``GOOGLE_API_KEY`` is unset, ``get_llm()`` returns ``None`` and every agent's
``analyse()`` is written to raise immediately in that case, which ``BaseAgent.run()``
turns into a clean drop to the deterministic path. Nothing here ever raises for a
missing key — that is an expected, first-class operating mode, not an error state.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@lru_cache(maxsize=1)
def _client():
    """The raw LangChain chat model, constructed once per process."""
    if not settings.llm_available:
        return None

    # Imported lazily: this pulls in google-generativeai, which is only installed
    # when requirements-ai.txt is layered on top of the core image (Phase 3 only).
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_output_tokens,
        timeout=settings.gemini_timeout_seconds,
    )


def llm_ready() -> bool:
    """Whether an agent may attempt an LLM call at all."""
    return settings.llm_available


async def structured_call(
    system_prompt: str,
    user_prompt: str,
    schema: type[SchemaT],
    *,
    temperature: float | None = None,
) -> SchemaT:
    """Ask Gemini for a response matching ``schema``, with one repair attempt.

    Raises on any failure (no key configured, network error, or two consecutive
    parse failures) — callers are expected to let that propagate out of their
    ``analyse()`` so ``BaseAgent.run()`` drops to ``fallback()``. This function never
    silently returns a degraded/partial value; a caller either gets a fully valid
    ``schema`` instance or an exception.
    """
    client = _client()
    if client is None:
        raise RuntimeError("No GOOGLE_API_KEY configured; LLM path unavailable.")

    if temperature is not None:
        client = client.bind(temperature=temperature)

    structured = client.with_structured_output(schema)
    messages = [("system", system_prompt), ("human", user_prompt)]

    try:
        return await structured.ainvoke(messages)
    except Exception as exc:  # noqa: BLE001 - one repair attempt regardless of failure mode
        logger.info("agent.llm_repair_attempt", schema=schema.__name__, error=str(exc))
        repair_messages = [
            ("system", system_prompt),
            ("human", user_prompt),
            (
                "human",
                "Your previous response did not parse as valid JSON matching the "
                "required schema. Reply again with ONLY the JSON object, no prose, "
                "no markdown fences.",
            ),
        ]
        return await structured.ainvoke(repair_messages)
