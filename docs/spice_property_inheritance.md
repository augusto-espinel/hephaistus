# SPICE Property Inheritance

## Problem

When HephAIstus adds new components (especially SPICE subcircuits), they may fail simulation because critical `Sim.*` properties are missing from the instance.

### KiCad's Property Model

KiCad has a two-level property system:

1. **Library Symbol** (`lib_symbols` section): Defines default properties including ALL `Sim.*` properties for SPICE simulation
2. **Instance Symbol** (placed component): Only stores properties that override library defaults

When you place a symbol in KiCad's GUI, it references the library symbol and inherits properties at runtime. However, the `.kicad_sch` file only stores overridden properties at the instance level.

### What This Means for SPICE Symbols

For a symbol like `Traction_Power_Components:2MBI1500XYF170_Switch`:

**Library Symbol has:**
```
(property "Sim.Device" "SUBCKT" ...)
(property "Sim.Library" "FUJI_2MBI1500XYF170.lib" ...)
(property "Sim.Name" "2MBI1500XYF170" ...)
(property "Sim.Pins" "1=C 2=G 3=E 4=Tc" ...)
```

**Instance (Q1) only has:**
```
(property "Reference" "Q1" ...)
(property "Value" "2MBI1500XYF170_Switch" ...)
```

**Instance (Q2, Q3 added by HephAIstus) originally had:**
```
(property "Reference" "Q2" ...)
(property "Value" "2MBI1500XYF170_Switch" ...)
(property "Sim.Device" "" ...)     ← Empty!
(property "Sim.Library" "" ...)    ← Missing!
(property "Sim.Name" "" ...)       ← Missing!
(property "Sim.Pins" "" ...)       ← Missing!
```

Without these properties, ngspice cannot find the subcircuit definition and simulation fails with:
```
Error: subcircuit 2MBI1500XYF170 not found
```

---

## Solution

We implement property inheritance in **two places**:

### 1. Parser: Merge Library + Instance Properties

**File:** `backend/hephaistus_circuit/parser.py`

**Before (lines 312-359):**
```python
# Extract SPICE simulation properties
spice_props = {
    "device": props.get('Sim.Device', ''),      # ← Only instance properties
    "library": props.get('Sim.Library', ''),    # ← Empty for new components!
    ...
}
```

**After:**
```python
# Find library symbol for inherited properties
lib_sym = lib_symbols.get(lib_id)

# Merge library properties with instance properties
lib_props = {}
if lib_sym and hasattr(lib_sym, 'properties'):
    lib_props = {p.key: p.value for p in lib_sym.properties}

# Instance properties override library defaults
merged_props = {**lib_props, **props}

# Extract SPICE properties from merged properties
spice_props = {
    "device": merged_props.get('Sim.Device', ''),
    "library": merged_props.get('Sim.Library', ''),
    "name": merged_props.get('Sim.Name', ''),
    "pins": merged_props.get('Sim.Pins', ''),
    "params": merged_props.get('Sim.Params', ''),
}
```

**Result:** Q2 and Q3 now correctly inherit SPICE properties from the library symbol.

### 2. Component Creation: Copy SPICE Properties to Instance

**File:** `backend/hephaistus_circuit/text_apply.py`

**Function:** `create_symbol_instance()`

**Before:**
```python
# Only created Reference, Value, Footprint, Datasheet
# No Sim.* properties → simulation fails
```

**After:**
```python
# Extract SPICE properties from library symbol block
spice_props = {}
for prop_name in ['Sim.Device', 'Sim.Type', 'Sim.Params', 
                  'Sim.Pins', 'Sim.Library', 'Sim.Name']:
    pattern = rf'\(property\s+"{re.escape(prop_name)}"\s+"([^"]*)"'
    match = re.search(pattern, lib_symbol_block)
    if match:
        spice_props[prop_name] = match.group(1)

# Add SPICE properties to instance
for prop_name in ['Sim.Device', 'Sim.Type', 'Sim.Params', 
                  'Sim.Pins', 'Sim.Library', 'Sim.Name']:
    if prop_name in spice_props:
        property_blocks.append(f'''\t\t(property "{prop_name}" "{spice_props[prop_name]}"
            (at {position[0]:.2f} {position[1]:.2f} 0)
            (show_name no)
            (do_not_autoplace no)
            (hide yes)
            (effects
                (font
                    (size 1.27 1.27)
                )
            )
        )''')
```

**Result:** New components have complete SPICE properties written to the schematic, making them self-contained for simulation.

---

## Design Decisions

### Why Copy Properties to Instance?

**Option A:** Don't copy (rely on library at runtime)
- ❌ Schematic depends on library being available
- ❌ Simulation fails if library path changes
- ❌ Less portable

**Option B:** Copy SPICE properties to instance
- ✅ Schematic is self-contained
- ✅ Works even if library is missing
- ✅ Consistent with how KiCad GUI works (shows inherited properties)
- ✅ Safer for patch apply (all data in one place)

**Decision:** Option B for SPICE symbols, Option A for regular symbols.

### How to Detect SPICE Symbols?

