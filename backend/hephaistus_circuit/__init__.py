"""Deterministic KiCad circuit backend for the HephAIstus companion."""

from .engine import (
    PatchPlanError,
    apply_operation_to_state,
    apply_patch_plan,
    load_patch_plan,
    mutate_state,
    parse_schematic,
)

__all__ = [
    "PatchPlanError",
    "apply_operation_to_state",
    "apply_patch_plan",
    "load_patch_plan",
    "mutate_state",
    "parse_schematic",
]
