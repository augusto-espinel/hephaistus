# Phase 3: Context Management & Companion UI

## Executive Summary

Phase 3 implements the **Context Management** and **Companion UI** for HephAIstus. This is the critical layer that bridges between the deterministic backend and the LLM, ensuring engineers can verify and understand AI decisions before accepting changes.

The key insight: Context is **not flat**. It's layered, tiered, and auditable. Engineers need a structured engineering notebook, not a chat transcript.

---

## Core Architecture: Layered Context Model

### Layer 0: System Context (Static)

**Always present. Defines what HephAIstus IS and how to interact with it.**

```yaml
context_layers:
  layer_0_system:
    contents:
      - hephaistus_identity: "AI copilot for KiCad schematic design"
      - patch_plan_schema: "hephaistus/patch-plan/v1 operations"
      - supported_directives: ["tran", "ac", "dc", "op", "options"]
      - validation_contract: "parse + round-trip before apply"
      - error_codes: [INVALID_SCHEMA, UNSUPPORTED_OPERATION, ...]
    token_budget: ~2000
    priority: critical
```

Generated once at session start. The "rules of engagement."

---

### Layer 1: Session State (Dynamic, Fresh)

**The current world state. Always reflects the latest schematic and simulation.**

```yaml
  layer_1_session_state:
    contents:
      - schematic_summary:
          components: 10
          nets: 5
          directives: [{type: "tran", parameters: {...}}]
          last_modified: "2026-08-20T18:30:00Z"
          hash: "abc123"
      - simulation_state:
          status: "stale" | "current"
          last_run: {...}
          staleness_warning: "Schematic modified after last simulation"
      - user_directives:
          expertise_level: "professional" | "hobbyist" | "student"
          change_aggression: "conservative" | "moderate" | "aggressive"
          explain_steps: true | false
          target_metrics: ["efficiency", "cost", "size"]
    token_budget: ~1500
    priority: critical
    refresh: "on_every_request"
```

**Key innovation:** Staleness detection tells the LLM if results are trustworthy.

---

### Layer 2: Conversation History (Windowed)

**Configurable window of exchanges. Preserves the "why" behind decisions.**

```yaml
  layer_2_history:
    contents:
      - exchanges: [...]
      - window_size: configurable (default: 10)
      - reset_on: ["new_project", "user_request"]
    token_budget: ~4000
    priority: high
    degradation: "summarize_older_exchanges"
```

Each exchange includes:

```json
{
  "user_request": "Add a snubber to the flyback converter",
  "llm_reasoning_summary": "User wants protection across inductor. Proposing RC snubber.",
  "patch_plan": {...},
  "validation_result": "passed",
  "user_action": "accepted"
}
```

---

### Layer 3: Reasoning Trace (Condensed)

**Key decisions preserved, not full chain-of-thought.**

```yaml
  layer_3_reasoning:
    contents:
      - decision_points:
          - step: 1
            decision: "Use shunt resistor for current sensing"
            rationale: "Non-intrusive, low cost, adequate bandwidth"
            alternatives_rejected: ["hall effect", "transformer"]
          - step: 5
            decision: "Place snubber across diode"
            rationale: "User constraint: no series insertion"
    token_budget: ~1000
    priority: medium
    refresh: "on_new_decision"
```

When something goes wrong, engineers can trace back to WHY.

---

### Layer 4: Simulation Results (On-Demand)

**Summaries always, full data on request.**

```yaml
  layer_4_simulation:
    contents:
      - summary:
          analysis_type: "transient"
          converged: true
          key_signals:
            - name: "V(out)"
              final: "12.0V"
              overshoot: "8%"
              settling_time: "2.3ms"
            - name: "I(L1)"
              peak: "1.2A"
          warnings: []
      - full_data:
          available: true
          access: "on_request"
          token_budget: ~8000 (only when requested)
    token_budget: ~500 (summary only by default)
    priority: medium
```

---

### Layer 5: Deep History (Reference)

**Searchable archive. Not in context unless explicitly requested.**

```yaml
  layer_5_deep_history:
    storage: "sqlite or jsonl"
    access: "search_by_keyword_or_time"
    use_cases:
      - "What did we try last week?"
      - "Why did we abandon the flyback topology?"
      - "Show all changes to the output filter"
```

---

## User Directives: Tuning the Behavior

### Expertise Level

