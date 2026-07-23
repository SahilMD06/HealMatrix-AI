"""Agent runs, notifications, reports, audit trail and knowledge-base chunks."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.constants import (
    AgentStatus,
    NotificationType,
    ReportType,
    Severity,
    TriggerType,
)
from app.models.base import (
    DateRange,
    DocumentModel,
    HealMatrixModel,
    ObjectIdField,
    TenantDocumentModel,
)


# ---------------------------------------------------------------- agent logs
class LLMUsage(HealMatrixModel):
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class AgentMessage(HealMatrixModel):
    """A message on the inter-agent bus carried in the LangGraph shared state."""

    from_agent: str
    to_agent: str | None = None  # None means broadcast
    intent: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class AgentError(HealMatrixModel):
    agent: str
    type: str
    message: str
    recoverable: bool = True


class AgentLog(TenantDocumentModel):
    """Immutable record of one agent execution. This is the machine-reasoning audit trail."""

    run_id: str
    agent_name: str
    agent_version: str
    triggered_by: TriggerType
    input_summary: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    rationale: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    messages_emitted: list[AgentMessage] = Field(default_factory=list)
    used_fallback: bool = False
    llm: LLMUsage | None = None
    duration_ms: int = 0
    status: AgentStatus = AgentStatus.SUCCESS
    error: AgentError | None = None
    correlation_id: str | None = None


# -------------------------------------------------------------- notification
class EntityRef(HealMatrixModel):
    collection: str
    id: ObjectIdField


class ReadReceipt(HealMatrixModel):
    user_id: ObjectIdField
    read_at: datetime


class Acknowledgement(HealMatrixModel):
    user_id: ObjectIdField
    acknowledged_at: datetime
    note: str | None = None


class Notification(TenantDocumentModel):
    type: NotificationType
    severity: Severity = Severity.INFO
    title: str
    message: str
    target_roles: list[str] = Field(default_factory=list)
    target_user_ids: list[ObjectIdField] = Field(default_factory=list)
    entity_ref: EntityRef | None = None
    source_agent: str | None = None
    agent_run_id: str | None = None
    action_url: str | None = None
    read_by: list[ReadReceipt] = Field(default_factory=list)
    acknowledged_by: Acknowledgement | None = None
    expires_at: datetime | None = None


# ------------------------------------------------------------------- reports
class Report(TenantDocumentModel):
    type: ReportType
    period: DateRange
    status: str = "queued"
    file_url: str | None = None
    file_size_bytes: int = 0
    page_count: int = 0
    summary: dict = Field(default_factory=dict)
    generated_by: ObjectIdField | None = None
    celery_task_id: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------- audit logs
class ResourceRef(HealMatrixModel):
    collection: str
    id: ObjectIdField | None = None


class ChangeSet(HealMatrixModel):
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)


class AuditLog(TenantDocumentModel):
    user_id: ObjectIdField | None = None
    action: str
    resource: ResourceRef
    changes: ChangeSet | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None


# --------------------------------------------------------------- knowledge
class KnowledgeChunk(DocumentModel):
    """Text chunk mirroring one row of the FAISS matrix."""

    doc_id: str
    chunk_id: str
    faiss_index_position: int = Field(ge=0)
    source_document: str
    section: str | None = None
    category: str
    content: str
    token_count: int = 0
    embedding_model: str
    index_version: str


# ------------------------------------------------------------ simulation
class SimulationEvent(TenantDocumentModel):
    tick: int = Field(ge=0)
    stream: str
    payload: dict = Field(default_factory=dict)
    scenario: str | None = None
    seed: int = 0
