# Context Service Implementation

This document contains implementation details for the HephAIstus context service.

## ContextService (`context_service.py`)

### Initialization

```python
class ContextService:
    def __init__(self, schematic_path: str = None, session_dir: str = None):
        self.session_state = SessionState()
        self.history_manager = HistoryManager()
        self.reasoning_trace = ReasoningTrace()
        self.token_budget = TokenBudget()
```

### Context Assembly

```python
def assemble_context(self, user_message: str, include_simulation: bool = False) -> dict:
    layers = []

    # System layer (always present)
    system = self._assemble_system_layer()
    layers.append(("system", system, self.token_budget.get_budget("system")))

    # Session layer (always present)
    session = self._assemble_session_layer()
    layers.append(("session", session, self.token_budget.get_budget("session")))

    # History layer
    history = self._assemble_history_layer()
    layers.append(("history", history, self.token_budget.get_budget("history")))

    # Reasoning layer
    reasoning = self._assemble_reasoning_layer()
    layers.append(("reasoning", reasoning, self.token_budget.get_budget("reasoning")))

    # Simulation layer (on demand)
    if include_simulation:
        simulation = self._assemble_simulation_layer()
        layers.append(("simulation", simulation, self.token_budget.get_budget("simulation")))

    return self._format_context(layers)
```

## Token Budget Management (`token_budget.py`)

### Budget Allocation

```python
DEFAULT_BUDGETS = {
    "system": 2500,
    "session": 1500,
    "history": 2000,
    "reasoning": 1000,
    "simulation": 500,
}
```

### Token Counting

```python
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken or model-specific tokenizer."""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except ImportError:
        # Fallback: estimate 4 chars per token
        return len(text) // 4
```

### Prioritization

When over budget, layers are truncated or summarized in priority order:

1. **System** — Never truncated (required)
2. **Session** — Minimal truncation (critical for context)
3. **History** — Summarize older exchanges
4. **Reasoning** — Keep most recent decisions
5. **Simulation** — Summarize waveforms, drop details

## Session State (`session_state.py`)

### Structure

```python
@dataclass
class SessionState:
    schematic_path: str = None
    schematic_hash: str = None
    schematic_summary: dict = None
    simulation_state: SimulationState = None
    user_directives: UserDirectives = None
    last_modified: datetime = None
```

### Schematic Summary

```python
def summarize_schematic(self) -> dict:
    """Generate a compact summary for context."""
    return {
        "component_count": len(self.components),
        "net_count": len(self.nets),
        "components": [
            {"ref": c.reference, "value": c.value, "lib_id": c.libId}
            for c in self.components[:20]  # Limit to first 20
        ],
        "nets": [
            {"name": n.name, "pins": n.pins[:10]}  # Limit to first 10 pins
            for n in self.nets[:20]
        ],
        "directives": self.simulation_directives,
    }
```

### Staleness Detection

```python
def is_simulation_stale(self) -> bool:
    """Check if simulation is older than schematic."""
    if not self.simulation_state or not self.simulation_state.schematic_hash:
        return True
    return self.simulation_state.schematic_hash != self.schematic_hash
```

## History Manager (`history_manager.py`)

### Storage

History is stored in SQLite with FTS5 for search:

```sql
CREATE TABLE exchanges (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE exchanges_fts USING fts5(content, content='exchanges');
```

### Windowing

```python
def get_recent_exchanges(self, max_tokens: int = 2000) -> List[dict]:
    """Get recent exchanges within token budget."""
    exchanges = []
    token_count = 0

    for row in self.db.execute("SELECT * FROM exchanges ORDER BY id DESC"):
        exchange = {"role": row["role"], "content": row["content"]}
        tokens = count_tokens(exchange["content"])
        if token_count + tokens > max_tokens:
            break
        exchanges.insert(0, exchange)
        token_count += tokens

    return exchanges
```

### Summarization

Older exchanges are summarized with a separate LLM call:

```python
def summarize_old_exchanges(self, exchanges: List[dict]) -> str:
    """Summarize older exchanges to save tokens."""
    prompt = f"Summarize the following conversation history in 200 words or less:\n\n"
    for ex in exchanges:
        prompt += f"{ex['role']}: {ex['content']}\n"

    summary = self.llm.generate(prompt, max_tokens=200)
    return summary
```

## Reasoning Trace (`reasoning_trace.py`)

### Structure

```python
@dataclass
class Decision:
    timestamp: datetime
    decision: str
    rationale: str
    confidence: float = 1.0

class ReasoningTrace:
    def __init__(self):
        self.decisions: List[Decision] = []
```

### Adding Decisions

```python
def add_decision(self, decision: str, rationale: str, confidence: float = 1.0):
    """Record a key decision."""
    self.decisions.append(Decision(
        timestamp=datetime.now(),
        decision=decision,
        rationale=rationale,
        confidence=confidence,
    ))
```

### Context Assembly

```python
def assemble(self, max_tokens: int = 1000) -> str:
    """Format decisions for context."""
    lines = ["## Key Decisions\n"]
    for d in self.decisions[-10:]:  # Keep last 10
        lines.append(f"- {d.decision}")
        if d.rationale:
            lines.append(f"  Rationale: {d.rationale}")
    return "\n".join(lines)
```

## Simulation Layer (`layers/simulation_layer.py`)

### DC Operating Points

```python
def format_dc_op(self, dc_op: dict) -> str:
    """Format DC operating points for context."""
    lines = ["## DC Operating Points\n"]
    for node, voltage in sorted(dc_op.items()):
        lines.append(f"- {node}: {voltage}")
    return "\n".join(lines)
```

### Waveform Summaries

```python
def summarize_waveform(self, signal: dict) -> str:
    """Summarize a waveform for context."""
    return f"""{signal['name']}:
  Range: [{signal['min']:.3f}, {signal['max']:.3f}]
  Mean: {signal['mean']:.3f}
  Trend: {signal['trend']}
  {f"Settling time: {signal['settling_time']}" if 'settling_time' in signal else ""}
"""
```

### Trend Detection

Trends are detected to provide context without raw data:

```python
def detect_trend(self, signal_data: List[float]) -> str:
    """Detect signal trend for context."""
    initial = signal_data[:10]
    final = signal_data[-10:]

    if abs(final[-1] - initial[0]) < 0.01 * max(abs(initial[0]), 1):
        return "stable"
    elif final[-1] > initial[0] + 0.1 * max(abs(initial[0]), 1):
        return "rising"
    elif final[-1] < initial[0] - 0.1 * max(abs(initial[0]), 1):
        return "falling"
    else:
        return "oscillating"
```

## CLI Commands

### Initialize Context

```bash
python -m hephaistus_context init /path/to/project.kicad_sch
```

### Assemble Context

```bash
python -m hephaistus_context assemble --include-simulation
```

### Debug Context

```bash
python -m hephaistus_context debug --show-tokens
```

## Related Documents

- [`docs/LLM_CONTEXT.md`](../../docs/LLM_CONTEXT.md) — Context assembly overview
- [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) — Architecture overview
- [`docs/AGENT.md`](../../docs/AGENT.md) — Agent orientation