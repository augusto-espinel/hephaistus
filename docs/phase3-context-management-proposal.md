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

## LLM Provider Architecture

### Provider Interface

The LLM abstraction supports multiple backends through a unified interface:

```python
class LLMProvider(Protocol):
    name: str
    
    def complete(self, prompt: str, config: LLMConfig) -> LLMResponse: ...
    def stream(self, prompt: str, config: LLMConfig) -> AsyncIterator[str]: ...
    def count_tokens(self, text: str) -> int: ...
    def models(self) -> list[ModelInfo]: ...
```

### Supported Providers

| Provider | Use Case | Configuration |
|----------|----------|---------------|
| **OpenRouter** | Cloud models (Claude, GPT, Gemini) | API key, model selection |
| **Ollama** | Local inference, privacy-sensitive | Base URL (localhost or remote) |
| **OpenAI** | Direct OpenAI API | API key, organization |

### Configuration Schema

```json
{
  "hephaistus.llm.provider": "openrouter" | "ollama" | "openai",
  "hephaistus.llm.model": "claude-3.5-sonnet" | "llama3.1:70b",
  "hephaistus.llm.openrouter.apiKey": "${OPENROUTER_API_KEY}",
  "hephaistus.llm.ollama.baseUrl": "http://localhost:11434",
  "hephaistus.llm.temperature": 0.7,
  "hephaistus.llm.maxTokens": 4096
}
```

### Module Structure

```
backend/hephaistus_llm/
├── __init__.py
├── base.py           # Protocol + data classes
├── config.py         # LLMConfig, ProviderConfig
├── providers/
│   ├── __init__.py
│   ├── openrouter.py # OpenRouter API client
│   ├── ollama.py    # Ollama client (local/remote)
│   └── openai.py     # OpenAI direct API
└── orchestrator.py   # ContextService → Provider wiring
```

---

## Implementation Roadmap

- **Phase 3.1:** ContextService (layered assembly, token management) ✅ **DONE**
- **Phase 3.2:** SessionManager (state persistence, debugging) ✅ **DONE**
- **Phase 3.3:** HistoryStore (SQLite, search)
- **Phase 3.4:** LLM Orchestration
  - **3.4.1:** Provider interface (`hephaistus_llm/base.py`)
  - **3.4.2:** OpenRouter provider
  - **3.4.3:** Ollama provider (local + remote)
  - **3.4.4:** Orchestrator (ContextService → LLM)
  - **3.4.5:** Response parsing + validation
- **Phase 3.5:** Companion UI (Tauri + React)
- **Phase 3.6:** Integration Testing (end-to-end)

---

---

## Simulation Data Ingestion (Phase 3.7)

### Overview

KiCad's Eeschema/ngspice integration runs simulations **in-memory** and does NOT write results to disk. This requires an explicit ingestion workflow where the user provides simulation data to HephAIstus.

### User Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  KiCad Simulator                                                │
│  ┌──────────────┐                                               │
│  │ Run Simulation│──► Console Output ──► User copies           │
│  └──────────────┘                                               │
│  ┌──────────────┐                                               │
│  │ File►Export  │──► <project>/<schematic>-<analysis>.csv      │
│  │ Plot as CSV  │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
                              │                      │
                              ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  HephAIstus Companion                                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [Load Simulation] Button                                │   │
│  │                                                          │   │
│  │ CSV File: [Browse...] <schematic>-<analysis>.csv        │   │
│  │            (user selects from .hephaistus/simulations/) │   │
│  │                                                          │   │
│  │ Console Output:                                          │   │
│  │ ┌──────────────────────────────────────────────────────┐ │   │
│  │ │ [Paste ngspice console output here]                  │ │   │
│  │ │                                                       │ │   │
│  │ │ - DC operating point results                          │ │   │
│  │ │ - Convergence status                                  │ │   │
│  │ │ - Warnings and errors                                 │ │   │
│  │ └──────────────────────────────────────────────────────┘ │   │
│  │                                                          │   │
│  │ [Import] [Cancel]                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Either field can be empty:                                    │
│  - DC op analysis: console only                                │
│  - Transient/AC: both CSV and console                          │
│  - Successful transient: console less valuable                 │
└─────────────────────────────────────────────────────────────────┘
```

### Storage Structure

```
<project>/.hephaistus/
├── session.json              # Current session state
├── history.db                 # Conversation history
└── simulations/
    ├── current/               # Active simulation (moved here on ingest)
    │   ├── run_metadata.json
    │   ├── console.txt
    │   └── waveform.csv
    └── history/               # FIFO archive (last 5 runs)
        ├── 2026-08-21T22-00-00/
        │   ├── run_metadata.json
        │   ├── console.txt
        │   └── waveform.csv
        ├── 2026-08-21T20-30-00/
        │   └── ...
        └── (max 5 folders)
