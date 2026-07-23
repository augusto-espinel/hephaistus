# HephAIstus Test Plan

> **Superseded 2026-07-23.** Use the consolidated test specs instead:
> - User manual tests: `docs/testing/USER-TESTS.md`
> - Agent automated tests: `docs/testing/AGENT-TESTS.md`
> - Test environment overview: `docs/testing/README.md`

*Created 2026-07-16 — Manual Test Checklist*

---

## Overview

This document contains manual test procedures for validating the HephAIstus VS Code extension. Each test has a checkbox for you to mark the result.

**Status Legend:**
- [ ] Not tested
- [✓] Passed
- [✗] Failed (add note)
- [⊘] Skipped / Not applicable

---

## Prerequisites

Before testing, ensure:

- [ ] VS Code installed (version ≥ 1.85)
- [ ] Node.js installed (version ≥ 18)
- [ ] Python installed (version ≥ 3.10)
- [ ] KiCad installed (version ≥ 7.0) — for end-to-end tests
- [ ] Ollama running locally (if testing local LLM) — or OpenRouter API key configured

---

## 1. Build & Compilation Tests

### 1.1 TypeScript Compilation

```bash
cd hephaistus
npm install
npm run compile
```

**Expected:** Clean compilation with no errors.

| Test | Result | Notes |
|------|--------|-------|
| [ ] `npm install` completes successfully | | |
| [ ] `npm run compile` produces no errors | | |
| [ ] `out/` directory contains compiled JS files | | |
| [ ] TypeScript source maps generated correctly | | |

### 1.2 Package Structure

```bash
npm run package
```

**Expected:** VSIX package created in `out/` directory.

| Test | Result | Notes |
|------|--------|-------|
| [ ] `npm run package` creates `.vsix` file | | |
| [ ] VSIX file size is reasonable (< 5MB) | | |
| [ ] VSIX contains expected files | | |

---

## 2. Extension Activation Tests

### 2.1 Extension Loading

Install the extension in VS Code:
- Development: Press F5 in VS Code to launch Extension Development Host
- Production: Install from VSIX: `code --install-extension hephaistus-*.vsix`

| Test | Result | Notes |
|------|--------|-------|
| [ ] Extension activates without errors | | |
| [ ] No error messages in VS Code Output panel | | |
| [ ] `HephAIstus` commands appear in Command Palette (Ctrl+Shift+P) | | |
| [ ] Extension icon appears in sidebar (if applicable) | | |

### 2.2 Command Registration

Open Command Palette (Ctrl+Shift+P) and search for "HephAIstus":

| Test | Result | Notes |
|------|--------|-------|
| [ ] `HephAIstus: Start Session` command exists | | |
| [ ] `HephAIstus: Open State File` command exists | | |
| [ ] `HephAIstus: Sync Schematic` command exists | | |
| [ ] Commands execute without crashing | | |

### 2.3 Python Environment Bootstrap

The extension should auto-bootstrap Python dependencies on first activation:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Virtual environment created in VS Code global storage | | |
| [ ] `requirements.txt` dependencies installed | | |
| [ ] No Python import errors in Output panel | | |
| [ ] `venvManager.ts` logs show successful bootstrap | | |

---

## 3. KiCad Parsing Tests

### 3.1 Schematic Ingestion

Create or open a KiCad schematic file (`.kicad_sch`):

| Test | Result | Notes |
|------|--------|-------|
| [ ] File watcher detects `.kicad_sch` save events | | |
| [ ] Schematic parsed without errors | | |
| [ ] JSON state file created (`.hephaistus/state.json`) | | |
| [ ] Components correctly extracted to JSON | | |
| [ ] Net connections correctly captured | | |

### 3.2 KiUtils Fallback

If KiUtils is not available, the system should fall back to mock parsing:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Extension handles missing KiUtils gracefully | | |
| [ ] Fallback parsing produces valid JSON structure | | |
| [ ] Warning message shown (not error/crash) | | |
| [ ] User can continue working with limited functionality | | |

### 3.3 Complex Schematics

