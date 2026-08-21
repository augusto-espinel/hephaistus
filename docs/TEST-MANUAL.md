# HephAIstus Manual Test Procedures

Version: 1.0
Date: 2026-08-21

## Prerequisites

- Python 3.9+ with virtual environment
- Ollama running locally (for local LLM tests)
- OpenRouter API key configured in `.env`
- KiCad installed (for schematic validation)

## Environment Setup

```bash
cd /path/to/hephaistus
source .venv/bin/activate
pip install -e .
pip install python-dotenv  # If not already installed
```

Create `.env` file in project root:

```
OPENROUTER_API_KEY=sk-or-v1-...
```

Start the API server:

```bash
uvicorn api.server:app --host 127.0.0.1 --port 8000
```

---

## Test 1: Health Check

**Purpose:** Verify server is running.

```bash
curl -s http://localhost:8000/ | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "ok",
  "service": "hephaistus-companion-api"
}
```

---

## Test 2: Session Status (Empty)

**Purpose:** Verify empty session state on fresh server.

```bash
curl -s http://localhost:8000/api/session/status | python3 -m json.tool
```

**Expected:**
```json
{
  "has_session": false,
  "session_id": "...",
  "project_root": null,
  "schematic": {
    "path": null,
    "relative_path": null,
    "hash": null,
    "component_count": 0,
    "net_count": 0
  },
  "simulation": {
    "status": "none",
    "last_run": null
  },
  "last_updated": "..."
}
```

---

## Test 3: Load Schematic

**Purpose:** Load a KiCad schematic and verify session persistence.

```bash
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/hephaistus/fixtures/schematics/rectifier.kicad_sch" | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "loaded",
  "path": "/path/to/hephaistus/fixtures/schematics/rectifier.kicad_sch",
  "project_root": "/path/to/hephaistus/fixtures/schematics",
  "relative_path": "rectifier.kicad_sch",
  "components": 10,
  "nets": 5,
  "session_file": "/path/to/hephaistus/fixtures/schematics/.hephaistus/session.json"
}
```

**Verify:**
- `project_root` is discovered correctly
- `.hephaistus/` directory created
- `session.json` file exists

```bash
ls -la fixtures/schematics/.hephaistus/
cat fixtures/schematics/.hephaistus/session.json | python3 -m json.tool
```

---

## Test 4: Session Status (Loaded)

**Purpose:** Verify session state reflects loaded schematic.

```bash
curl -s http://localhost:8000/api/session/status | python3 -m json.tool
```

**Expected:**
```json
{
  "has_session": true,
  "session_id": "...",
  "project_root": "/path/to/hephaistus/fixtures/schematics",
  "schematic": {
    "path": "/path/to/hephaistus/fixtures/schematics/rectifier.kicad_sch",
    "relative_path": "rectifier.kicad_sch",
    "hash": "8ddd5b109eb9f3eb",
    "component_count": 10,
    "net_count": 5
  },
  ...
}
```

---

## Test 5: Schematic State Endpoint

**Purpose:** Verify schematic state endpoint returns component/net details.

```bash
curl -s http://localhost:8000/api/schematic/state | python3 -m json.tool
```

**Expected:**
```json
{
  "path": "/path/to/hephaistus/fixtures/schematics/rectifier.kicad_sch",
  "hash": "8ddd5b109eb9f3eb",
  "component_count": 10,
  "net_count": 5,
  "components": [...],
  "nets": [...],
  "directives": [...],
  "last_modified": "...",
  "has_unsaved_changes": false
}
```

---

## Test 6: LLM Query (Ollama - Local)

**Purpose:** Verify LLM can answer questions about loaded schematic.

```bash
curl -s -X POST http://localhost:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "What components are in this schematic? List them.",
    "provider": "ollama",
    "model": "gemma4:e4b"
  }' | python3 -m json.tool
```

**Expected:** Response lists components from the schematic (C1, C2, D1-D4, R1, R2, V1).

**Example response:**
```json
{
  "raw_response": "Based on the current session state... The component references are:\n* Capacitors (C): C1, C2\n* Resistors (R): R1, R2\n* Diodes (D): D1, D2, D3, D4\n* Voltage Sources (V): V1...",
  "is_clarification": false,
  ...
}
```

---

## Test 7: LLM Query (OpenRouter - Cloud)

**Purpose:** Verify OpenRouter provider works with API key.

