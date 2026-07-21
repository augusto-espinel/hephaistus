# CHANGELOG

## 2026-07-21: Manual Sync Workflow & UI Improvements

### Added
- **Manual sync buttons** in sidebar panel:
  - "Parse KiCad → JSON" - One-way ingestion of KiCad schematic
  - "Apply JSON → KiCad" - One-way application of JSON changes to KiCad
- **Sync status indicators**:
  - 🔴 KiCad newer - Parse needed
  - 🔵 JSON newer - Apply needed
  - 🟢 In sync
- **Recommended action highlighting** - Arrow and "(recommended)" label on the logical button
- **Confirmation dialogs** for destructive operations:
  - Warns when applying JSON while KiCad has uncommitted changes
  - Warns when parsing KiCad while JSON has uncommitted changes
  - Option to "Discard KiCad changes and restore from JSON" when appropriate
- **Baseline file naming** - Uses `.original.json` suffix to avoid collision with `_backup.kicad_sch` files

### Fixed
- **Naming collision** - `_backup.json` was being confused with JSON for `_backup.kicad_sch` files
- **Sync status detection** - Correctly tracks `lastSync` timestamp and source after operations
- **Status refresh** - Added `refreshAsync()` to ensure file timestamps are current before status checks
- **Removed duplicate `value` field** - JSON now stores `value` only in `properties.Value`

### Removed
- **Full Sync button** - Workflow is one-way-at-a-time, not circular

## 2026-07-20: TypeScript Compilation & Status Panel

### Fixed
- Resolved 33 TypeScript compilation errors across 5 files
- Fixed path resolution for Python delta script using `findHephaistusRoot()`

### Added
- Status panel showing sync direction based on file timestamps
- Delta application infrastructure (`deltaApplyService.ts`)

## 2026-07-18: KiCad Ingestion Working

### Added
- End-to-end KiCad schematic parsing via KiUtils
- JSON state generation from `.kicad_sch` files
- State file tracking in `.hephaistus/state.json`

## 2026-07-14: Project Initialization

### Added
- Merged Obsidian backup of Hephaistus spec with existing KiUtils Phase 1 spec
- Added end-to-end narrative and architecture alignment
- Created memory snapshot entry