```

### Freshness Strategy

**On Every Prompt:**
1. Compare current schematic hash to simulation's schematic hash
2. If match → simulation is "current" (include in context)
3. If mismatch → simulation is "stale" (warn in context)
4. Archive current simulation to history before replacing

**FIFO Archive:**
- Keep last 5 simulation runs in `simulations/history/`
- Delete oldest when limit exceeded
- Timestamp-based folder naming for traceability

### Context Size Management

#### Waveform CSV (Transient Analysis)

For large CSV files (>10,000 rows), provide **summary only**:

```yaml
waveform_summary:
  analysis_type: "transient"
  duration: "10ms"
  step: "1μs"
  total_samples: 10000
  signals:
    - name: "V(dc_plus)"
      min: 380.2
      max: 420.5
      mean: 400.1
      std: 12.3
      initial: 0.0
      final: 400.0
      trend: "settling"
      settling_time: "2.3ms"
      overshoot: "5.1%"
    - name: "I(L1)"
      peak: "1.2A"
      trend: "oscillating"
      frequency: "50kHz"
  note: "Full waveform has 10,000 samples. Summary provided."
  hint: "To reduce sampling: increase .tran step or use .options interp"
```

**LLM can request full data:**
- "Show full V(dc_plus) data" → include all samples for that signal
- "Show last 1000 samples" → include final N rows

#### Console Output (All Analysis Types)

Always included in context (usually compact):

```yaml
console_summary:
  analysis: ".tran 1u 10m"
  convergence: "converged"
  operating_points:
    - node: "dc_plus" value: "400.0V"
    - node: "dc_minus" value: "0.0V"
  warnings:
    - "timestep too small at t=1ns"
  errors: []
```

**Why Console Matters:**
- Convergence failures → diagnostic hints
- Operating points → DC bias validation
- Warnings → transient quality issues
- Errors → topology or model problems

### Module Structure

```
backend/hephaistus_simulation/
├── __init__.py
├── parser.py           # ngspice output parsing (EXISTS)
├── run_metadata.py     # simulation tracking (EXISTS)
├── context.py          # LLM context assembly (EXISTS)
├── waveform.py         # signal analysis (EXISTS)
├── cli.py              # CLI commands (EXISTS)
├── ingestion.py        # NEW: file ingestion + validation
└── archiver.py          # NEW: FIFO history management
```

### API Endpoints

```yaml
POST /api/simulation/import:
  request:
    csv_path: "<project>/.hephaistus/simulations/<file>.csv"
    console_text: "Circuit: ...\nDoing analysis..."
  response:
    status: "imported"
    analysis_type: "transient"
    signals: 5
    convergence: "converged"
    warnings: []

GET /api/simulation/history:
  response:
    runs:
      - timestamp: "2026-08-21T22:00:00Z"
        analysis: "tran"
        status: "stale"
        schematic_hash: "abc123"
      - ...

DELETE /api/simulation/clear:
  response:
    status: "cleared"
```

### UI Component: ImportSimulationDialog

```tsx
// companion/src/components/ImportSimulationDialog.tsx
interface ImportSimulationProps {
  onImport: (data: SimulationData) => void;
}

// Two-mode dialog:
// 1. CSV only (transient/AC waveforms)
// 2. Console only (DC operating point)
// 3. Both (full context)

