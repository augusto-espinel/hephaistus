# Circuit Engine Implementation

This document contains deep implementation details for the HephAIstus circuit engine.

## Parser (`parser.py`)

### Schematic to JSON State

The parser converts `.kicad_sch` S-expressions into structured JSON:

```json
{
  "components": [
    {
      "uuid": "...",
      "reference": "R1",
      "libId": "Device:R",
      "value": "10k",
      "pins": [
        {"number": "1", "uuid": "...", "net": "dc_plus", "position": {"x": 100, "y": 50}},
        {"number": "2", "uuid": "...", "net": "dc_minus", "position": {"x": 100, "y": 100}}
      ],
      "properties": {"Value": "10k", "Reference": "R1"},
      "position": {"x": 100, "y": 75, "angle": 0}
    }
  ],
  "nets": [
    {"name": "dc_plus", "pins": ["R1.1", "C1.1"]},
    {"name": "dc_minus", "pins": ["R1.2", "C1.2"]}
  ],
  "simulation_directives": [
    {"type": "tran", "text": ".tran 1u 10m", "parameters": {"step": "1u", "stop": "10m"}}
  ]
}
```

### Y-Coordinate Fix (2026-09-04)

**Problem:** Rotated components (IBGTs, transistors) had incorrect pin-to-net assignments.

**Root cause:** KiCad library symbols use Y-UP (Cartesian) coordinates while schematics use Y-DOWN (screen) coordinates.

**Solution:** Negate the Y coordinate when transforming from library to schematic space:

```python
schematic_y = symbol_y - library_y  # library_y is negated implicitly
```

### KiCad-Compatible Net Naming

Unnamed nets use KiCad's `Net-(Ref-PadName)` convention:

```python
# Before: synthetic names like N$1, N$2
net_name = f"N${net_counter}"

# After: KiCad-compatible names
net_name = f"Net-({reference}-{pin_name})"
```

This ensures parser output aligns with simulation logs and netlist exports.

### SPICE Property Inheritance

**Problem:** KiCad stores `Sim.*` properties in library symbols, not instances. When HephAIstus adds components, they're missing SPICE properties needed for simulation.

**Solution:**

1. **Parser merge:** Combine library + instance properties
   ```python
   lib_props = {p.key: p.value for p in lib_sym.properties}
   merged_props = {**lib_props, **instance_props}
   spice_props = {
       "device": merged_props.get('Sim.Device', ''),
       "library": merged_props.get('Sim.Library', ''),
       ...
   }
   ```

2. **Component creation copy:** When creating instances, copy `Sim.*` properties from library:
   ```python
   for prop_name in ['Sim.Device', 'Sim.Library', 'Sim.Name', 'Sim.Pins']:
       if prop_name in spice_props:
           property_blocks.append(f'\t\t(property "{prop_name}" "{spice_props[prop_name]}" ...)')
   ```

**Benefits:**
- Schematic is self-contained
- Works even if library is missing
- Safer for patch apply

**Detection:** SPICE symbols are identified by presence of `Sim.Device` property.

### B-Source Handling

**Problem:** B-sources (behavioral sources) need `Sim.Params` for their equations, but the LLM operates on a semantic `value` field.

**Current design:**

```
LLM: {"type": "component.update_value", "reference": "B1", "value": "I=10*sin(time)"}
    ↓ apply layer
KiCad: Sim.Params = 'type="B" model="I=10*sin(time)"'
```

The apply layer detects B-sources and routes the value to `Sim.Params`.

**Deferred consideration:** For reasoning about additional fields (e.g., `sim.type`), a `_kicad_fields` object could expose raw properties to the LLM. See `docs/spice_property_inheritance.md` for details.

## Patch Engine (`engine.py`)

### Operation Validation

All operations are validated in this order:

1. **Schema validation** — Required fields, correct types
2. **Semantic validation** — Referenced components/pins exist
3. **Integrity validation** — No duplicate UUIDs or references
4. **Round-trip validation** — Parse after write succeeds

### Error Codes

| Code | Meaning | Recovery |
|------|---------|----------|
| `INVALID_SCHEMA` | Malformed JSON | Fix JSON syntax |
| `UNSUPPORTED_OPERATION` | Unknown operation type | Use supported operation |
| `UNKNOWN_COMPONENT` | Reference doesn't exist | Use existing reference |
| `UNKNOWN_PIN` | Pin doesn't exist | Use valid pin number |
| `INTEGRITY_VIOLATION` | Duplicate UUID/ref | Assign fresh UUIDs |
| `ROUND_TRIP_FAILED` | Parse after write failed | Check KiCad version |
| `APPLY_FAILED` | Text-level apply failed | Check schematic integrity |

### State Mutation

Each operation mutates the JSON state:

```python
def _add_component(state, operation):
    component = operation["component"]
    state["components"].append({
        "uuid": new_uuid(),
        "reference": component["reference"],
        "libId": component["lib_id"],
        "value": component.get("value", ""),
        "pins": [...],
    })
```

## Text Apply (`text_apply.py`)

### Stub-Based Net Restructuring

