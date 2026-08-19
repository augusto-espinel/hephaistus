# HephAIstus Patch Plan v1

`hephaistus/patch-plan/v1` is the deterministic contract between the copilot layer and the circuit backend.

A patch plan is a JSON object with an explicit schema, human-readable intent, and a bounded operation list.

```json
{
  "schema": "hephaistus/patch-plan/v1",
  "intent": "Insert a 1mΩ current shunt between C1 and R2",
  "operations": [
    {
      "type": "net.split",
      "origin_net": "dc_plus",
      "move_pins": ["R2.2"],
      "new_net": "dc_plus_shunt"
    },
    {
      "type": "component.add",
      "component": {
        "reference": "R3",
        "lib_id": "Device:R",
        "value": "0.001",
        "pins": {
          "1": "dc_plus",
          "2": "dc_plus_shunt"
        }
      }
    }
  ]
}
```

## Supported operations

### `pin.assign_net`

Assign one existing component pin to a net.

```json
{
  "type": "pin.assign_net",
  "reference": "R2",
  "pin": "2",
  "net": "dc_plus_shunt"
}
```

### `net.split`

Move one or more existing pins from an origin net to a new net. The backend maps this to deterministic pin net assignments and stub-based text application.

```json
{
  "type": "net.split",
  "origin_net": "dc_plus",
  "move_pins": ["R2.2"],
  "new_net": "dc_plus_shunt"
}
```

### `component.add`

Add a component by reference, library ID, value, and pin net assignments.

```json
{
  "type": "component.add",
  "component": {
    "reference": "R3",
    "lib_id": "Device:R",
    "value": "0.001",
    "pins": {"1": "dc_plus", "2": "dc_plus_shunt"}
  }
}
```

### `component.update_value`

Update a component's KiCad `Value` property through targeted text replacement.

```json
{"type": "component.update_value", "reference": "R2", "value": "1.2"}
```

### `component.remove`

Remove a component by UUID through the deterministic text-level deletion path.

```json
{"type": "component.remove", "reference": "R3"}
```

## Validation layers

The backend validates plans in this order:

1. **Schema validation** — version, operation list, operation shape, required fields.
2. **Semantic validation** — references, pins, unique component references, supported types.
3. **Integrity validation** — duplicate UUIDs, duplicate references, orphan pins.
4. **Round-trip validation** — apply to a temporary copy and re-parse before changing the original.

## Structured results

Successful validation returns an envelope such as:

```json
{
  "status": "validated",
  "schema": "hephaistus/patch-plan/v1",
  "intent": "Insert current shunt",
  "plan_id": "...",
  "created_at": "...",
  "delta": {"connection_changes": [], "added_components": []},
  "affected": {"components": ["R2", "R3"], "nets": ["dc_plus", "dc_plus_shunt"]},
  "changes": ["..."],
  "warnings": [],
  "round_trip": {"parse_ok": true, "erc_exit": null}
}
```

Apply returns the same shape with `status: "applied"` and `changed_operations`.

## Stable error codes

- `INVALID_SCHEMA` — malformed plan, unsupported schema, missing required fields.
- `UNSUPPORTED_OPERATION` — operation type outside the v1 registry.
- `UNKNOWN_COMPONENT` — referenced component does not exist.
- `UNKNOWN_PIN` — referenced pin does not exist.
- `INTEGRITY_VIOLATION` — duplicate UUID/reference or invalid graph invariants.
- `ROUND_TRIP_FAILED` — temporary write/re-parse validation failed.
- `APPLY_FAILED` — final deterministic text-level apply failed.

## CLI

Validate without touching the original file:

```bash
PYTHONPATH=backend .venv/bin/python -m hephaistus_circuit.cli apply-plan \
  fixtures/schematics/rectifier.kicad_sch \
  examples/patches/insert_shunt.json \
  --dry-run
```

Apply after preview:

```bash
PYTHONPATH=backend .venv/bin/python -m hephaistus_circuit.cli apply-plan \
  fixtures/schematics/rectifier.kicad_sch \
  examples/patches/insert_shunt.json
```
