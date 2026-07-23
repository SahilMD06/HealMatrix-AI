"""Domain exception hierarchy.

Services raise these; a single FastAPI exception handler converts them into a
consistent JSON envelope. Routes therefore never build error responses by hand.
"""

from typing import Any


class HealMatrixError(Exception):
    """Base class for every application error."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        self.code = code or self.code
        super().__init__(self.message)

    def to_dict(self, correlation_id: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "correlation_id": correlation_id,
            }
        }


# ------------------------------------------------------------------- 4xx
class NotFoundError(HealMatrixError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class ValidationError(HealMatrixError):
    status_code = 422
    code = "validation_error"
    message = "The request payload failed validation."


class ConflictError(HealMatrixError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class AuthenticationError(HealMatrixError):
    status_code = 401
    code = "authentication_failed"
    message = "Authentication credentials are missing or invalid."


class AuthorizationError(HealMatrixError):
    status_code = 403
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class TenantIsolationError(AuthorizationError):
    code = "tenant_isolation_violation"
    message = "Cross-hospital data access is not permitted."


class RateLimitError(HealMatrixError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please retry later."


# ------------------------------------------------------------------- 5xx
class DatabaseError(HealMatrixError):
    status_code = 503
    code = "database_unavailable"
    message = "The database is currently unavailable."


class ExternalServiceError(HealMatrixError):
    status_code = 502
    code = "external_service_error"
    message = "An upstream service failed."


class AgentExecutionError(HealMatrixError):
    status_code = 500
    code = "agent_execution_failed"
    message = "An AI agent failed to produce a result."


class ModelNotAvailableError(HealMatrixError):
    status_code = 503
    code = "model_unavailable"
    message = "The requested ML model artefact is not available."


# ---------------------------------------------------------- domain specific
class BedUnavailableError(ConflictError):
    code = "bed_unavailable"
    message = "No suitable bed is currently available."


class InsufficientStockError(ConflictError):
    code = "insufficient_stock"
    message = "Requested quantity exceeds available stock."


class ColdChainViolationError(ValidationError):
    code = "cold_chain_violation"
    message = "The proposed transfer violates cold-chain constraints."