Test with various schematic complexities:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Simple schematic (1-5 components) parses correctly | | |
| [ ] Medium schematic (10-30 components) parses correctly | | |
| [ ] Large schematic (50+ components) parses correctly | | |
| [ ] Hierarchical schematics (sub-sheets) handled | | |
| [ ] Schematic with custom symbols handled | | |

---

## 4. State Management Tests

### 4.1 State File Operations

| Test | Result | Notes |
|------|--------|-------|
| [ ] `state.json` created in `.hephaistus/` directory | | |
| [ ] State contains `kicadHash` field | | |
| [ ] State contains `pythonHash` field | | |
| [ ] State contains `components` array | | |
| [ ] State contains `nets` array | | |
| [ ] State persists across VS Code restarts | | |

### 4.2 Hash-Based Change Detection

| Test | Result | Notes |
|------|--------|-------|
| [ ] Hash calculated for schematic file | | |
| [ ] Hash mismatch triggers re-ingestion | | |
| [ ] Hash match skips unnecessary processing | | |
| [ ] `analyzeState()` returns correct drift status | | |

---

## 5. Python Bridge Tests

### 5.1 Process Communication

| Test | Result | Notes |
|------|--------|-------|
| [ ] Python process spawns successfully | | |
| [ ] stdout/stderr captured correctly | | |
| [ ] JSON results parsed from Python output | | |
| [ ] Error handling works (malformed JSON) | | |
| [ ] Process timeout enforced correctly | | |

### 5.2 KiCad Sync Module

Test the Python `kicad_sync` module:

| Test | Result | Notes |
|------|--------|-------|
| [ ] `kicad_update.py` runs without errors | | |
| [ ] `delta.py` computes differences correctly | | |
| [ ] `updater.py` applies patches correctly | | |
| [ ] Backup created before modifications | | |
| [ ] Staging area coordinates computed | | |

---

## 6. LLM Integration Tests

### 6.1 LLM Client Configuration

Configure LLM backend (Ollama or OpenRouter):

| Test | Result | Notes |
|------|--------|-------|
| [ ] Ollama connection succeeds (if configured) | | |
| [ ] OpenRouter API call succeeds (if configured) | | |
| [ ] Configuration errors shown to user | | |
| [ ] Fallback model works when primary fails | | |

### 6.2 LLM Service Operations

| Test | Result | Notes |
|------|--------|-------|
| [ ] `llmService.ts` generates text without errors | | |
| [ ] Streaming output works correctly | | |
| [ ] Rate limiting handled gracefully | | |
| [ ] Token counting/limits enforced | | |

---

## 7. Patch Application Tests

### 7.1 Diff Parsing

Test `patchUtils.ts`:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Unified diff format parsed correctly | | |
| [ ] Multi-line hunks handled | | |
| [ ] Binary diff rejected gracefully | | |
| [ ] Malformed diff handled without crash | | |

### 7.2 Patch Application

Test `patchApplyService.ts`:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Value changes applied correctly | | |
| [ ] Component additions staged correctly | | |
| [ ] Log file created for each patch | | |
| [ ] Rollback works after failed patch | | |
| [ ] Backup restored on user abort | | |

---

## 8. UI Components Tests

### 8.1 Patch Viewer

Open the patch viewer for a proposed change:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Diff rendered correctly | | |
| [ ] Approve/Reject buttons work | | |
| [ ] Changes preview shown | | |
| [ ] Large diffs scrollable | | |

### 8.2 LLM Webview

| Test | Result | Notes |
|------|--------|-------|
| [ ] Webview panel opens | | |
| [ ] LLM output streams to webview | | |
| [ ] User can type in chat input | | |
| [ ] Messages persist in history | | |
| [ ] Error messages displayed clearly | | |

---

## 9. Integration Tests

### 9.1 End-to-End Workflow

Complete a full workflow from schematic edit to LLM suggestion:

| Test | Result | Notes |
|------|--------|-------|
| [ ] Open KiCad schematic | | |
| [ ] Edit component value in KiCad | | |
| [ ] Save triggers sync cycle | | |
| [ ] State updated with new value | | |
| [ ] Python drift detected (if applicable) | | |
| [ ] LLM suggestion generated | | |
| [ ] Patch preview shown | | |
| [ ] User approval applies patch | | |

### 9.2 Iterative Optimization

| Test | Result | Notes |
|------|--------|-------|
| [ ] LLM proposes optimization | | |
| [ ] Simulation runs (or fails gracefully if ngspice unavailable) | | |
| [ ] Results fed back to LLM | | |
| [ ] Iteration count tracked | | |
| [ ] Checkpoint triggered at iteration limit | | |

---

## 10. Error Handling Tests

### 10.1 Missing Dependencies

| Test | Result | Notes |
|------|--------|-------|
| [ ] Graceful handling when KiCad not installed | | |
| [ ] Graceful handling when Python not found | | |
| [ ] Graceful handling when ngspice not found | | |
| [ ] Clear error messages shown | | |
| [ ] Extension doesn't crash | | |

### 10.2 File System Errors

| Test | Result | Notes |
|------|--------|-------|
| [ ] Read permission error handled | | |
| [ ] Write permission error handled | | |
| [ ] Disk full error handled | | |
| [ ] File locked error handled | | |

### 10.3 Network Errors

| Test | Result | Notes |
|------|--------|-------|
| [ ] LLM API timeout handled | | |
| [ ] Network disconnection handled | | |
| [ ] Invalid API key error shown | | |
| [ ] Rate limit error shown | | |

---

## 11. Performance Tests

### 11.1 Large Schematics

| Test | Result | Notes |
|------|--------|-------|
| [ ] 100-component schematic ingests < 5s | | |
| [ ] 500-component schematic ingests < 30s | | |
| [ ] Memory usage stays reasonable (< 500MB) | | |
| [ ] UI remains responsive during processing | | |

### 11.2 Rapid Edits

| Test | Result | Notes |
|------|--------|-------|
| [ ] Debouncing prevents rapid re-ingestion | | |
| [ ] Queue doesn't overflow | | |
| [ ] No duplicate state updates | | |

---

## 12. Component Addition Tests

### 12.1 Parallel Insertion (Different Nets)

**Setup:** Create test JSON with component connecting to different nets.

```json
{
  "added_components": [{
    "reference": "C2",
    "libId": "Device:C",
    "value": "100n",
    "connections": {
      "1": "dc_plus",
      "2": "dc_minus"
    }
  }]
}
```

| Test | Result | Notes |
|------|--------|-------|
| [ ] Component added to schematic | | |
| [ ] Net labels created for each pin | | |
| [ ] No warning annotations in schematic | | |
| [ ] JSON output: `warnings: []` | | |
| [ ] Schematic opens in KiCad without errors | | |
| [ ] Labels appear at correct positions | | |

**Manual Verification in KiCad:**
1. Open modified schematic in KiCad
2. Verify C2 appears at staging position (offset from existing components)
3. Verify labels `dc_plus` and `dc_minus` appear near pins
4. Run ERC (Electrical Rules Check) — should pass

### 12.2 Series Insertion (Same Net)

**Setup:** Create test JSON with component connecting to same net.

```json
{
  "added_components": [{
    "reference": "R3",
    "libId": "Device:R",
    "value": "100",
    "connections": {
      "1": "dc_plus",
      "2": "dc_plus"
    }
  }]
}
```

| Test | Result | Notes |
|------|--------|-------|
| [ ] Component added to schematic | | |
| [ ] Warning annotation created in schematic | | |
| [ ] JSON output: `warnings[].type === "series_insertion"` | | |
| [ ] VS Code modal shows warning | | |
| [ ] `pendingWarnings` saved to state.json | | |

**Expected Schematic Annotation:**
```
⚠ R3 requires series insertion.
Break wire on net 'dc_plus' and connect labels.
```

**Manual Verification in KiCad:**
1. Open modified schematic
2. Verify warning annotation appears below R3
3. Verify both pins have `dc_plus` labels
4. To complete: Break existing wire, connect R3 in series, update labels