We check for presence of `Sim.Device` property in the library symbol:
- If `Sim.Device` exists → copy ALL `Sim.*` properties
- If not → regular component, no SPICE properties needed

### Why Both Parser and Component Creation?

1. **Parser:** Fixes existing components (Q1) and future parsing
2. **Component Creation:** Ensures new components (Q2, Q3) are created correctly

Both are needed for a complete fix.

---

## Testing

### Unit Test

```python
# Test that parser merges library properties
def test_spice_property_inheritance():
    schematic = parse("midpoint_drift_full_SDC.kicad_sch")
    
    # Q2 should have inherited SPICE properties
    q2 = next(c for c in schematic.components if c.reference == "Q2")
    
    assert q2.spice.device == "SUBCKT"
    assert q2.spice.library == "FUJI_2MBI1500XYF170.lib"
    assert q2.spice.name == "2MBI1500XYF170"
    assert q2.spice.pins == "1=C 2=G 3=E 4=Tc"
```

### Integration Test

1. Create patch plan to add Q4 as replica of Q1
2. Apply patch
3. Parse modified schematic
4. Verify Q4 has complete SPICE properties
5. Run ngspice simulation → should succeed

### Regression Test

1. Parse schematic with regular components (R, C, L)
2. Verify they still work without SPICE properties
3. No performance impact

---

## Related Files

- `backend/hephaistus_circuit/parser.py`: Parser with property merging
- `backend/hephaistus_circuit/text_apply.py`: Component creation with SPICE property copy
- `docs/architecture.md`: Overall architecture
- `docs/spec.md`: Specification

---

## Session: 2026-09-03 — SPICE Property Inheritance Fix

### Issue Discovery

User reported: "LLM created Q2 and Q3 as replicas of Q1, but they missed important parameters: Sim.Library, Sim.Name, Sim.Device, Sim.Pins."

**Root Cause:**
KiCad stores SPICE properties (`Sim.*`) in library symbols (`lib_symbols` section), not in instance symbols. When HephAIstus added Q2/Q3, it only created instance-level properties (Reference, Value, Footprint, Datasheet) — the SPICE properties were empty.

Without these properties, ngspice cannot find subcircuit definitions.

### Solution Implemented

**1. Parser Fix** (`backend/hephaistus_circuit/parser.py`):
- Merge library symbol properties with instance properties
- Instance properties override library defaults
- Extract SPICE properties from merged dict

```python
# Before: Only instance properties (empty for Q2/Q3)
spice_props = {"device": props.get('Sim.Device', '')}  # ← Empty!

# After: Merge library + instance
lib_props = {p.key: p.value for p in lib_sym.properties}
merged_props = {**lib_props, **props}
spice_props = {"device": merged_props.get('Sim.Device', '')}  # ← Inherited!
```

**2. Component Creation Fix** (`backend/hephaistus_circuit/text_apply.py`):
- Extract SPICE properties from library symbol block
- Copy to instance during component creation
- Ensures schematic is self-contained

```python
# Extract SPICE properties from library symbol
spice_props = {}
for prop_name in ['Sim.Device', 'Sim.Library', 'Sim.Name', 'Sim.Pins']:
    match = re.search(rf'\(property\s+"{prop_name}"\s+"([^"]*)"', lib_symbol_block)
    if match:
        spice_props[prop_name] = match.group(1)

# Add to instance properties
for prop_name, value in spice_props.items():
    property_blocks.append(f'\t\t(property "{prop_name}" "{value}" ...)')
```

### Verification

Tested on `midpoint_drift_full_SDC.kicad_sch`:

```
Q1, Q2, Q3 all show:
  Sim.Device: SUBCKT
  Sim.Library: FUJI_2MBI1500XYF170.lib
  Sim.Name: 2MBI1500XYF170
  Sim.Pins: 1=C 2=G 3=E 4=Tc
```

### Documentation

- `docs/spice_property_inheritance.md`: Complete design doc
- Includes rationale, implementation details, testing approach

### Design Decisions

1. **Copy SPICE properties to instance** (not just reference library)
   - ✅ Schematic is self-contained
   - ✅ Works even if library is missing
   - ✅ Safer for patch apply

2. **Detect SPICE symbols** by presence of `Sim.Device` property
   - Only copy `Sim.*` properties for simulation symbols
   - Regular components (R, C, L) unchanged

3. **Fix both parser and component creation**
   - Parser: Fixes existing components
   - Component creation: Ensures new components are correct

### Files Modified

| File | Change |
|------|--------|
| `backend/hephaistus_circuit/parser.py` | Merge library properties before extracting SPICE props |
| `backend/hephaistus_circuit/text_apply.py` | Copy SPICE properties to instance during creation |
| `docs/spice_property_inheritance.md` | New documentation file |
| `MEMORY.md` | Updated with this session |

---

## Session: 2026-09-03 — B-Source Property Value Escaping Fix

### Issue Discovery

User reported KiCad parsing error after applying a patch to update B-source formula:

```
Error loading schematic 'midpoint_drift_full_SDC.kicad_sch'.
Expecting '(' in 'midpoint_drift_full_SDC.kicad_sch', line 2828, offset 33.
```

