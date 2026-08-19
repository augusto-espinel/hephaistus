"""Deterministic KiCad circuit backend for the HephAIstus companion."""

from .engine import (
    apply_operation_to_state,
    apply_patch_plan,
    load_patch_plan,
    mutate_state,
    normalised_operations,
    parse_schematic,
    validate_patch_plan,
)
from .errors import PatchPlanError

__all__ = [
    "PatchPlanError",
    "apply_operation_to_state",
    "apply_patch_plan",
    "load_patch_plan",
    "mutate_state",
    "normalised_operations",
    "parse_schematic",
    "validate_patch_plan",
]
