"""Deterministic circuit patch engine.

This module turns an explicit patch plan into a modified schematic state and
then delegates safe text-level application to the ported KiCad apply backend.
"""

from __future__ import annotations

import copy
import json
import uuid as uuid_module
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

from .parser import parse_with_kiutils
from .text_apply import (
    apply_delta_to_schematic,
    compute_delta,
    validate_state_integrity,
)


class PatchPlanError(ValueError):
    """Raised when a patch plan cannot be validated."""


SUPPORTED_OPS = {"set_pin_net", "add_component", "update_value", "remove_component"}


def _new_uuid() -> str:
    return str(uuid_module.uuid4())


def _component_index(state: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(component.get("reference", "")): component
        for component in state.get("components", [])
        if component.get("reference")
    }


def _set_pin_net(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    reference = str(operation.get("reference", ""))
    pin_number = str(operation.get("pin", ""))
    new_net = str(operation.get("net", ""))
    components = _component_index(state)
    component = components.get(reference)
    if component is None:
        raise PatchPlanError(f"component '{reference}' does not exist")

    for pin in component.get("pins", []):
        if str(pin.get("number")) == pin_number:
            pin["net"] = new_net
            return

    raise PatchPlanError(f"pin '{reference}.{pin_number}' does not exist")


def _add_component(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    reference = str(operation.get("reference", ""))
    lib_id = str(operation.get("lib_id") or operation.get("libId") or "")
    value = str(operation.get("value", ""))
    pins = dict(operation.get("pins", {}) or {})

    if not reference:
        raise PatchPlanError("add_component requires 'reference'")
    if not lib_id:
        raise PatchPlanError(f"add_component {reference} requires 'lib_id'")
    components = _component_index(state)
    if reference in components:
        raise PatchPlanError(f"component '{reference}' already exists")

    pin_entries = []
    for pin_number, net in pins.items():
        pin_entries.append(
            {
                "number": str(pin_number),
                "uuid": _new_uuid(),
                "net": str(net or ""),
                "position": {"x": 0.0, "y": 0.0},
            }
        )

    component_uuid = str(operation.get("uuid") or _new_uuid())
    state.setdefault("components", []).append(
        {
            "uuid": component_uuid,
            "reference": reference,
            "libId": lib_id,
            "value": value,
            "properties": {"Value": value},
            "pins": pin_entries,
        }
    )


def _update_value(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    reference = str(operation.get("reference", ""))
    value = str(operation.get("value", ""))
    components = _component_index(state)
    component = components.get(reference)
    if component is None:
        raise PatchPlanError(f"component '{reference}' does not exist")
    component["value"] = value
    component.setdefault("properties", {})["Value"] = value


def _remove_component(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    reference = str(operation.get("reference", ""))
    components = state.get("components", [])
    remaining = [component for component in components if component.get("reference") != reference]
    if len(remaining) == len(components):
        raise PatchPlanError(f"component '{reference}' does not exist")
    state["components"] = remaining


def apply_operation_to_state(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    operations = operation.get("operations")
    if isinstance(operations, (list, dict)):
        raise PatchPlanError(
            "top-level operation objects are supported only inside a plan with an 'operations' list"
        )
    op_name = operation.get("op")
    if op_name == "set_pin_net":
        _set_pin_net(state, operation)
    elif op_name == "add_component":
        _add_component(state, operation)
    elif op_name == "update_value":
        _update_value(state, operation)
    elif op_name == "remove_component":
        _remove_component(state, operation)
    else:
        raise PatchPlanError(f"unsupported operation '{op_name or '<missing>'}'")


def _validate_plan(plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    operations = plan.get("operations")
    if not isinstance(operations, list) or not operations:
        raise PatchPlanError("patch plan must contain a non-empty 'operations' list")

    normalized: List[Dict[str, Any]] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            raise PatchPlanError(f"operation at index {index} must be an object")
        op_name = operation.get("op")
        if op_name not in SUPPORTED_OPS:
            raise PatchPlanError(f"operation at index {index} uses unsupported op '{op_name}'")
        normalized.append(dict(operation))
    return normalized


def mutate_state(original: Mapping[str, Any], plan: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a modified circuit state after validating and applying a plan."""
    modified: Dict[str, Any] = copy.deepcopy(dict(original))
    for operation in _validate_plan(plan):
        apply_operation_to_state(modified, operation)
    return modified


def parse_schematic(schematic_path: Path | str) -> Dict[str, Any]:
    """Parse a KiCad schematic into the derived circuit-state format."""
    parsed = parse_with_kiutils(str(schematic_path))
    if parsed is None:
        raise PatchPlanError(f"could not parse schematic: {schematic_path}")
    return parsed


def apply_patch_plan(
    schematic_path: Path | str,
    plan: Mapping[str, Any],
    output_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Validate and apply an explicit patch plan to a KiCad schematic."""
    path = Path(schematic_path)
    original = parse_schematic(path)
    modified = mutate_state(original, plan)

    original_errors = validate_state_integrity(original, "original")
    modified_errors = validate_state_integrity(modified, "modified")
    violations = original_errors + modified_errors
    if violations:
        raise PatchPlanError("integrity validation failed: " + "; ".join(violations))

    delta = compute_delta(original, modified)
    total_changes = (
        len(delta.get("value_changes", []))
        + len(delta.get("added_components", []))
        + len(delta.get("removed_components", []))
        + len(delta.get("connection_changes", []))
    )
    if total_changes == 0:
        return {
            "status": "no_changes",
            "changed_operations": [],
            "delta": delta,
        }

    success, changes, warnings = apply_delta_to_schematic(
        str(path),
        delta,
        output_path=str(output_path) if output_path else None,
        original_json=original,
        modified_json=modified,
    )
    if not success:
        raise PatchPlanError("apply failed: " + "; ".join(changes))

    return {
        "status": "applied",
        "changed_operations": len(changes),
        "changes": changes,
        "warnings": warnings,
        "delta": delta,
    }


def load_patch_plan(path: Path | str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=False)
