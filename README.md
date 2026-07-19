# HephAIstus

**LLM-Driven Circuit Optimization for VS Code**

HephAIstus is a VS Code extension that bridges KiCad schematic design with Python/SPICE simulation workflows. It enables **Decoupled Collaboration**: the engineer maintains spatial control of the visual schematic, while an LLM-backed agent handles mathematical optimization and simulation in the background.

## Architecture

The system operates across three pillars:
1. **Schematic** (`.kicad_sch`) — Human's source of truth; geometry is immutable
2. **JSON State** (`state.json`) — Machine-readable ledger for LLM reasoning
3. **Code** (Python/SKiDL) — Simulation catalyst for iterative optimization

### Project Structure

```
hephaistus/
├── src/                    # TypeScript extension
│   ├── services/           # Core services (ingestion, patching)
│   ├── python/             # Python bridge services
│   └── ui/                 # VS Code UI components
├── python/                 # Python package
│   └── hephaistus/
│       ├── kicad_sync/     # KiCad synchronization
│       ├── simulation/     # SPICE simulation (planned)
│       └── utils/          # Common utilities
├── tests/                  # Test suites
│   ├── typescript/
│   └── python/
├── fixtures/               # Test fixtures
├── scripts/                # Utility scripts
└── docs/                   # Documentation
```

## Quick Start

### Prerequisites

- VS Code 1.85+
- Python 3.9+ (for KiCad parsing and simulation)
- Node.js 18+

### Installation

1. Install the extension from VS Code Marketplace
2. Open a KiCad project
3. Run "HephAIstus: Initialize Project" from the Command Palette

### Python Setup

The extension requires Python dependencies for KiCad parsing and simulation:

```bash
# Automatic setup (on first activation)
# Or manual setup:
cd python
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Configure LLM backends in VS Code settings:

```json
{
  "hephaistus.ollama.endpoint": "http://localhost:11434",
  "hephaistus.openrouter.apiKey": "your-api-key",
  "hephaistus.execution.maxSteps": 100,
  "hephaistus.execution.timeoutSeconds": 60
}
```

## Typical Workflow

1. **Modify KiCad schematic** and save
2. **Trigger optimization** via Command Palette: "HephAIstus: Optimize Circuit"
3. **Review LLM suggestions** in the patch viewer
4. **Accept/Reject patches** to apply changes
5. **Run simulation** to validate optimization

## Features

### KiCad Synchronization
- Bidirectional sync between KiCad schematics and JSON state
- Preserve component positions while updating values
- Staging area for new components

### LLM Integration
- Local Ollama for ingestion and drift proposals
- Cloud OpenRouter for optimization passes
- Streaming output in VS Code webview

### SPICE Simulation (Planned)
- SKiDL schematic generation
- ngspice simulation execution
- inspire circuit analysis

## Development

### Build

```bash
npm install
npm run compile
```

### Test

```bash
npm test                    # TypeScript tests
cd python && pytest         # Python tests
```

### Project Setup

```bash
# Bootstrap Python environment
scripts/bootstrap-venv.sh

# Post-install hook
npm run postinstall
```

## Documentation

- [Specification](docs/spec.md) — Complete system specification
- [Architecture](docs/architecture.md) — Technical architecture details
- [KiCad Sync](docs/python/kicad-sync.md) — KiCad synchronization module

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.