# HephAIstus - KiCad Schematic Synchronization (Kicad Sync) (Draft Addendum)

This addendum describes the in-repo approach to synchronizing a KiCad schematic with the optimized JSON ledger and an optional Python patch, using the same KiCad parser (kiutils) library as the ingestion path.

Overview
- Goal: When the ledger.json (optimized state after synchronization) indicates changes to the schematic, apply a delta to schematic.kicad_sch without altering existing component positions, and inject new components where needed.
- Scope: Ingestor loads current schematic, ledger, and optimized JSON state; delta identifies value changes and new parts; updater applies value changes, injects new parts at a staging area, and attaches wire stubs and net labels.

Folder layout (within the same kicad_sync folder):
- schematic.kicad_sch        target schematic to update
- ledger.json                 optimized JSON state from sync
- kicad_update.py              orchestrator
- ingestion.py                 KiCad → JSON loader/validator (existing from ingestion path)
- delta.py                     compute value diffs vs ledger
- updater.py                   apply updates to schematic
- staging.py                   compute global max bounds and staging origin
- backups/                    timestamped backups of schematic before update
- utils.py                     helpers: open/parse, backups, net-name mapping
- README.md                    notes on conventions

Key behaviors
- Existing parts: only value fields updated; positions pos.x/pos.y preserved.
- New parts: placed at a defined staging area just outside the current bounds; 50 mil grid steps; wires of 100 or 150 mil stub length; net-labels from target nets in JSON.
- Validation: re-parse schematic after updates; save updated file; create a timestamped backup.
- Environment: run within the same virtual environment as ingestion; KiCad/kiutils API calls should be swapped in with real code.

Implementation plan (high level)
1. Load the original schematic via kiutils; parse Symbol objects with refs, values, and positions.
2. Load ledger.json (the latest JSON state) and compute delta:
   - For existing parts: if value changed in JSON, update symbol.value only.
   - For new parts: inject new Symbol with footprint/value and stage using staging.py rules.
3. Locate staging origin: compute global maxX/maxY from current schematic elements; set stagingOriginX = maxX + 1000 mils; stagingOriginY = maxY + 1000 mils.
4. Inject new parts, create 100/150 mil wire stubs, add net-labels at wire endpoints.
5. Validate and save: re-parse, then save back to schematic.kicad_sch; store a backup in backups/ with a timestamp.

Next steps for implementation
- Implement skeleton modules (kicad_sync.py, ingestion.py (reuse), delta.py, updater.py, staging.py, backups.py).
- Wire into unit tests and add a simple integration test harness using mock kiutils.
- Document usage in README within the folder.
