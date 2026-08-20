"""Deterministic circuit patch engine with hardened patch-plan contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import uuid as uuid_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

from .errors import (
    APPLY_FAILED,
    INTEGRITY_VIOLATION,
    INVALID_SCHEMA,
    ROUND_TRIP_FAILED,
    UNKNOWN_COMPONENT,
    UNKNOWN_PIN,
    UNSUPPORTED_OPERATION,
    PatchPlanError,
)
from .parser import parse_with_kiutils
from .text_apply import (
    apply_delta_to_schematic,
    compute_delta,
    validate_state_integrity,
)

SUPPORTED_SCHEMA = "hephaistus/patch-plan/v1"

CANONICAL_OPS = {
    "pin.assign_net",
    "net.split",
    "component.add",
    "component.update_value",
    "component.remove",
    "simulation.set_directive",
    "simulation.remove_directive",
}

LEGACY_OP_MAP = {
    "set_pin_net": "pin.assign_net",
    "add_component": "component.add",
    "update_value": "component.update_value",
    "remove_component": "component.remove",
}


def _new_uuid() -> str:
    return str(uuid_module.uuid4())


def _plan_id(plan: Mapping[str, Any]) -> str:
    payload = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _components_by_reference(state: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(component.get("reference", "")): component
        for component in state.get("components", [])
        if component.get("reference")
    }


def _normalise_operation(operation: Mapping[str, Any], index: int) -> Dict[str, Any]:
    op_type = operation.get("type") or operation.get("op")
    if op_type is None:
        raise PatchPlanError(
            INVALID_SCHEMA,
            f"operation at index {index} is missing 'type'",
        )

    if op_type in LEGACY_OP_MAP:
        op_type = LEGACY_OP_MAP[op_type]

    if op_type not in CANONICAL_OPS:
        raise PatchPlanError(
            UNSUPPORTED_OPERATION,
            f"operation at index {index} uses unsupported type '{op_type}'",
        )

    if op_type == "net.split":
        origin_net = operation.get("origin_net")
        move_pins = operation.get("move_pins", [])
        new_net = operation.get("new_net")
        if not origin_net or not isinstance(move_pins, list) or not new_net:
            raise PatchPlanError(
                INVALID_SCHEMA,
                "net.split requires origin_net, move_pins, and new_net",
                {"index": index},
            )
        return {
            "type": "pin.assign_net",
            "semantic_type": "net.split",
            "origin_net": str(origin_net),
            "move_pins": [str(pin) for pin in move_pins],
            "new_net": str(new_net),
        }

    return {"type": op_type, **dict(operation)}


def normalised_operations(plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    operations = plan.get("operations")
    schema = plan.get("schema")

    if schema and schema != SUPPORTED_SCHEMA:
        raise PatchPlanError(
            INVALID_SCHEMA,
            f"unsupported patch-plan schema '{schema}'",
            {"expected": SUPPORTED_SCHEMA},
        )
    if not isinstance(operations, list) or not operations:
        raise PatchPlanError(INVALID_SCHEMA, "patch plan has no operations")

    return [_normalise_operation(op, index) for index, op in enumerate(operations)]


def _resolve_pin_reference(reference_pin: str) -> tuple[str, str]:
    if "." not in reference_pin:
        raise PatchPlanError(
            INVALID_SCHEMA,
            f"pin reference '{reference_pin}' must use <COMPONENT>.<PIN> form",
        )
    reference, pin = reference_pin.split(".", 1)
    return reference, pin


def _assign_pin_net(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    references: List[tuple[str, str]] = []
    if operation.get("semantic_type") == "net.split":
        references = [_resolve_pin_reference(pin) for pin in operation.get("move_pins", [])]
        net = operation["new_net"]
    else:
        reference = operation.get("reference")
        pin = operation.get("pin")
        if not reference or not pin:
            raise PatchPlanError(
                INVALID_SCHEMA,
                "pin.assign_net requires reference and pin",
            )
        references = [(str(reference), str(pin))]
        net = str(operation.get("net", ""))

    components = _components_by_reference(state)
    for reference, pin_number in references:
        component = components.get(reference)
        if component is None:
            raise PatchPlanError(
                UNKNOWN_COMPONENT,
                f"component '{reference}' does not exist",
                {"operation": operation},
            )
        found = False
        for pin in component.get("pins", []):
            if str(pin.get("number")) == pin_number:
                pin["net"] = str(net or "")
                found = True
                break
        if not found:
            raise PatchPlanError(
                UNKNOWN_PIN,
                f"pin '{reference}.{pin_number}' does not exist",
                {"operation": operation},
            )


def _add_component(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    component_payload = operation.get("component")
    if component_payload is None:
        # Legacy add_component format
        component_payload = {
            "reference": operation.get("reference"),
            "lib_id": operation.get("lib_id") or operation.get("libId"),
            "value": operation.get("value", ""),
            "pins": operation.get("pins", {}),
            "uuid": operation.get("uuid"),
        }
    if not isinstance(component_payload, Mapping):
        raise PatchPlanError(
            INVALID_SCHEMA,
            "component.add requires a component object",
            {"operation": operation},
        )

    reference = str(component_payload.get("reference", ""))
    lib_id = str(component_payload.get("lib_id") or component_payload.get("libId") or "")
    value = str(component_payload.get("value", ""))
    pins = dict(component_payload.get("pins", {}) or {})

    if not reference:
        raise PatchPlanError(INVALID_SCHEMA, "component.add requires component.reference")
    if not lib_id:
        raise PatchPlanError(INVALID_SCHEMA, "component.add requires component.lib_id")
    components = _components_by_reference(state)
    if reference in components:
        raise PatchPlanError(INTEGRITY_VIOLATION, f"component '{reference}' already exists")

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

    component_uuid = str(component_payload.get("uuid") or _new_uuid())
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
    value = operation.get("value")
    if not reference:
        raise PatchPlanError(INVALID_SCHEMA, "component.update_value requires reference")
    components = _components_by_reference(state)
    component = components.get(reference)
    if component is None:
        raise PatchPlanError(UNKNOWN_COMPONENT, f"component '{reference}' does not exist")
    component["value"] = str(value if value is not None else "")
    component.setdefault("properties", {})["Value"] = str(value if value is not None else "")


def _remove_component(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    reference = str(operation.get("reference", ""))
    if not reference:
        raise PatchPlanError(INVALID_SCHEMA, "component.remove requires reference")
    components = state.get("components", [])
    remaining = [component for component in components if component.get("reference") != reference]
    if len(remaining) == len(components):
        raise PatchPlanError(UNKNOWN_COMPONENT, f"component '{reference}' does not exist")
    state["components"] = remaining


def _set_simulation_directive(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    """Create or update a simulation directive."""
    directive_type = str(operation.get("directive", "") or operation.get("type", "")).lower()
    parameters = dict(operation.get("parameters", {}) or {})
    
    if not directive_type:
        raise PatchPlanError(INVALID_SCHEMA, "simulation.set_directive requires directive type")
    
    # Import here to avoid circular dependency
    from .simulation_directive import create_directive_text, validate_directive_type
    
    if not validate_directive_type(directive_type):
        raise PatchPlanError(
            UNSUPPORTED_OPERATION,
            f"unsupported simulation directive type '{directive_type}'",
            {"operation": operation},
        )
    
    # Build directive text
    directive_text = create_directive_text(directive_type, parameters)
    
    # Check if directive of this type already exists
    directives = state.setdefault("simulation_directives", [])
    existing = None
    for d in directives:
        if d.get("directive_type") == directive_type:
            existing = d
            break
    
    if existing:
        # Update existing
        existing["text"] = directive_text
        existing["parameters"] = parameters
    else:
        # Add new
        directives.append({
            "uuid": _new_uuid(),
            "text": directive_text,
            "directive_type": directive_type,
            "parameters": parameters,
            "position": operation.get("position", (0, 0, 0)),
            "exclude_from_sim": operation.get("exclude_from_sim", False),
        })


def _remove_simulation_directive(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    """Remove a simulation directive."""
    directive_type = str(operation.get("directive", "") or operation.get("type", "")).lower()
    
    if not directive_type:
        raise PatchPlanError(INVALID_SCHEMA, "simulation.remove_directive requires directive type")
    
    directives = state.get("simulation_directives", [])
    remaining = [d for d in directives if d.get("directive_type") != directive_type]
    
    if len(remaining) == len(directives):
        raise PatchPlanError(
            INVALID_SCHEMA,
            f"simulation directive '{directive_type}' does not exist",
            {"operation": operation},
        )
    
    state["simulation_directives"] = remaining


def apply_operation_to_state(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    op_type = operation.get("type")
    if op_type == "pin.assign_net":
        _assign_pin_net(state, operation)
    elif op_type == "component.add":
        _add_component(state, operation)
    elif op_type == "component.update_value":
        _update_value(state, operation)
    elif op_type == "component.remove":
        _remove_component(state, operation)
    elif op_type == "simulation.set_directive":
        _set_simulation_directive(state, operation)
    elif op_type == "simulation.remove_directive":
        _remove_simulation_directive(state, operation)
    else:
        raise PatchPlanError(UNSUPPORTED_OPERATION, f"unsupported operation '{op_type}'")


def mutate_state(original: Mapping[str, Any], plan: Mapping[str, Any]) -> Dict[str, Any]:
    modified: Dict[str, Any] = copy.deepcopy(dict(original))
    for operation in normalised_operations(plan):
        apply_operation_to_state(modified, operation)
    return modified


def parse_schematic(schematic_path: Path | str) -> Dict[str, Any]:
    parsed = parse_with_kiutils(str(schematic_path))
    if parsed is None:
        raise PatchPlanError(ROUND_TRIP_FAILED, f"could not parse schematic: {schematic_path}")
    return parsed


def _validated_state_pair(
    original: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> Dict[str, Any]:
    modified = mutate_state(original, plan)
    original_errors = validate_state_integrity(original, "original")
    modified_errors = validate_state_integrity(modified, "modified")
    violations = original_errors + modified_errors
    if violations:
        raise PatchPlanError(
            INTEGRITY_VIOLATION,
            "integrity validation failed",
            violations,
        )
    return modified


def _changed_count(delta: Mapping[str, Any]) -> int:
    return (
        len(delta.get("value_changes", []))
        + len(delta.get("added_components", []))
        + len(delta.get("removed_components", []))
        + len(delta.get("connection_changes", []))
        + len(delta.get("simulation_changes", []))
    )


def _affected(delta: Mapping[str, Any]) -> Dict[str, List[str]]:
    components = set()
    nets = set()
    for item in delta.get("value_changes", []):
        components.add(str(item.get("reference", "")))
    for item in delta.get("added_components", []):
        reference = item.get("reference")
        if reference:
            components.add(str(reference))
        for pin in item.get("pins", []):
            if pin.get("net"):
                nets.add(str(pin["net"]))
    for item in delta.get("removed_components", []):
        reference = item.get("reference")
        if reference:
            components.add(str(reference))
    for item in delta.get("connection_changes", []):
        reference = item.get("reference")
        if reference:
            components.add(str(reference))
        if item.get("old_net"):
            nets.add(str(item["old_net"]))
        if item.get("new_net"):
            nets.add(str(item["new_net"]))
    return {
        "components": sorted(item for item in components if item),
        "nets": sorted(item for item in nets if item),
    }


def _result_envelope(
    status: str,
    plan: Mapping[str, Any],
    *,
    delta: Optional[Mapping[str, Any]] = None,
    changes: Optional[List[str]] = None,
    warnings: Optional[List[Dict[str, Any]]] = None,
    round_trip: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "status": status,
        "schema": plan.get("schema", SUPPORTED_SCHEMA),
        "intent": plan.get("intent", ""),
        "plan_id": _plan_id(plan),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "delta": delta or {},
        "affected": _affected(delta or {}),
        "changes": changes or [],
        "warnings": warnings or [],
    }
    if round_trip is not None:
        payload["round_trip"] = dict(round_trip)
    return payload


def validate_patch_plan(
    schematic_path: Path | str,
    plan: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate a plan and return a structured dry-run result without writes."""
    path = Path(schematic_path)
    original = parse_schematic(path)
    modified = _validated_state_pair(original, plan)
    delta = compute_delta(original, modified)
    if _changed_count(delta) == 0:
        return _result_envelope("no_changes", plan, delta=delta)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_schematic = Path(temp_dir) / path.name
        shutil.copy2(path, temp_schematic)
        success, changes, warnings = apply_delta_to_schematic(
            str(temp_schematic),
            delta,
            original_json=original,
            modified_json=modified,
        )
        round_trip = {"parse_ok": False, "erc_exit": None}
        if success:
            try:
                parse_schematic(temp_schematic)
                round_trip["parse_ok"] = True
            except PatchPlanError:
                round_trip["parse_ok"] = False
    if not success or not round_trip.get("parse_ok"):
        raise PatchPlanError(
            ROUND_TRIP_FAILED,
            "round-trip validation failed for patch plan",
            changes,
        )
    return _result_envelope(
        "validated",
        plan,
        delta=delta,
        changes=changes,
        warnings=warnings,
        round_trip=round_trip,
    )


def apply_patch_plan(
    schematic_path: Path | str,
    plan: Mapping[str, Any],
    output_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Validate and apply an explicit patch plan to a KiCad schematic."""
    validated = validate_patch_plan(schematic_path, plan)
    if validated["status"] == "no_changes":
        validated["changed_operations"] = []
        return validated

    original = parse_schematic(schematic_path)
    modified = _validated_state_pair(original, plan)
    delta = compute_delta(original, modified)
    success, changes, warnings = apply_delta_to_schematic(
        str(schematic_path),
        delta,
        output_path=str(output_path) if output_path else None,
        original_json=original,
        modified_json=modified,
    )
    if not success:
        raise PatchPlanError(APPLY_FAILED, "apply failed", changes)

    payload = _result_envelope(
        "applied",
        plan,
        delta=delta,
        changes=changes,
        warnings=warnings,
        round_trip=validated.get("round_trip"),
    )
    payload["changed_operations"] = len(changes)
    return payload


def load_patch_plan(path: Path | str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=False)
