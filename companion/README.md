# HephAIstus Companion UI

AI copilot companion for KiCad schematic design.

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Architecture

- **Framework:** React 18 + TypeScript
- **Build:** Vite
- **Components:** Radix UI primitives
- **Routing:** React Router

## Pages

- **Schematic View** (`/`) — Current schematic state and components
- **Context Inspector** (`/context`) — Debug view of assembled LLM context
- **Patch-Plan Diff** (`/diff`) — Before/after comparison of proposed changes
- **History Browser** (`/history`) — Searchable decision history

## Tauri Integration

To build as a desktop app with Tauri:

1. Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
2. Install Tauri CLI: `cargo install tauri-cli`
3. Initialize Tauri: `cargo tauri init`
4. Build: `cargo tauri build`

The companion will communicate with the Python backend via HTTP/WebSocket.

## Backend API

The companion expects a backend server at `http://localhost:8000` with these endpoints:

- `POST /api/context/assemble` — Assemble LLM context
- `POST /api/llm/generate` — Generate patch-plan
- `GET /api/history/search` — Search history
- `GET /api/history/recent` — Get recent history
- `GET /api/schematic/state` — Get current schematic state