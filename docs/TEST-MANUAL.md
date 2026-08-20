# Manual Test Plan: Phase 3 Integration

## Prerequisites

### 1. Environment Setup

```bash
# Navigate to project
cd /path/to/hephaistus

# Create .env file for API key (optional - only for OpenRouter)
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Or export directly
export OPENROUTER_API_KEY="your-key-here"
```

**API Key Options:**
- **OpenRouter** (recommended for testing): Get key from https://openrouter.ai/keys
- **Ollama** (local, no key required): Install from https://ollama.ai and run `ollama serve`

### 2. Start Servers

**Terminal 1 - Backend:**
```bash
cd /path/to/hephaistus
source .venv/bin/activate
uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd /path/to/hephaistus/companion
npm install  # First time only
npm run dev
```

**Verify:**
- Backend: http://localhost:8000 should return `{"status":"ok"}`
- Frontend: http://localhost:3000 should show HephAIstus UI

---

## Test Cases

### Test 1: Backend Health Check

**Purpose:** Verify backend is running and responding.

**Steps:**
```bash
curl http://localhost:8000/
```

**Expected:**
```json
{"status":"ok","service":"hephaistus-companion-api"}
```

---

### Test 2: Load Schematic

**Purpose:** Verify schematic parsing and state management.

**Steps:**
```bash
curl -X POST "http://localhost:8000/api/schematic/load?path=fixtures/schematics/rectifier.kicad_sch"
```

**Expected:**
```json
{
  "status": "loaded",
  "path": "fixtures/schematics/rectifier.kicad_sch",
  "components": 10,
  "nets": 5
}
```

---

### Test 3: Get Schematic State

**Purpose:** Verify schematic state endpoint returns parsed data.

**Steps:**
```bash
curl http://localhost:8000/api/schematic/state
```

**Expected:**
```json
{
  "path": "fixtures/schematics/rectifier.kicad_sch",
  "hash": "...",
  "component_count": 10,
  "net_count": 5,
  "has_unsaved_changes": false,
  ...
}
```

---

### Test 4: Get Simulation State

**Purpose:** Verify simulation state endpoint returns staleness info.

**Steps:**
```bash
curl http://localhost:8000/api/simulation/state
```

**Expected:**
```json
{
  "status": "none",
  "last_run_id": null,
  "staleness_warning": null
}
```

---

### Test 5: Assemble Context (Debug)

**Purpose:** Verify context assembly works without LLM.

**Steps:**
```bash
curl -X POST http://localhost:8000/api/context/assemble \
  -H "Content-Type: application/json" \
  -d '{"request": "Add a snubber circuit across D1"}'
```

**Expected:**
```json
{
  "session_id": "...",
  "total_tokens": <number>,
  "layers": {
    "system": "...",
    "session": "...",
    ...
  },
  "prompt": "..."
}
```

---

### Test 6: LLM Generation (Ollama - Local)

**Prerequisites:**
- Ollama running: `ollama serve`
- Model pulled: `ollama pull llama3.1:70b` (or `llama3.1:8b` for faster testing)

**Steps:**
```bash
curl -X POST http://localhost:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Add a snubber circuit across D1",
    "provider": "ollama",
    "model": "llama3.1:8b"
  }'
```

**Expected:**
```json
{
  "raw_response": "...",
  "patch_plan": {...} or null,
  "is_clarification": false,
  "is_valid": true
}
```

**Note:** First run may be slow (model loading). Subsequent runs are faster.

---

### Test 7: LLM Generation (OpenRouter - Cloud)

**Prerequisites:**
- `OPENROUTER_API_KEY` environment variable set

**Steps:**
```bash
curl -X POST http://localhost:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Add a snubber circuit across D1",
    "provider": "openrouter",
    "model": "anthropic/claude-3.5-sonnet"
  }'
```

**Expected:**
```json
{
  "raw_response": "...",
  "patch_plan": {...},
  "reasoning": "...",
  "is_valid": true
}
```

---

### Test 8: Frontend - Session Status Display

**Purpose:** Verify frontend shows schematic/simulation status.

**Steps:**
1. Open http://localhost:3000 in browser
2. Observe SessionStatus component in left sidebar

