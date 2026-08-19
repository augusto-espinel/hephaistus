"""Stable error vocabulary for the deterministic circuit patch backend."""

from __future__ import annotations


class PatchPlanError(ValueError):
    """Typed patch-plan error carrying a stable machine-readable code."""

    def __init__(self, code: str, message: str, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []

    def to_dict(self):
        return {
            "status": "error",
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }


INVALID_SCHEMA = "INVALID_SCHEMA"
UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
UNKNOWN_COMPONENT = "UNKNOWN_COMPONENT"
UNKNOWN_PIN = "UNKNOWN_PIN"
INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"
ROUND_TRIP_FAILED = "ROUND_TRIP_FAILED"
APPLY_FAILED = "APPLY_FAILED"
