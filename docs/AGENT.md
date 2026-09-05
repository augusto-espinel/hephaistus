# Agent Orientation Guide

This document provides detailed guidance for AI agents working on the HephAIstus codebase.

## Project Philosophy

**Core principle:** Schematic is the source of truth. The circuit graph is derived from KiCad files. LLM proposes; deterministic backend disposes. Every mutation is previewable.

## Codebase Structure

```
hephaistus/
├── backend/
│   ├── hephaistus_circuit/      # KiCad parsing & patch engine
│   │   ├── parser.py            # Schematic → JSON state
│   │   ├── engine.py            # Patch-plan validation & application
│   │   ├── text_apply.py        # Text-level schematic mutations
│   │   ├── simulation_directive.py  # SPICE directive parsing
│   │   └── IMPLEMENTATION.md    # Deep implementation notes
│   ├── hephaistus_context/      # LLM context assembly
│   │   ├── context_service.py   # Layered context orchestration
│   │   ├── token_budget.py      # Token budget enforcement
│   │   └── IMPLEMENTATION.md    # Context layer details
│   ├── hephaistus_simulation/   # Simulation output parsing
│   │   ├── parser.py            # Ngspice console/waveform parsing
│   │   └── context.py           # Simulation → LLM context
│   └── hephaistus_llm/          # LLM orchestration
│       ├── orchestrator.py      # Provider abstraction, patch-plan extraction
│       └── config.py            # Model configuration
├── companion/                    # React UI (Vite + TypeScript)
├── docs/                         # Documentation
├── fixtures/                     # Test schematics
└── examples/                     # Example patch plans
```

## LLM Contract

**Input:** Structured JSON context from `context_service.py`

**Output:** Patch-plan JSON conforming to `hephaistus/patch-plan/v1`

**Key constraint:** LLM must produce valid JSON matching the schema. Hallucinated components/nets fail validation.

### Supported Operations

| Operation | Purpose |
|-----------|---------|
| `pin.assign_net` | Assign a pin to a net |
| `net.split` | Move pins to a new net |
| `component.add` | Add a new component |
| `component.update_value` | Change component value |
| `component.remove` | Remove a component |
| `simulation.set_directive` | Create/update SPICE directive |
| `simulation.remove_directive` | Remove SPICE directive |

See [`docs/patch-plan-v1.md`](patch-plan-v1.md) for the full schema.

## Validation Flow

```
Patch Plan JSON
    ↓ schema validation
Valid Operations
    ↓ semantic validation (references exist)
Validated Plan
    ↓ compute_delta()
JSON State Diff
    ↓ validate_state_integrity()
Integrity Check
    ↓ apply_delta_to_schematic()
Text-Level Apply
    ↓ parse_schematic()
Round-Trip Validation
    ↓
Result Envelope
```

## Key Implementation Patterns

### Stub-Based Net Restructuring

Series insertions (e.g., adding a shunt between R2 and C1) are expressed as:

1. **Pin re-assignment:** `R2.2: dc_plus → dc_plus_shunt`
2. **Component addition:** New component spanning both nets
3. **Stub creation:** Each re-assigned pin gets a wire + label stub

The apply flow strips all wires/junctions/labels from nets losing pins, then adds stubs.

### SPICE Property Inheritance

KiCad stores `Sim.*` properties in library symbols, not instances. When adding SPICE components:

1. Parser merges library + instance properties
2. Component creation copies `Sim.Device`, `Sim.Library`, `Sim.Name`, `Sim.Pins` to instance
3. Instance is self-contained for simulation

See `backend/hephaistus_circuit/IMPLEMENTATION.md` for details.

### Context Assembly

LLM context is assembled in layers with token budgets:

| Layer | Priority | Content |
|-------|----------|---------|
| System | Critical | Identity, schema, validation contract |
| Session | Critical | Schematic state, simulation staleness |
| History | High | Recent exchanges + summaries |
| Reasoning | Medium | Key decisions with rationale |
| Simulation | Low | DC OP, signal summaries |

See `docs/LLM_CONTEXT.md` for details.

## Common Tasks

### Adding a New Patch Operation

1. Add operation to `CANONICAL_OPS` in `engine.py`
2. Add validation in `_normalise_operation()`
3. Add state mutation in `apply_operation_to_state()`
4. Add delta computation in `compute_delta()`
5. Add text-level apply in `text_apply.py`
6. Update `patch-plan-v1.md` with schema
7. Update `system_layer.py` with operation description

### Adding a New Context Layer

1. Create `layers/<layer>_layer.py`
2. Implement `assemble()` method returning `(content, tokens)`
3. Register in `context_service.py`
4. Add token budget in `token_budget.py`
5. Update `docs/LLM_CONTEXT.md`

### Fixing a Parsing Issue

1. Identify the S-expression pattern in `.kicad_sch`
2. Update `parser.py` to extract the data
3. Add to JSON state schema
4. Ensure round-trip: parse → modify → write → parse again
5. Test with `fixtures/schematics/` examples

## Testing

### Unit Tests

```bash
# Circuit engine tests
python -m pytest tests/test_circuit_engine.py -v

# All tests
python -m pytest tests/ -v
```

### Manual Testing

See [`docs/TEST-MANUAL.md`](TEST-MANUAL.md) for comprehensive procedures.

### Test Fixtures

- `fixtures/schematics/rectifier.kicad_sch` — Basic rectifier circuit
- `fixtures/schematics/midpoint_drift_full_SDC.kicad_sch` — IGBT inverter with SPICE models
- `fixtures/simulation/` — Ngspice output samples

## Error Codes

| Code | Meaning |
|------|---------|
| `INVALID_SCHEMA` | Malformed patch plan |
| `UNSUPPORTED_OPERATION` | Unknown operation type |
| `UNKNOWN_COMPONENT` | Referenced component doesn't exist |
| `UNKNOWN_PIN` | Referenced pin doesn't exist |
| `INTEGRITY_VIOLATION` | Duplicate UUID or reference |
| `ROUND_TRIP_FAILED` | Write/re-parse validation failed |
| `APPLY_FAILED` | Text-level apply failed |

## Debugging Tips

### Patch Not Applying

1. Check `validate_patch_plan()` output
2. Examine `compute_delta()` result
3. Check round-trip parse in temporary file
4. Look for KiCad version differences

### LLM Producing Invalid JSON

1. Check system prompt in `orchestrator.py`
2. Verify token budget isn't truncating
3. Check for model-specific issues (max_tokens, reasoning)

### Parsing Errors

1. Open `.kicad_sch` in text editor
2. Find the S-expression causing issues
3. Compare with working examples in `fixtures/`
4. Check KiCad version compatibility

## Related Documents

- [`CONTEXT.md`](../CONTEXT.md) — Quick start and status
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — Technical architecture
- [`docs/patch-plan-v1.md`](patch-plan-v1.md) — Patch plan schema
- [`docs/LLM_CONTEXT.md`](LLM_CONTEXT.md) — Context assembly
- [`backend/hephaistus_circuit/IMPLEMENTATION.md`](../backend/hephaistus_circuit/IMPLEMENTATION.md) — Engine deep dive