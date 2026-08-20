# HephAIstus Simulation Module

Simulation output parsing and context assembly for the HephAIstus companion.

## Overview

This module parses ngspice simulation output and assembles LLM-friendly context from schematic state and simulation results.

## Components

### parser.py

Parses ngspice output formats:

- **Console output** — stdout/stderr with analysis types, convergence status, warnings, errors
- **DC operating points** — node voltages and branch currents from `.op` analysis
- **Raw waveform data** — ngspice `.raw` files with time-domain signal data

### run_metadata.py

Tracks simulation runs with:

- Run ID and timestamp
- Schematic path and hash (for correlation)
- Analysis type and parameters
- Convergence status and errors
- File references (console, raw, op files)

### context.py

Assembles LLM context from:

- Schematic state (components, nets)
- Simulation run (console, op points, waveforms)
- Correlation status (freshness detection)

### cli.py

Command-line interface:

```bash
# Parse console output
hephaistus-simulation parse-console output.txt

# Parse DC operating points
hephaistus-simulation parse-op op_output.txt

# Parse raw waveform
hephaistus-simulation parse-raw transient.raw

# Create run metadata
hephaistus-simulation create-run schematic.kicad_sch \
  --analysis tran \
  --param stop=10m \
  --param step=1u \
  --console output.txt \
  --raw transient.raw

# Check correlation
hephaistus-simulation check-correlation run.json schematic.kicad_sch

# Assemble LLM context
hephaistus-simulation context schematic.kicad_sch \
  --run run.json \
  --format text
```

## Usage Examples

### Parse Console Output

```python
from hephaistus_simulation import parse_console_output

with open("ngspice_output.txt") as f:
    output = f.read()

parsed = parse_console_output(output)
# parsed.analyses: [{type: "tran", status: "completed"}]
# parsed.convergence: ConvergenceInfo(converged=True)
# parsed.warnings: [...]
# parsed.errors: [...]
```

### Parse DC Operating Points

```python
from hephaistus_simulation import parse_dc_op_points

with open("op_output.txt") as f:
    output = f.read()

points = parse_dc_op_points(output)
# [{name: "v(out)", value: 5.0, unit: "V"}, ...]
```

### Assemble Context

```python
from hephaistus_simulation import assemble_context, create_run_metadata
from hephaistus_circuit import parse_schematic
from pathlib import Path

# Parse schematic
schematic_state = parse_schematic(Path("rectifier.kicad_sch"))

# Create run metadata
run = create_run_metadata(
    schematic_path=Path("rectifier.kicad_sch"),
    analysis_type="tran",
    parameters={"stop": "10m", "step": "1u"},
    console_output_path=Path("ngspice_output.txt"),
)

# Assemble context
context = assemble_context(
    schematic_path=Path("rectifier.kicad_sch"),
    schematic_state=schematic_state,
    run=run,
)

# Get LLM-friendly text
print(context.get_llm_context())
```

## Waveform Processing

The module includes waveform post-processing to minimize token usage while preserving essential information:

### WaveformConfig

Control how waveforms are summarized:

```python
from hephaistus_simulation import WaveformConfig

config = WaveformConfig(
    max_raw_points=100,  # Max points if raw included
    max_signals=10,  # Max signals in context
    include_stats=True,  # min, max, mean, std, final
    include_trend=True,  # settling, oscillating, rising
    include_final_n=50,  # Last N points
    include_initial_n=20,  # First N points
    include_peaks=True,  # Local maxima/minima
    include_crossings=True,  # Zero crossings
)
```

### Summary Statistics

```python
from hephaistus_simulation import summarize_waveform

summary = summarize_waveform('v(out)', time, values, config)
# summary.trend: 'settling', 'oscillating', 'rising', 'falling', 'stable'
# summary.settling_time: time to reach <1% variation
# summary.overshoot: percentage overshoot from final
# summary.peaks: list of (t, v) tuples for peaks
```

### Context Efficiency

The LLM context includes guidance for efficient simulation setup:

- DC operating points are always included (compact, useful)
- Transient waveforms are summarized, not raw
- For settling analysis: use larger steps (stop/100)
- For steady-state: focus on final period
- Post-processing available: final_value, settling_time, overshoot, peaks

## Integration with HephAIstus

The simulation module provides context for LLM orchestration:

1. **Schematic state** — from `hephaistus_circuit.parse_schematic()`
2. **Simulation results** — from ngspice output parsing
3. **Correlation** — detect if simulation matches current schematic
4. **Context assembly** — combine into LLM-friendly summary

This enables the LLM to:
- Answer questions about circuit behavior
- Diagnose convergence failures
- Compare simulation runs
- Propose schematic changes based on simulation results

## Test Fixtures

Sample files in `fixtures/simulation/`:

- `transient_console.txt` — ngspice console output with convergence error
- `dc_op_output.txt` — DC operating points
- `transient.raw` — Raw waveform data

## Next Steps

- Phase 2: Simulation parameter management (patch-plan extension)
- Phase 3: Companion UI + LLM orchestration