```bash
curl -s -X POST http://localhost:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Add a snubber circuit across D1",
    "provider": "openrouter",
    "model": "deepseek/deepseek-v4-pro-0813"
  }' | python3 -m json.tool
```

**Expected:** Response references loaded schematic components.

---

## Test 8: Clarification Flow

**Purpose:** Verify LLM asks clarifying questions when context is insufficient.

```bash
curl -s -X POST http://localhost:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Optimize the circuit for efficiency",
    "provider": "ollama",
    "model": "gemma4:e4b"
  }' | python3 -m json.tool
```

**Expected:** Response asks clarifying questions about optimization goals, constraints, or circuit behavior.

---

## Test 9: Session Persistence Across Restart

**Purpose:** Verify session survives server restart.

**Steps:**

1. Load schematic (Test 3)
2. Verify session file exists
3. Stop server: `pkill -f "uvicorn api.server:app"`
4. Start server again
5. Check session status (should be empty)
6. Call restore endpoint:

```bash
curl -s -X POST http://localhost:8000/api/session/restore | python3 -m json.tool
```

**Expected:** Session restored from `.hephaistus/session.json`.

---

## Test 10: Context Assembly

**Purpose:** Verify context assembly for debugging.

```bash
curl -s -X POST http://localhost:8000/api/context/assemble \
  -H "Content-Type: application/json" \
  -d '{
    "request": "What is the power supply voltage?"
  }' | python3 -m json.tool
```

**Expected:** Response includes assembled context with token breakdown.

---

## Test 11: History Search

**Purpose:** Verify conversation history is persisted.

```bash
# After some LLM interactions
curl -s "http://localhost:8000/api/history/search?q=component&limit=5" | python3 -m json.tool
```

**Expected:** Array of matching history entries.

---

## Test 12: Multiple Projects

**Purpose:** Verify different projects have separate sessions.

**Steps:**

1. Load schematic from project A
2. Verify `.hephaistus/` in project A
3. Load schematic from project B (different path)
4. Verify `.hephaistus/` in project B
5. Check session status shows project B

**Expected:** Each project has its own `.hephaistus/` directory and session.

---

## Test 13: Project Root Discovery

**Purpose:** Verify project root discovery from schematic path.

```bash
# Test with schematic in subdirectory
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/project/subdir/schematic.kicad_sch" | python3 -m json.tool
```

**Expected:** `project_root` is the directory containing `.kicad_pro` or parent of schematic.

---

## Test 14: SPICE Library Loading

**Purpose:** Verify SPICE libraries are loaded and included in context.

**Prerequisites:**
- Schematic with `Sim.Library` properties (e.g., `rectifier.kicad_sch` with IGBT)
- `.lib` files in project directory

**Steps:**

1. Load schematic with SPICE library references:

```bash
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/hephaistus/fixtures/schematics/rectifier.kicad_sch" | python3 -m json.tool
```

2. Check session status for SPICE libraries:

```bash
curl -s http://localhost:8000/api/session/status | python3 -m json.tool
```

**Expected:**
```json
{
  "has_session": true,
  "spice_libraries": [
    {
      "name": "FUJI_2MBI1500XYF170.lib",
      "models": ["NMOS_MODEL", "FWD_MODEL"],
      "subcircuits": ["2MBI1500XYF170"],
      "token_estimate": 200
    }
  ]
}
```

3. Verify context includes SPICE models:

```bash
curl -s -X POST http://localhost:8000/api/context/assemble \
  -H "Content-Type: application/json" \
  -d '{"request": "What SPICE models are defined?"}' | python3 -m json.tool
```

**Expected:** Context includes `### SPICE Models` section with complete library content (comments stripped).

**Verify library content is complete:**
- `.SUBCKT` definitions present
- `.MODEL` statements present
- Comment lines (starting with `*`) removed

---

## Test 15: Simulation Import

**Purpose:** Verify simulation data can be imported from CSV and console output.

**Prerequisites:**
- Schematic loaded (Test 3)
- CSV file exported from KiCad simulator
- Console output copied from simulator window

**Test 15a: Import from CSV only**

```bash
# Create a test CSV file
cat > /tmp/test_transient.csv << 'EOF'
time,V(out),I(R1)
0.000,0.0,0.0
0.001,5.2,0.052
0.002,9.8,0.098
0.003,12.1,0.121
0.004,12.0,0.120
EOF

# Import simulation
curl -s -X POST http://localhost:8000/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": "/tmp/test_transient.csv",
    "console_text": null
  }' | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "imported",
  "run_id": "...",
  "analysis_type": "tran",
  "converged": true,
  "signal_count": 3,
  "sample_count": 5
}
```