**Core insight:** Series insertions (shunts, series resistors) are expressed as pin net re-assignments, not wire surgery.

**Flow:**

1. **Detect nets losing pins:** Find nets where `old_pins - new_pins`
2. **Strip all wires/junctions/labels:** Use kiutils island BFS to find connected elements
3. **Create stubs:** For each re-assigned pin, create:
   - A short wire from pin position outward
   - A net label at the wire end with the NEW net name
4. **Add new components:** Place in staging area with proper pin connections

**Example:** Insert R_shunt between R2 and net `dc_plus`:

```json
{
  "operations": [
    {"type": "net.split", "origin_net": "dc_plus", "move_pins": ["R2.2"], "new_net": "dc_plus_shunt"},
    {"type": "component.add", "component": {"reference": "R_shunt", "lib_id": "Device:R", "pins": {"1": "dc_plus", "2": "dc_plus_shunt"}}}
  ]
}
```

### Library Embedding

When adding a component with a `lib_id` not in the schematic's `lib_symbols` section:

1. **Resolve library path:** Search sym-lib-table for library nickname
2. **Load symbol definition:** Parse from library file
3. **Embed in schematic:** Add to `lib_symbols` section
4. **Create instance:** Reference the embedded symbol

**Missing library:** Warn user to import in KiCad and re-apply.

### Component Staging

New components are placed in a staging area beyond existing symbols:

```python
def find_existing_symbols_bounds(content):
    # Find max x, y of all symbol positions
    # Stage new components at (max_x + margin, mid_y)
```

**Fix (2026-09-03):** Only use symbol positions (first `(at ...)` in block), not property positions which can be offset.

### Value Escaping

**Problem:** B-source formulas contain quotes that need escaping in KiCad format.

**Solution:**

```python
# Before: type="B" model="I=..."
# After: type=\"B\" model=\"I=...\"
sim_params_value = f'type=\"B\" model=\"{model_value}\"'
```

The `replace_property_value` function properly handles escaped quotes when finding closing quotes.

## Simulation Directive (`simulation_directive.py`)

### Directive Parsing

Each SPICE directive type has specific parameter parsing:

```python
# .tran <step> <stop> [start] [max_step]
if directive_type == "tran":
    parts = params_str.split()
    params = {"step": parts[0], "stop": parts[1]}
    if len(parts) >= 3: params["start"] = parts[2]
    if len(parts) >= 4: params["max_step"] = parts[3]

# .ac <dec/oct/lin> <points> <start> <stop>
elif directive_type == "ac":
    parts = params_str.split()
    params = {"type": parts[0], "points": parts[1], "start": parts[2], "stop": parts[3]}
```

### Text Block Creation

Directives are stored as KiCad text elements:

```python
def create_text_block(text, x, y):
    return f'''(text "{text}"
    (at {x:.2f} {y:.2f} 0)
    (effects (font (size 1.27 1.27)))
)'''
```

### Supported Directives

| Directive | Parameters |
|-----------|------------|
| `tran` | step, stop, start?, max_step? |
| `ac` | type (dec/oct/lin), points, start, stop |
| `dc` | source, start, stop, step |
| `op` | (none) |
| `options` | key=value pairs |
| `ic` | V(node)=value pairs |
| `nodeset` | V(node)=value pairs |

## Testing

### Test Fixtures

- `fixtures/schematics/rectifier.kicad_sch` — 9 components, 5 nets
- `fixtures/schematics/midpoint_drift_full_SDC.kicad_sch` — IGBT inverter with SPICE models

### Round-Trip Validation

Every patch operation is validated by:

1. Apply to a temporary copy
2. Re-parse the modified file
3. Verify parse succeeds
4. (Optional) Run kicad-cli ERC

```python
with tempfile.TemporaryDirectory() as temp_dir:
    temp_schematic = Path(temp_dir) / path.name
    shutil.copy2(path, temp_schematic)
    apply_delta_to_schematic(str(temp_schematic), delta)
    parse_schematic(temp_schematic)  # Must succeed
```

## Common Issues

### Incorrect Pin Assignments for Rotated Components

**Cause:** Y-coordinate transformation missing or incorrect.

**Fix:** Ensure parser negates library Y coordinates when computing schematic pin positions.

### Duplicate UUID Errors

**Cause:** Hand-copying components without generating fresh UUIDs.

**Fix:** Use `repair_state_integrity()` to assign fresh UUIDs to components and pins.

### Missing SPICE Properties

**Cause:** SPICE symbol added without property inheritance.

**Fix:** Parser merges library + instance properties; component creation copies to instance.

### Stub Wires Not Following Moved Symbols

**Cause:** KiCad doesn't auto-drag connected elements when symbols are moved.

**Fix:** User must manually adjust in KiCad, or request a new patch to fix connectivity.

## Related Documents

- [`docs/patch-plan-v1.md`](../../docs/patch-plan-v1.md) — Patch-plan schema
- [`docs/spice_property_inheritance.md`](../../docs/spice_property_inheritance.md) — SPICE property deep dive
- [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) — Architecture overview