// CSV browser starts in <project>/.hephaistus/simulations/
// Console textbox accepts paste from KiCad simulator console
```

### Implementation Checklist

**Simulation Ingestion:**
- [ ] `ingestion.py`: CSV parser + console parser integration
- [ ] `archiver.py`: FIFO history management (max 5 runs)
- [ ] `POST /api/simulation/import`: Ingestion endpoint
- [ ] `DELETE /api/simulation/clear`: Clear current simulation
- [ ] SessionState: Add `simulation_hash` for freshness tracking
- [ ] SimulationLayer: Include summary + staleness warning
- [ ] Frontend: ImportSimulationDialog component
- [ ] Frontend: SimulationStatus indicator (current/stale)

**SPICE Library Context:**
- [ ] Parser: Extract `Sim.Library` properties from schematic
- [ ] Context: Include `.lib` file contents in session layer
- [ ] Path resolution: Find `.lib` files in project folder
- [ ] Token management: Summarize large model files

### SPICE Library Context

**Problem:** Schematics reference SPICE models via `.lib` files (e.g., `FUJI_2MBI1500XYF170.lib`). The LLM needs access to model parameters to understand component behavior and troubleshoot simulation issues.

**Discovery:**
```kicad_sch
(property "Sim.Library" "FUJI_2MBI1500XYF170.lib"
 (at 0 0 0)
 (unlocked yes)
 (effects (font (size 1.27 1.27)))
)
```

**Implementation:**

1. **Parse schematic for library references:**
   - Extract all `Sim.Library` properties
   - Collect unique `.lib` filenames

2. **Resolve library paths:**
   - Check `<project>/<libname>.lib`
   - Check `<project>/models/<libname>.lib`
   - Fallback to KiCad global library paths

3. **Include in session context:**
   ```yaml
   spice_libraries:
     - name: "FUJI_2MBI1500XYF170.lib"
       models:
         - "2MBI1500XYF170" (subcircuit, IGBT + diode)
       tokens: ~200
       summary: "IGBT module with freewheeling diode"
   ```

4. **Token management:**

   SPICE libraries are **complete circuit definitions** - the LLM needs full visibility to understand:
   - Topology (e.g., diode is antiparallel to IGBT)
   - Pin assignments (which pin connects to cathode/anode)
   - Model parameters (threshold, capacitances, breakdown voltages)
   - Subcircuit structure (internal components like gate resistor)

   **Include complete library content:**
   - Strip comments (lines starting with `*`) to save tokens and avoid hallucinations
   - Keep all `.MODEL`, `.SUBCKT`, and component lines
   - Small files (<5KB): include verbatim
   - Large files (>5KB): still include complete, just be aware of token cost

**Example Context (after stripping comments):**
```
## SPICE Models

### FUJI_2MBI1500XYF170.lib
.SUBCKT 2MBI1500XYF170 C G E
Rg G G_int 0.67
M1 C G_int E E NMOS_MODEL 
Cge G_int E 184.65n
Cgc G_int C 0.35n
Cce C E 11.15n
D1 E C FWD_MODEL
.MODEL NMOS_MODEL NMOS(VTO=6.5 KP=100)
.MODEL FWD_MODEL D(BV=1700 IS=1E-9 N=1.5 RS=0.0004)
.ENDS 2MBI1500XYF170
```

The LLM can now reason:
- "The diode D1 is between E and C (antiparallel to the IGBT)"
- "Gate resistor Rg = 0.67Ω is internal to the module"
- "Capacitances Cge, Cgc, Cce define switching behavior"
- "Pin C is Collector, G is Gate, E is Emitter"

### Future Enhancements

| Phase | Feature | Description |
|-------|---------|-------------|
| Short | KiCad Plugin | Auto-export simulation results on completion |
| Medium | Agentic Simulation | HephAIstus runs ngspice directly for optimization |
| Long | KiCad IPC | Direct integration as docked panel |
| Long | Multi-simulator | Support PSpice, LTspice, other engines |

---

## Design Principles

1. **Auditability** — Every decision is traceable
2. **Transparency** — Users see what the AI is doing
3. **Efficiency** — Token budgets enforced
4. **Flexibility** — User expertise level drives behavior
5. **Recoverability** — History preserves decisions

This architecture is designed to empower engineers, not replace them.