**Test 15b: Import from console only**

```bash
curl -s -X POST http://localhost:8000/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": null,
    "console_text": "Circuit: * rectifier\nDoing analysis at TEMP = 27.000000\nReference   Value      Power    \nV1          12V       0.144W   \nR1          1k        0.0W     \n\nOperating point information:\nV(out) = 12.000000\nI(R1) = 0.012000"
  }' | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "imported",
  "run_id": "...",
  "analysis_type": "op",
  "converged": true,
  "op_point_count": 2
}
```

**Test 15c: Import from both CSV and console**

```bash
curl -s -X POST http://localhost:8000/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{
    "csv_path": "/tmp/test_transient.csv",
    "console_text": "Circuit: * rectifier\nTransient analysis...\nNo errors detected."
  }' | python3 -m json.tool
```

---

## Test 16: Simulation State Query

**Purpose:** Verify simulation state endpoint returns imported data.

```bash
curl -s http://localhost:8000/api/simulation/state | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "current",
  "last_run_id": "...",
  "last_run_timestamp": "2026-08-21T...",
  "analysis_type": "tran",
  "converged": true,
  "staleness_warning": null
}
```

---

## Test 17: Simulation Archive (FIFO)

**Purpose:** Verify simulation history management.

**Steps:**

1. Import first simulation
2. Import second simulation
3. Check history directory

```bash
# Import simulation 1
curl -s -X POST http://localhost:8000/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "/tmp/test1.csv"}'

# Import simulation 2
curl -s -X POST http://localhost:8000/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "/tmp/test2.csv"}'

# Check history
ls -la fixtures/schematics/.hephaistus/simulations/history/
```

**Expected:**
- `current/` contains most recent simulation
- `history/` contains previous simulation (timestamped folder)
- Max 5 historical runs (older runs deleted)

---

## Test 18: Simulation Freshness Detection

**Purpose:** Verify simulation staleness is detected when schematic changes.

**Note:** Staleness detection works within the SAME project. Loading a different project creates a new session (simulation state = "none").

**Test 18a: Same-project staleness**

```bash
# Step 1: Load schematic and import simulation
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/project/schematic.kicad_sch"
curl -s -X POST http://localhost:8000/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "/tmp/test.csv"}'

# Step 2: Verify simulation is current
curl -s http://localhost:8000/api/simulation/state | python3 -m json.tool
# Expected: "status": "current"

# Step 3: Simulate schematic modification by reloading with external change
# (In practice, this would be KiCad saving the file, changing its hash)
# For testing, we can manually modify the file:
echo "# Modified" >> /path/to/project/schematic.kicad_sch

# Step 4: Reload schematic
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/project/schematic.kicad_sch"

# Step 5: Check simulation state - should be stale
curl -s http://localhost:8000/api/simulation/state | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "stale",
  "staleness_warning": "Schematic modified after last simulation (hash changed: abc12345 → def67890)"
}
```

**Test 18b: Different project resets simulation**

```bash
# Load project A with simulation
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/projectA/schematic.kicad_sch"
curl -s -X POST http://localhost:8000/api/simulation/import -d '{"csv_path": "/tmp/test.csv"}'

# Load project B (different project)
curl -s -X POST "http://localhost:8000/api/schematic/load?path=/path/to/projectB/schematic.kicad_sch"

# Check simulation state - should be "none" (new session)
curl -s http://localhost:8000/api/simulation/state | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "none",
  "last_run_id": null,
  "staleness_warning": null
}
```

**Explanation:** Loading a different project creates a NEW session (separate `.hephaistus/` directory). This is correct behavior - simulation staleness only applies within the same project.

---

## Test 19: SPICE Library Context in LLM Query

**Purpose:** Verify LLM can see SPICE model topology.

```bash
curl -s -X POST http://localhost:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "In the FUJI IGBT library, is the freewheeling diode antiparallel to the switch? Explain the connection.",
    "provider": "ollama",
    "model": "gemma4:e4b"
  }' | python3 -m json.tool
```

**Expected:** Response references:
- Diode D1 between E and C (Emitter and Collector)
- Confirms antiparallel connection
- May mention internal gate resistor Rg

**Example response excerpt:**
> "Yes, the freewheeling diode (D1) is connected between E and C, making it antiparallel to the main IGBT switch (M1). The subcircuit shows: D1 E C FWD_MODEL..."

---

