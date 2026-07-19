TESTING GUIDE: KiCad Sync (Hephaistus) - Ingestion & Update testing

Overview
- This guide documents how to run ingestion alignment tests and delta updates using the JSON proxy when KiCad tooling is unavailable, and how to enable full KiCad-based tests when kiutils is present.

Project structure
- tests/: fixtures, ingest_align.py, min_run_delta.py, and small test runners.
- ledger_aligned.json: produced by ingest_align.py
- schematic.kicad_sch: minimal fixture schematic in JSON form

Prerequisites
- Python 3.10+
- Optional: kiutils (for real KiCad integration)
- Optional: pytest (for automated tests)

Workflow - JSON-only path (no KiCad)
1. Prepare fixtures under tests/fixtures: schematic.kicad_sch and ledger.json
2. Run ingestion alignment:
   python3 tests/ingest_align.py
   - Outputs ledger_aligned.json in tests/fixtures
3. Run delta dry-run:
   python3 kicad_update.py --dry-run --ledger_path tests/fixtures/ledger_aligned.json --schematic_path tests/fixtures/schematic.kicad_sch
   - Outputs a Markdown delta to stdout
4. Review delta and decide to proceed with a live update (requires KiCad tooling)

Workflow - KiCad path (with kiutils)
1. Ensure KiCad and kiutils are installed and accessible to Python
2. Use the same fixtures, but the ingest_align.py will try to read the live schematic via kiutils and produce ledger_aligned.json
3. Run delta dry-run, then perform live update with proper backups

Environment setup: kiutils
- Install via your package manager or building KiCad tools: consult kiutils docs for installation steps
- Ensure KiCad libraries are accessible in the KiCad environment

Validation tips
- Confirm that new_parts in delta correspond to entries in ledger.json but not in schematic.kicad_sch
- Confirm new net creation and label placement in the staging area mock
- Backup behavior is exercised only in live path (requires write permissions to schematic files)

Tips
- Use TESTING_GUIDE_KICAD_SYNC.md as a living document and keep it updated as the test harness evolves.