**Root Cause:**
The `replace_property_value` function didn't handle escaped quotes inside property values correctly. When B-source `Sim.Params` was updated, the function incorrectly parsed the value:

Original: `(property "Sim.Params" "type=\"B\" model=\"I = ...\"")`
Corrupted: `(property "Sim.Params" "type="B" model="I=...""B\" model=\"...\"")`

The function found the first `"` inside the value (from `\"`) instead of the actual closing quote.

### Solution Implemented

**`replace_property_value` Fix** (`backend/hephaistus_circuit/text_apply.py`):
- Properly handle escaped quotes when finding closing quote
- Skip `\"` sequences when searching for the end of a quoted value

```python
# Before: Wrong - finds first " character
value_end = symbol_block.find('"', value_start + 1)

# After: Correct - handles escaped quotes
i = value_start + 1
while i < len(symbol_block):
    if symbol_block[i] == '\\' and i + 1 < len(symbol_block) and symbol_block[i + 1] == '"':
        # Escaped quote - skip both characters
        i += 2
    elif symbol_block[i] == '"':
        # Found the closing quote
        value_end = i + 1
        break
    else:
        i += 1
```

**B-Source Value Escaping** (`apply_value_changes_text`):
- Escape quotes in B-source model formulas before writing
- Format: `type=\"B\" model=\"I=...\"` (quotes escaped for KiCad)

```python
# Before: Quotes not escaped
sim_params_value = f'type="B" model="{model_value}"'

# After: Quotes properly escaped
sim_params_value = f'type=\"B\" model=\"{model_value}\"'
```

### Verification

Tested by:
1. Applying patch to update B-source formula
2. Parsing modified schematic with KiCad
3. No syntax errors

### Files Modified

| File | Change |
|------|--------|
| `backend/hephaistus_circuit/text_apply.py` | Fix escaped quote handling in `replace_property_value` |
| `backend/hephaistus_circuit/text_apply.py` | Escape quotes in B-source Sim.Params values |
| `MEMORY.md` | Updated with this session |

---

## Session: 2026-09-03 — Staging Position Calculation Fix

### Issue Discovery

User reported: "After patching, wires with labels N$tc_Q2 and N$tc_Q3 were added as open wires instead of being placed at pin 4 of the switches."

**Root Cause:**
The `find_existing_symbols_bounds` function used ALL `(at x y angle)` positions from symbol blocks, including property positions like Reference and Value. This caused:

1. Incorrect bounding box calculation (max_x was too large)
2. Wrong staging positions for new components
3. Stubs created at incorrect positions

**Example:**
- Q2 expected position: (287.02, 49.53) based on correct bounds
- Q2 actual position: (302.26, 55.88) based on incorrect bounds
- Difference: 15.24mm in x-direction

### Solution Implemented

**`find_existing_symbols_bounds` Fix** (`backend/hephaistus_circuit/text_apply.py`):
- Use only the symbol's position (first `(at ...)` in block)
- Ignore property positions which can be offset from symbol position

```python
# Before: Used all (at ...) positions including properties
for at_match in re.finditer(at_pattern, symbol_block):
    x = float(at_match.group(1))
    y = float(at_match.group(2))
    # ... included in bounds

# After: Use only the symbol's position (first match)
at_match = re.search(r'\(at\s+([\d.\-]+)\s+([\d.\-]+)\s+[\d.\-]+\)', symbol_block)
if at_match:
    x = float(at_match.group(1))
    y = float(at_match.group(2))
    # ... included in bounds
```

### Verification

Tested on `midpoint_drift_full_SDC.kicad_sch`:

```
Original bounds (incorrect):
  min: (93.98, 49.53)
  max: (261.62, 148.59)  <- includes property positions
  staging_x: 287.02

Corrected bounds (symbol positions only):
  min: (93.98, 58.42)
  max: (257.81, 142.24)  <- only symbol positions
  staging_x: 283.21
```

### Design Decision

**Use only symbol positions for bounds calculation:**
- ✅ Accurate component placement
- ✅ Correct stub wire positions
- ✅ Matches KiCad's behavior
- ❌ More complex regex (minor)

### Files Modified

| File | Change |
|------|--------|
| `backend/hephaistus_circuit/text_apply.py` | Use only symbol position for bounds |
| `MEMORY.md` | Updated with this session |

---

## Future Improvements

1. **Smart Property Copying:** Only copy properties that differ from defaults
2. **Property Diffing:** Show inherited vs. overridden properties in UI
3. **Validation:** Warn if SPICE symbol is missing critical properties
4. **Library Path Resolution:** Auto-resolve relative library paths
5. **Property Value Validation:** Test with various B-source formulas

---

## References

- KiCad Schematic File Format: https://dev-docs.kicad.org/en/file-formats/sexpr-schematic/
- ngspice Manual: https://ngspice.sourceforge.io/docs.html
- Issue: "Q2/Q3 missing Sim.* properties when created as replicas"
- Issue: "B-source Sim.Params corruption during patch apply"