### 12.3 Missing Labels (Parallel Without Existing Labels)

**Setup:** Create test JSON with component connecting to nets that exist but have no labels.

```json
{
  "added_components": [{
    "reference": "R4",
    "libId": "Device:R",
    "value": "1k",
    "connections": {
      "1": "unlabeled_net_a",
      "2": "unlabeled_net_b"
    }
  }]
}
```

| Test | Result | Notes |
|------|--------|-------|
| [ ] Component added to schematic | | |
| [ ] Warning annotation created | | |
| [ ] JSON output: `warnings[].type === "missing_labels"` | | |
| [ ] VS Code modal shows warning | | |

**Expected Schematic Annotation:**
```
⚠ R4 requires labels on existing nets.
Add net labels 'unlabeled_net_a', 'unlabeled_net_b' to existing wires.
```

**Manual Verification in KiCad:**
1. Open modified schematic
2. Verify warning annotation appears below R4
3. Add labels to existing wires manually
4. Verify R4 labels connect when wires are labeled

### 12.4 VS Code UI Guard

**Setup:** Apply JSON → KiCad with warnings, then attempt Parse KiCad → JSON.

| Test | Result | Notes |
|------|--------|-------|
| [ ] Apply JSON → KiCad shows warning modal | | |
| [ ] "Open Schematic" button opens schematic | | |
| [ ] Parse KiCad → JSON blocked with modal | | |
| [ ] Modal shows pending warnings | | |
| [ ] "Parse Anyway" clears warnings and proceeds | | |
| [ ] "Cancel" returns to sync panel | | |

### 12.5 Wiring in KiCad

**Prerequisites:** Component added with net labels.

**Steps:**
1. Open modified schematic in KiCad
2. Locate new component at staging position
3. Locate net labels on pins
4. Use wire tool to connect labels to existing circuit:
   - For parallel: Connect each label to matching net label on existing circuit
   - For series: Break existing wire, connect component in series
5. Verify ERC passes
6. Save schematic

| Test | Result | Notes |
|------|--------|-------|
| [ ] Labels visible in KiCad | | |
| [ ] Wire tool connects to labels | | |
| [ ] ERC passes after manual wiring | | |
| [ ] Schematic saves without errors | | |
| [ ] Re-parse preserves manual changes | | |

### 12.6 Round-Trip After Wiring

**Steps:**
1. Complete manual wiring in KiCad
2. Save schematic
3. Parse KiCad → JSON
4. Verify JSON reflects wired connections

| Test | Result | Notes |
|------|--------|-------|
| [ ] Parse succeeds after manual wiring | | |
| [ ] JSON shows correct net connections | | |
| [ ] No duplicate components | | |
| [ ] Net names preserved | | |

---

## 13. Regression Tests

### 13.1 Previous Bugs

| Bug ID | Description | Test | Result | Notes |
|--------|-------------|------|--------|-------|
| | | | | |

(Add known bugs here as they are discovered and fixed)

---

## Test Summary

**Date Tested:** _______________________

**Tester:** _______________________

**Build Version:** _______________________

**Overall Results:**

| Category | Passed | Failed | Skipped |
|----------|--------|--------|---------|
| Build & Compilation | | | |
| Extension Activation | | | |
| KiCad Parsing | | | |
| State Management | | | |
| Python Bridge | | | |
| LLM Integration | | | |
| Patch Application | | | |
| UI Components | | | |
| Integration | | | |
| Error Handling | | | |
| Performance | | | |
| Component Addition | | | |
| **TOTAL** | | | |

**Critical Issues Found:**

1. _______________________________________
2. _______________________________________
3. _______________________________________

**Blockers:**

1. _______________________________________
2. _______________________________________

**Notes:**

_______________________________________
_______________________________________
_______________________________________

---

## Next Steps After Testing

1. **If tests pass:** Update MEMORY.md with "Ready for next phase" status
2. **If tests fail:** Create issues in issue tracker with reproduction steps
3. **If blockers found:** Document in test summary and notify development team
4. **Update this document:** Add new tests for any discovered edge cases