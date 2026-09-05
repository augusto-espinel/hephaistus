# LLM Context Assembly

This document describes how HephAIstus assembles context for the LLM.

## Overview

The context service builds a token-budgeted prompt from multiple sources. The goal is to provide enough context for the LLM to reason about the circuit without overwhelming the token budget.

## Layered Context Model

Context is assembled in layers, ordered by priority:

```
┌─────────────────────────────────────┐
│ Layer 0: System (always present)   │  ~2500 tokens
├─────────────────────────────────────┤
│ Layer 1: Session State             │  ~1500 tokens
│   - Schematic summary               │
│   - Simulation staleness            │
│   - User directives                │
├─────────────────────────────────────┤
│ Layer 2: History                   │  ~2000 tokens
│   - Recent exchanges               │
│   - Summaries of older exchanges    │
├─────────────────────────────────────┤
│ Layer 3: Reasoning                 │  ~1000 tokens
│   - Key decisions                   │
│   - Rationale for past choices      │
├─────────────────────────────────────┤
│ Layer 4: Simulation                │  ~500 tokens
│   - DC operating points            │
│   - Signal summaries               │
│   - Trend detection                │
└─────────────────────────────────────┘
```

## Layer Details

### Layer 0: System Context

**Always present. Defines what HephAIstus IS and how to interact.**

```yaml
contents:
  - hephaistus_identity: "AI copilot for KiCad schematic design"
  - patch_plan_schema: "hephaistus/patch-plan/v1 operations"
  - supported_operations: [pin.assign_net, net.split, component.add, ...]
  - validation_contract: "parse + round-trip before apply"
  - error_codes: [INVALID_SCHEMA, UNKNOWN_COMPONENT, ...]
  - output_discipline: "No internal reasoning in output"
```

**Implementation:** `backend/hephaistus_context/layers/system_layer.py`

### Layer 1: Session State

**Dynamic. Refreshed on every request.**

```yaml
contents:
  - schematic_summary:
      components: 10
      nets: 5
      directives: [{type: "tran", parameters: {...}}]
      last_modified: "2026-09-05T08:00:00Z"
      hash: "abc123"
  - simulation_state:
      status: "current" | "stale"
      last_run: {...}
      staleness_warning: "Schematic modified after last simulation"
  - user_directives:
      expertise_level: "professional" | "hobbyist" | "student"
      change_aggression: "conservative" | "moderate" | "aggressive"
      explain_steps: true | false
```

**Implementation:** `backend/hephaistus_context/layers/session_layer.py`

### Layer 2: History

**Windowed. Recent exchanges in full, older exchanges summarized.**

```yaml
contents:
  - recent_exchanges: [{role: "user", content: "..."}, {role: "assistant", content: "..."}]
  - older_summaries: ["User asked about R1 value. Assistant explained...", ...]
```

**Token management:**
- Keep last N exchanges in full (N configurable)
- Summarize older exchanges with a separate LLM call
- Prune when approaching budget

**Implementation:** `backend/hephaistus_context/layers/history_layer.py`

### Layer 3: Reasoning

**Condensed. Key decisions from past interactions.**

```yaml
contents:
  - decisions:
      - "Added R3 between R2.2 and C1.1 to create dc_plus_shunt net"
      - "Chose Device:R over Device:R_US for standard resistor symbol"
  - rationale:
      - "Shunt placement chosen to minimize trace length"
```

**Implementation:** `backend/hephaistus_context/layers/reasoning_layer.py`

### Layer 4: Simulation

**On-demand. Loaded when simulation context is relevant.**

```yaml
contents:
  - dc_operating_points:
      V_out: 12.34
      I_R1: 1.23m
  - signal_summaries:
      - name: "V(out)"
        min: 0.0, max: 12.0, mean: 6.0
        trend: "settling"
        settling_time: "1.2ms"
  - convergence:
      status: "converged"
      warnings: []
```

**Token efficiency:**
- Waveforms summarized, not raw
- Key points: final N, initial N, peaks, crossings
- LLM can request full data on demand

**Implementation:** `backend/hephaistus_context/layers/simulation_layer.py`

## Token Budget

Each layer has a token budget enforced by `token_budget.py`:

```python
LAYER_BUDGETS = {
    "system": 2500,
    "session": 1500,
    "history": 2000,
    "reasoning": 1000,
    "simulation": 500,
}
MAX_TOTAL_TOKENS = 8000  # Adjust based on model context window
```

**Enforcement:**
1. Assemble each layer
2. Count tokens (using tiktoken or model-specific tokenizer)
3. Truncate or summarize if over budget
4. Prioritize: system > session > history > reasoning > simulation

## Context Service API

```python
from hephaistus_context import ContextService

# Initialize with schematic
service = ContextService(schematic_path="project.kicad_sch")

# Assemble context for LLM
context = service.assemble_context(
    user_message="Add a 1mΩ shunt between C1 and R2",
    include_simulation=True,
    max_tokens=8000,
)

# context = {
#     "system": "...",
#     "session": "...",
#     "history": "...",
#     "reasoning": "...",
#     "simulation": "...",
#     "token_count": 6500,
# }
```

## SPICE Library Context

When components have SPICE models, the context includes library content:

```yaml
spice_libraries:
  - name: "FUJI_2MBI1500XYF170.lib"
    models: ["2MBI1500XYF170"]
    tokens: 200
    content: |
      * IGBT with antiparallel diode
      .SUBCKT 2MBI1500XYF170 C G E Tc
      ...
      .ENDS
```

**Token management:**
- Strip comments (lines starting with `*`)
- Include complete `.SUBCKT` and `.MODEL` definitions
- Code is circuit — LLM needs full visibility

## Session Persistence

Sessions are stored in the project directory:

```
<project>/.hephaistus/
├── session.json      # Current state
├── history.db        # Conversation history (SQLite/FTS5)
└── simulations/
    ├── current/      # Active simulation
    └── history/      # FIFO archive (last 5 runs)
```

**Staleness detection:**
- Compare schematic hash to simulation hash
- Warn in context if simulation is stale

## Implementation Files

| File | Purpose |
|------|---------|
| `context_service.py` | Orchestration, layer assembly |
| `token_budget.py` | Budget enforcement, prioritization |
| `session_state.py` | Schematic, simulation, directives |
| `history_manager.py` | Windowed history, summarization |
| `reasoning_trace.py` | Decision audit trail |
| `layers/system_layer.py` | Identity, schema, error codes |
| `layers/session_layer.py` | Schematic state, staleness |
| `layers/history_layer.py` | Recent exchanges, summaries |
| `layers/reasoning_layer.py` | Key decisions |
| `layers/simulation_layer.py` | DC OP, waveforms |

## Related Documents

- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — Architecture overview
- [`backend/hephaistus_context/IMPLEMENTATION.md`](../backend/hephaistus_context/IMPLEMENTATION.md) — Implementation details
- [`docs/AGENT.md`](AGENT.md) — Agent orientation