| Level | Behavior |
|-------|----------|
| **Student** | Explain each step. Suggest alternatives. Ask before applying. Show reasoning. |
| **Hobbyist** | Balance explanation and action. Moderate caution. |
| **Professional** | Propose complete solutions. Minimal explanation. Trust validation. |

### Change Aggression

| Level | Behavior |
|-------|----------|
| **Conservative** | One change at a time. Wait for user acceptance. Explain risks. |
| **Moderate** | Propose related changes together. Still ask before applying. |
| **Aggressive** | Propose complete solutions. Batch related changes. Trust user to reject. |

### Learning Mode

```json
{
  "explain_steps": true,
  "show_alternatives": true,
  "verbose_reasoning": true,
  "pause_before_apply": true
}
```

---

## Context Assembly Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    User Request Arrives                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. REFRESH SESSION STATE                                    │
│     - Reload schematic summary                               │
│     - Check simulation staleness                            │
│     - Verify user directives                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. ASSEMBLE CONTEXT LAYERS                                   │
│     Layer 0: System (always)                                │
│     Layer 1: Session State (refreshed)                      │
│     Layer 2: History (windowed)                             │
│     Layer 3: Reasoning (condensed)                         │
│     Layer 4: Simulation (summary)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. INJECT INTO LLM PROMPT                                   │
│     - Structured sections                                    │
│     - Token budget enforcement                              │
│     - Priority-based truncation                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. RECEIVE LLM RESPONSE                                     │
│     - Parse patch-plan or question                          │
│     - Validate against schema                              │
│     - Run round-trip check                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. UPDATE SESSION STATE                                      │
│     - Record decision point                                 │
│     - Update history                                        │
│     - Mark simulation as stale (if changes pending)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. PRESENT TO USER                                           │
│     - Show proposed changes                                  │
│     - Highlight affected components/nets                   │
│     - Offer inspect/apply/reject                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Companion UI Architecture

### Technology Stack

- **Cross-Platform Desktop:** Tauri (Rust + WebView)
- **Frontend:** React + TypeScript
- **Component Library:** Radix UI
- **Backend:** Python (existing HephAIstus modules)

### Key Features

#### 1. Context Inspector (Debug Mode)

Click "Inspect" on any LLM response to see:

```json
{
  "context_assembled": {
    "layer_0_system": { "tokens": 1847, "truncated": false },
    "layer_1_session": { "tokens": 1203, "stale_simulation": true },
    "layer_2_history": { "tokens": 3521, "exchanges": 8 },
    "layer_3_reasoning": { "tokens": 892, "decisions": 3 },
    "layer_4_simulation": { "tokens": 487, "summary_only": true }
  },
  "total_tokens": 7950,
  "model": "claude-3-5-sonnet",
  "validation_result": "passed",
  "round_trip": { "parse_ok": true, "erc_exit": null }
}
```

#### 2. Patch-Plan Diff View

Before accepting, see exactly what will change:

```
┌─────────────────────────────────────────────────┐
│  Proposed Changes                                │
├─────────────────────────────────────────────────┤
│  Components:                                     │
│    + R_snub (Device:R) [100Ω]                   │
│    + C_snub (Device:C) [100nF]                  │
│                                                  │
│  Nets:                                           │
│    R_snub.1 → anode                              │
│    R_snub.2 → C_snub.1                          │
│    C_snub.2 → cathode                            │
│                                                  │
│  Simulation:                                     │
│    .tran 1u 10m (unchanged)                      │
│                                                  │
│  Affected: D1, R_snub, C_snub, anode, cathode   │
│                                                  │
│  [Show full JSON] [Show schematic preview]      │
│                                                  │
│  [Apply] [Reject] [Modify]                      │
└─────────────────────────────────────────────────┘
```

#### 3. History Browser

Navigate past decisions, search by keyword, filter by date.

---

## Implementation Roadmap

- **Phase 3.1:** ContextService (layered assembly, token management)
- **Phase 3.2:** SessionManager (state persistence, debugging)
- **Phase 3.3:** HistoryStore (SQLite, search)
- **Phase 3.4:** LLM Orchestration (patch planning, validation)
- **Phase 3.5:** Companion UI (Tauri + React)
- **Phase 3.6:** Integration Testing (end-to-end)

---

## Design Principles

1. **Auditability** — Every decision is traceable
2. **Transparency** — Users see what the AI is doing
3. **Efficiency** — Token budgets enforced
4. **Flexibility** — User expertise level drives behavior
5. **Recoverability** — History preserves decisions

This architecture is designed to empower engineers, not replace them.