## Test 20: Archive Persistence

**Purpose:** Verify simulation archives persist across server restart.

**Steps:**

1. Import simulation (Test 15)
2. Stop server
3. Start server
4. Restore session
5. Check history directory

```bash
# After importing
ls -la fixtures/schematics/.hephaistus/simulations/

# Stop server
pkill -f "uvicorn api.server:app"

# Restart
uvicorn api.server:app --host 127.0.0.1 --port 8000 &

# Restore session
curl -s -X POST http://localhost:8000/api/session/restore | python3 -m json.tool

# Check history persists
ls -la fixtures/schematics/.hephaistus/simulations/history/
```

**Expected:** History folders persist after restart.

---

## Troubleshooting

### Server won't start

```bash
# Check for port conflicts
lsof -i :8000

# Check Python dependencies
pip install -e .
pip install python-dotenv
```

### OpenRouter API errors

```bash
# Verify API key is loaded
cat .env | grep OPENROUTER

# Test API key directly
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models
```

### Ollama connection errors

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Pull required model
ollama pull gemma4:e4b
```

### Session not persisting

```bash
# Check permissions
ls -la fixtures/schematics/.hephaistus/

# Check for errors in server log
tail -20 /tmp/hephaistus.log
```

---

## Test Summary Template

| Test | Status | Notes |
|------|--------|-------|
| 1. Health Check | ⬜ | |
| 2. Empty Session | ⬜ | |
| 3. Load Schematic | ⬜ | |
| 4. Session Status | ⬜ | |
| 5. Schematic State | ⬜ | |
| 6. LLM Query (Ollama) | ⬜ | |
| 7. LLM Query (OpenRouter) | ⬜ | |
| 8. Clarification Flow | ⬜ | |
| 9. Session Persistence | ⬜ | |
| 10. Context Assembly | ⬜ | |
| 11. History Search | ⬜ | |
| 12. Multiple Projects | ⬜ | |
| 13. Project Root Discovery | ⬜ | |
| 14. SPICE Library Loading | ⬜ | |
| 15. Simulation Import | ⬜ | |
| 16. Simulation State Query | ⬜ | |
| 17. Simulation Archive (FIFO) | ⬜ | |
| 18. Simulation Freshness | ⬜ | |
| 19. SPICE Library in LLM | ⬜ | |
| 20. Archive Persistence | ⬜ | |

---

## Next Steps

After passing these tests:

1. **Companion UI Tests** — Test React frontend integration
2. **End-to-End Tests** — Full workflow from schematic load to patch application
3. **Simulation Import UI** — Test ImportSimulationDialog component
4. **History Tests** — Verify FTS5 search and statistics

## Test Fixtures

Create test fixtures for simulation tests:

```bash
# Create test CSV
cat > fixtures/simulations/test_transient.csv << 'EOF'
time,V(out),I(R1)
0.000,0.0,0.0
0.001,5.2,0.052
0.002,9.8,0.098
0.003,12.1,0.121
0.004,12.0,0.120
EOF

# Create test console output
cat > fixtures/simulations/test_console.txt << 'EOF'
Circuit: * rectifier
Doing analysis at TEMP = 27.000000
Reference   Value      Power
V1          12V       0.144W
R1          1k        0.0W

Operating point information:
V(out) = 12.000000
I(R1) = 0.012000
EOF
```

## Automated Test Script

Run all tests with a single script:

```bash
#!/bin/bash
# test-api.sh - Run all API tests

BASE_URL="http://localhost:8000"
SCHEMATIC="/path/to/hephaistus/fixtures/schematics/rectifier.kicad_sch"

# Test 1: Health Check
echo "Test 1: Health Check"
curl -s $BASE_URL/ | python3 -m json.tool

# Test 3: Load Schematic
echo "Test 3: Load Schematic"
curl -s -X POST "$BASE_URL/api/schematic/load?path=$SCHEMATIC" | python3 -m json.tool

# Test 14: SPICE Libraries
echo "Test 14: SPICE Libraries"
curl -s $BASE_URL/api/session/status | python3 -m json.tool | grep -A5 spice_libraries

# Test 15: Import Simulation
echo "Test 15: Import Simulation"
curl -s -X POST $BASE_URL/api/simulation/import \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "fixtures/simulations/test_transient.csv"}' | python3 -m json.tool

# Test 16: Simulation State
echo "Test 16: Simulation State"
curl -s $BASE_URL/api/simulation/state | python3 -m json.tool

echo "All tests completed."
```