**Expected:**
```
┌─────────────────────────────────────┐
│ Schematic                           │
│ ● rectifier.kicad_sch               │
│   saved                              │
│   10 components, 5 nets             │
│                                      │
│ Simulation                           │
│ ○ No simulation                      │
│                                      │
│ Workflow                             │
│ 1. Save ✓                            │
│ 2. Sim                               │
│ 3. Prompt ✓                          │
└─────────────────────────────────────┘
```

---

### Test 9: Frontend - Chat Input (No Schematic)

**Purpose:** Verify pre-prompt guard blocks input without schematic.

**Steps:**
1. Stop backend server (Ctrl+C)
2. Restart without loading schematic
3. Open http://localhost:3000

**Expected:**
- Yellow warning panel: "Save required before prompting"
- Text input disabled (grayed out)
- Send button disabled

---

### Test 10: Frontend - Chat Submission

**Prerequisites:**
- Schematic loaded (Test 2)
- LLM available (Ollama or OpenRouter)

**Steps:**
1. Open http://localhost:3000 in browser
2. Type in chat: "Add a snubber circuit across D1"
3. Click "Send"

**Expected:**
- Button shows "Thinking..." while processing
- Response appears in chat area
- No error messages

---

### Test 11: History Search

**Purpose:** Verify FTS5 history search works.

**Steps:**
```bash
# First, generate some history (run Test 10 multiple times)
curl "http://localhost:8000/api/history/search?q=snubber&limit=5"
```

**Expected:**
```json
{
  "entries": [
    {
      "id": "...",
      "user_request": "Add a snubber circuit...",
      "relevance_score": 0.8,
      ...
    }
  ]
}
```

---

### Test 12: History Recent

**Purpose:** Verify recent history retrieval.

**Steps:**
```bash
curl "http://localhost:8000/api/history/recent?limit=10"
```

**Expected:**
```json
{
  "entries": [
    {
      "id": "...",
      "timestamp": "...",
      "user_request": "...",
      "reasoning_summary": "..."
    }
  ]
}
```

---

## Integration Test Matrix

| Test | Backend | Frontend | LLM Required |
|------|---------|----------|--------------|
| 1. Health check | ✅ | - | No |
| 2. Load schematic | ✅ | - | No |
| 3. Schematic state | ✅ | ✅ | No |
| 4. Simulation state | ✅ | ✅ | No |
| 5. Context assemble | ✅ | - | No |
| 6. LLM (Ollama) | ✅ | - | Yes (local) |
| 7. LLM (OpenRouter) | ✅ | - | Yes (API key) |
| 8. Frontend status | - | ✅ | No |
| 9. Frontend guard | - | ✅ | No |
| 10. Chat submission | ✅ | ✅ | Yes |
| 11. History search | ✅ | - | No |
| 12. History recent | ✅ | - | No |

---

## Troubleshooting

### Backend won't start
```bash
# Check Python dependencies
source .venv/bin/activate
pip install -e ".[all]"

# Check for import errors
python -c "from api.server import app; print('OK')"
```

### Frontend won't start
```bash
# Clear node_modules and reinstall
cd companion
rm -rf node_modules package-lock.json
npm install
```

### Ollama not found
```bash
# Install Ollama
brew install ollama  # macOS
# or download from https://ollama.ai

# Start server
ollama serve

# Pull model
ollama pull llama3.1:8b
```

### OpenRouter API key issues
```bash
# Verify key is set
echo $OPENROUTER_API_KEY

# Test directly
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "anthropic/claude-3.5-sonnet", "messages": [{"role": "user", "content": "Hi"}]}'
```

### CORS errors in browser
- Backend has CORS enabled for `localhost:3000` and `localhost:5173`
- Check browser console for specific error
- Verify backend is running on port 8000

---

## Success Criteria

- All Tests 1-5 pass (core functionality)
- At least one of Tests 6-7 passes (LLM integration)
- Frontend displays correctly (Tests 8-9)
- End-to-end flow works (Test 10)

---

## Next Steps After Testing

1. **File Watcher:** Implement `.kicad_sch` file watching for automatic reload
2. **KiCad Integration:** Test with actual KiCad workflow (save → reload)
3. **Tauri Packaging:** Package as desktop app for KiCad integration
4. **Error Handling:** Add user-friendly error messages in UI
5. **Streaming:** Implement streaming responses for better UX