"""
HephAIstus Companion API Server.

FastAPI server that wires backend modules to HTTP endpoints
for the React companion UI.
"""

import os
import uuid
from pathlib import Path

# Load environment variables from .env file (for development)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

# Backend modules
from hephaistus_context import (
    ContextService,
    SessionPersistence,
    HistoryStore,
    SimulationStatus,
)
from hephaistus_circuit import parse_schematic
from hephaistus_circuit.engine import validate_patch_plan, apply_patch_plan
from hephaistus_circuit.spice_library import load_libraries_for_schematic
from hephaistus_simulation.ingestion import ingest_simulation, to_run_metadata
from hephaistus_simulation.archiver import SimulationArchive
from hephaistus_llm import LLMOrchestrator, ProviderConfig


# Provider config path
PROVIDERS_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "llm-providers.json"

# Application
app = FastAPI(
    title="HephAIstus Companion API",
    description="Backend API for the HephAIstus companion UI",
    version="0.1.0",
)

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_context_service: Optional[ContextService] = None
_history_store: Optional[HistoryStore] = None
_session_persistence: Optional[SessionPersistence] = None
_project_root: Optional[Path] = None


def _init_persistence(project_root: str) -> SessionPersistence:
    """Initialize persistence for a project."""
    global _session_persistence, _history_store, _project_root
    
    _project_root = Path(project_root)
    _session_persistence = SessionPersistence(project_root)
    _history_store = HistoryStore(db_path=str(_project_root / ".hephaistus" / "history.db"))
    
    return _session_persistence


def _restore_session() -> Optional[str]:
    """Restore session from disk if it exists. Returns schematic path or None."""
    global _context_service, _session_persistence, _project_root
    
    if not _session_persistence or not _session_persistence.has_session():
        return None
    
    try:
        session = _session_persistence.load_session()
        if session and session.schematic.path:
            # Restore context service with loaded session
            _context_service = ContextService()
            _context_service.session = session
            return session.schematic.path
    except Exception as e:
        print(f"Warning: Failed to restore session: {e}")
    
    return None


def _save_session() -> None:
    """Save current session to disk."""
    global _context_service, _session_persistence
    
    if not _context_service or not _session_persistence:
        return
    
    try:
        _session_persistence.save_session(_context_service.session)
    except Exception as e:
        print(f"Warning: Failed to save session: {e}")


# Request/Response Models

class SchematicStateResponse(BaseModel):
    path: Optional[str] = None
    hash: Optional[str] = None
    component_count: int = 0
    net_count: int = 0
    components: List[dict] = []
    nets: List[dict] = []
    directives: List[dict] = []
    last_modified: Optional[str] = None
    has_unsaved_changes: bool = False


class SimulationStateResponse(BaseModel):
    status: str  # "current", "stale", "none"
    last_run_id: Optional[str] = None
    last_run_timestamp: Optional[str] = None
    analysis_type: Optional[str] = None
    converged: Optional[bool] = None
    staleness_warning: Optional[str] = None


class GenerateRequest(BaseModel):
    request: str
    schematic_path: Optional[str] = None
    include_full_simulation: bool = False
    provider: str = "ollama"  # "ollama" or "openrouter"
    model: Optional[str] = None
    timeout_seconds: Optional[float] = None  # Override default timeout (120s)


class GenerateResponse(BaseModel):
    raw_response: str
    patch_plan: Optional[dict] = None
    reasoning: str = ""
    is_clarification: bool = False
    clarification_question: str = ""
    parse_error: Optional[str] = None
    is_valid: bool


class ContextAssembleRequest(BaseModel):
    request: str = ""
    include_full_simulation: bool = False
    schematic_path: Optional[str] = None


class ContextAssembleResponse(BaseModel):
    session_id: str
    assembled_at: str
    total_tokens: int
    budget_summary: Optional[dict] = None
    layers: dict
    prompt: str


class HistorySearchResponse(BaseModel):
    entries: List[dict]


# Helper functions

def get_context_service() -> ContextService:
    """Get or create the global context service."""
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service


def get_history_store() -> HistoryStore:
    """Get the project-scoped history store."""
    global _history_store
    if _history_store is None:
        # Fallback to in-memory if no project loaded
        _history_store = HistoryStore()
    return _history_store


# Endpoints

@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "hephaistus-companion-api"}


@app.get("/api/session/status")
async def get_session_status():
    """
    Get current session status.
    
    Returns project root, schematic info, and whether a session is loaded.
    """
    service = get_context_service()
    session = service.session
    
    return {
        "has_session": bool(session.schematic.path),
        "session_id": session.session_id,
        "project_root": session.project_root or None,
        "schematic": {
            "path": session.schematic.path or None,
            "relative_path": session.schematic.relative_path or None,
            "hash": session.schematic.hash or None,
            "component_count": session.schematic.component_count,
            "net_count": session.schematic.net_count,
        },
        "simulation": {
            "status": session.simulation.status.value,
            "last_run": session.simulation.last_run_id,
        },
        "spice_libraries": [
            {
                "name": lib.name,
                "models": lib.models,
                "subcircuits": lib.subcircuits,
                "token_estimate": lib.token_estimate,
            }
            for lib in session.spice_libraries
        ],
        "last_updated": session.last_updated.isoformat() if session.last_updated else None,
    }


@app.post("/api/session/restore")
async def restore_session(project_path: Optional[str] = None):
    """
    Restore a saved session.
    
    If project_path is provided, restore that project's session.
    Otherwise, try to restore the most recent session.
    
    Returns the restored schematic path or null if no session exists.
    """
    global _session_persistence, _project_root
    
    # If project_path provided, initialize persistence for it
    if project_path:
        _init_persistence(project_path)
    
    # If no persistence initialized, try to find the most recent session
    if not _session_persistence:
        # Look for recent sessions in common locations
        # This is a heuristic - in production, we'd track recently used projects
        home = Path.home()
        recent_session = None
        recent_time = 0
        
        # Search in common KiCad project locations
        search_paths = [
            home / "Documents" / "KiCad" / "Projects",
            home / "KiCad" / "Projects",
        ]
        
        for search_dir in search_paths:
            if not search_dir.exists():
                continue
            for session_file in search_dir.rglob(".hephaistus/session.json"):
                try:
                    mtime = session_file.stat().st_mtime
                    if mtime > recent_time:
                        recent_time = mtime
                        recent_session = session_file
                except:
                    continue
        
        if recent_session:
            # Found a session file - initialize from its project
            project_root = str(recent_session.parent.parent)
            _init_persistence(project_root)
        else:
            return {
                "status": "no_session",
                "schematic_path": None,
                "message": "No saved sessions found. Load a schematic first.",
            }
    
    restored_path = _restore_session()
    
    if restored_path:
        service = get_context_service()
        return {
            "status": "restored",
            "schematic_path": restored_path,
            "project_root": service.session.project_root,
            "components": service.session.schematic.component_count,
            "nets": service.session.schematic.net_count,
        }
    else:
        return {
            "status": "no_session",
            "schematic_path": None,
        }


@app.get("/api/llm/providers")
async def get_llm_providers():
    """
    Get available LLM providers and models.
    
    Loads configuration from config/llm-providers.json.
    Returns provider list with models and defaults.
    Also includes whether API keys are configured.
    """
    import json
    
    if not PROVIDERS_CONFIG_PATH.exists():
        raise HTTPException(
            status_code=500, 
            detail="Provider config not found"
        )
    
    with open(PROVIDERS_CONFIG_PATH) as f:
        config = json.load(f)
    
    # Check API key availability for each provider
    providers_with_status = []
    for provider in config.get("providers", []):
        provider_status = provider.copy()
        
        # Check if API key is configured (for providers that need one)
        if provider.get("requires_api_key"):
            env_var = provider.get("env_var","")
            api_key = os.environ.get(env_var)
            provider_status["api_key_configured"] = bool(api_key)
        else:
            provider_status["api_key_configured"] = True  # Local providers don't need keys
        
        # For Ollama, check if server is reachable
        if provider["id"] == "ollama":
            try:
                import requests
                base_url = provider.get("base_url", "http://localhost:11434")
                resp = requests.get(f"{base_url}/api/tags", timeout=2)
                provider_status["server_available"] = resp.status_code == 200
            except:
                provider_status["server_available"] = False
        
        providers_with_status.append(provider_status)
    
    return {
        "providers": providers_with_status,
        "defaults": config.get("defaults", {"provider": "ollama", "model": "gemma4:e4b"})
    }


@app.get("/api/schematic/state", response_model=SchematicStateResponse)
async def get_schematic_state():
    """
    Get current schematic state.
    
    Returns component/net counts, directives, and unsaved status.
    """
    service = get_context_service()
    session = service.session
    
    # Check if schematic file still exists and hasn't changed
    has_unsaved = False
    schematic_path = Path(session.schematic.path) if session.schematic.path else None
    if schematic_path and schematic_path.exists():
        current_hash = session.schematic.compute_hash()
        if session.schematic.hash and current_hash != session.schematic.hash:
            # File was modified externally (e.g., saved in KiCad)
            has_unsaved = False
        # For now, we assume file is saved (user workflow responsibility)
    else:
        has_unsaved = bool(session.schematic.path and not session.schematic.hash)
    
    return SchematicStateResponse(
        path=session.schematic.path or None,
        hash=session.schematic.hash or None,
        component_count=session.schematic.component_count,
        net_count=session.schematic.net_count,
        components=session.schematic.components[:25],  # Limit for UI
        nets=[{"name": n.get("name"), "pins": n.get("connectedPins", [])} for n in session.schematic.nets[:10]],
        directives=[{"type": d.get("directive_type"), "text": d.get("text")} for d in session.schematic.directives],
        last_modified=session.schematic.last_modified.isoformat() if session.schematic.last_modified else None,
        has_unsaved_changes=has_unsaved,
    )


@app.get("/api/schematic/check-stale")
async def check_schematic_stale():
    """
    Check if the schematic file has been modified since last load.
    
    Compares current file hash with stored hash to detect external changes.
    Returns staleness status and suggests reload if needed.
    """
    service = get_context_service()
    session = service.session
    
    if not session.schematic.path:
        return {"stale": False, "reason": "no_schematic"}
    
    schematic_path = Path(session.schematic.path)
    if not schematic_path.exists():
        return {"stale": True, "reason": "file_deleted", "path": str(schematic_path)}
    
    current_hash = session.schematic.compute_hash()
    stored_hash = session.schematic.hash
    
    if current_hash == stored_hash:
        return {"stale": False, "reason": "unchanged"}
    
    return {
        "stale": True,
        "reason": "modified_externally",
        "path": str(schematic_path),
        "stored_hash": stored_hash,
        "current_hash": current_hash,
        "last_modified": session.schematic.last_modified.isoformat() if session.schematic.last_modified else None,
    }


@app.delete("/api/history")
async def clear_history():
    """
    Clear all conversation history for the current project.
    
    This removes all entries from the history database and resets
    the context, allowing the user to start fresh on the same circuit.
    The schematic and simulation state are preserved.
    """
    global _history_store, _context_service, _project_root
    
    if not _history_store:
        raise HTTPException(status_code=404, detail="No project loaded")
    
    try:
        # Clear all history entries
        _history_store.clear_all()
        
        # Reset context service (keeps schematic/simulation, clears history)
        if _context_service:
            _context_service.clear_history()
        
        # Clear cached last_prompt.json
        if _project_root:
            debug_file = _project_root / '.hephaistus' / 'last_prompt.json'
            if debug_file.exists():
                debug_file.unlink()
        
        return {
            "status": "cleared",
            "message": "History cleared. You can start a fresh design iteration.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")


@app.post("/api/summary/generate")
async def generate_summary():
    """
    Generate a session summary using the LLM.
    
    Creates a prompt asking the LLM to summarize the work done,
    using the condensed context (not full history re-read).
    Returns the summary prompt for the frontend to display.
    """
    global _context_service, _history_store
    
    if not _context_service:
        raise HTTPException(status_code=404, detail="No session loaded")
    
    # Get history statistics for context
    history_stats = None
    if _history_store:
        history_stats = _history_store.get_statistics()
    
    # Build summary prompt based on context
    summary_prompt = """Please provide a concise engineering summary of the work done in this session. Include:

1. **Design Goals**: What changes or optimizations were discussed?
2. **Key Decisions**: What design choices were made and why?
3. **Patch Plans**: What schematic changes were proposed?
4. **Validation Results**: Any simulation results or validation feedback?
5. **Open Items**: What remains to be done or verified?

Format the summary in markdown, keeping it focused on actionable engineering decisions rather than conversational details."""

    # Return as a pseudo-response that the frontend can render
    return {
        "status": "generated",
        "prompt": summary_prompt,
        "history_stats": {
            "total_entries": history_stats.get("total_entries", 0) if history_stats else 0,
            "sessions": history_stats.get("sessions", []) if history_stats else [],
        } if history_stats else None,
    }


@app.post("/api/schematic/load")
async def load_schematic(path: str):
    """
    Load a schematic file.
    
    Parses the .kicad_sch file, discovers project root, and updates session state.
    Session is persisted to .hephaistus/session.json in the project directory.
    """
    schematic_path = Path(path)
    if not schematic_path.exists():
        raise HTTPException(status_code=404, detail=f"Schematic not found: {path}")
    
    try:
        # Discover project root from schematic path
        persistence = SessionPersistence()
        project_root = persistence.discover_project_root(str(schematic_path))
        
        # Initialize project-scoped persistence
        _init_persistence(project_root)
        
        # Try to restore existing session for this project
        restored_path = _restore_session()
        
        # Parse schematic
        parsed = parse_schematic(str(schematic_path))
        
        # Calculate relative path from project root
        try:
            relative_path = str(schematic_path.relative_to(project_root))
        except ValueError:
            relative_path = schematic_path.name
        
        # Update context service
        service = get_context_service()
        service.initialize_session(
            schematic_path=str(schematic_path),
            parsed_state=parsed,
        )
        
        # Update session with project-relative info
        service.session.project_root = project_root
        service.session.schematic.relative_path = relative_path
        
        # Load SPICE libraries referenced in schematic
        if parsed and "spice_libraries" in parsed:
            lib_context = load_libraries_for_schematic(
                str(schematic_path),
                search_paths=None,
            )
            
            # Convert to SpiceLibraryInfo objects
            from hephaistus_context.session_state import SpiceLibraryInfo
            service.session.spice_libraries = [
                SpiceLibraryInfo(
                    name=lib.name,
                    path=lib.path,
                    content=lib.content,
                    models=lib.models,
                    subcircuits=lib.subcircuits,
                    token_estimate=lib.token_estimate,
                )
                for lib in lib_context.libraries
            ]
        
        # Save session to disk
        _save_session()
        
        return {
            "status": "loaded",
            "path": str(schematic_path),
            "project_root": project_root,
            "relative_path": relative_path,
            "components": service.session.schematic.component_count,
            "nets": service.session.schematic.net_count,
            "session_file": str(_project_root / ".hephaistus" / "session.json") if _project_root else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse schematic: {str(e)}")


@app.get("/api/simulation/state", response_model=SimulationStateResponse)
async def get_simulation_state():
    """
    Get current simulation state.
    
    Returns staleness info and last run metadata.
    """
    service = get_context_service()
    sim = service.session.simulation
    
    return SimulationStateResponse(
        status=sim.status.value,
        last_run_id=sim.last_run_id,
        last_run_timestamp=sim.last_run_timestamp.isoformat() if sim.last_run_timestamp else None,
        analysis_type=sim.analysis_type,
        converged=sim.converged,
        staleness_warning=sim.staleness_warning,
    )


class SimulationLoadRequest(BaseModel):
    path: Optional[str] = None  # Path to simulation results directory or file
    analysis_type: Optional[str] = None  # "tran", "ac", "dc", "op"
    converged: Optional[bool] = None
    op_points: Optional[List[dict]] = None
    signal_summaries: Optional[List[dict]] = None
    warnings: Optional[List[str]] = None
    errors: Optional[List[str]] = None


@app.post("/api/simulation/load")
async def load_simulation(request: SimulationLoadRequest):
    """
    Load simulation results into session context.
    
    Can either:
    1. Auto-discover from .hephaistus/simulations/ (if path not provided)
    2. Load from specified path
    3. Accept manual results (op_points, signal_summaries)
    
    This allows the LLM to see simulation results for analysis.
    """
    global _project_root, _session_persistence
    
    if not _project_root:
        raise HTTPException(status_code=400, detail="No project loaded. Load a schematic first.")
    
    service = get_context_service()
    
    # If path provided, try to parse simulation files
    if request.path:
        # TODO: Implement simulation file parsing
        # For now, just record that simulation was loaded
        pass
    
    # Update simulation state
    if request.analysis_type:
        service.session.simulation.analysis_type = request.analysis_type
    if request.converged is not None:
        service.session.simulation.converged = request.converged
    if request.op_points is not None:
        service.session.simulation.op_points = request.op_points
    if request.signal_summaries is not None:
        service.session.simulation.signal_summaries = request.signal_summaries
    if request.warnings is not None:
        service.session.simulation.warnings = request.warnings
    if request.errors is not None:
        service.session.simulation.errors = request.errors
    
    # Mark as current
    service.session.simulation.status = SimulationStatus.CURRENT
    service.session.simulation.staleness_warning = None
    service.session.last_updated = datetime.now(timezone.utc)
    
    # Save session
    _save_session()
    
    return {
        "status": "loaded",
        "analysis_type": service.session.simulation.analysis_type,
        "converged": service.session.simulation.converged,
        "signal_count": len(service.session.simulation.signal_summaries) if service.session.simulation.signal_summaries else 0,
        "op_point_count": len(service.session.simulation.op_points) if service.session.simulation.op_points else 0,
    }


class SimulationImportRequest(BaseModel):
    """Request to import simulation from CSV and/or console."""
    csv_path: Optional[str] = None
    console_text: Optional[str] = None


class PatchValidateRequest(BaseModel):
    """Request to dry-run validate a patch plan."""
    patch_plan: dict
    schematic_path: Optional[str] = None  # Uses current session if omitted


class PatchApplyRequest(BaseModel):
    """Request to apply a validated patch plan."""
    patch_plan: dict
    schematic_path: Optional[str] = None  # Uses current session if omitted


@app.post("/api/simulation/import")
async def import_simulation(request: SimulationImportRequest):
    """
    Import simulation data from CSV file and/or console output.
    
    Archives current simulation (if any) to history and loads new data.
    
    User workflow:
    1. Run simulation in KiCad
    2. Export CSV: File -> Export current plot as CSV
    3. Copy console output from simulator
    4. Call this endpoint with both or either
    """
    global _project_root
    
    if not _project_root:
        raise HTTPException(status_code=400, detail="No project loaded. Load a schematic first.")
    
    service = get_context_service()
    
    # Archive current simulation if exists
    archive = SimulationArchive(str(_project_root))
    archive.archive_current()
    
    # Ingest simulation data
    ingested = ingest_simulation(
        schematic_path=service.session.schematic.path,
        schematic_hash=service.session.schematic.hash,
        csv_path=request.csv_path,
        console_text=request.console_text,
    )
    
    # Save to current
    archive.save_current(
        metadata=to_run_metadata(ingested),
        console_text=request.console_text,
        csv_path=request.csv_path,
    )
    
    # Update session state
    service.session.simulation.status = SimulationStatus.CURRENT
    service.session.simulation.last_run_id = ingested.run_id
    service.session.simulation.last_run_timestamp = ingested.timestamp
    service.session.simulation.analysis_type = ingested.analysis_type
    service.session.simulation.converged = ingested.converged
    service.session.simulation.op_points = ingested.op_points
    service.session.simulation.signal_summaries = ingested.signal_summaries
    service.session.simulation.warnings = ingested.warnings
    service.session.simulation.errors = ingested.errors
    service.session.simulation.staleness_warning = None
    # Store schematic hash for staleness detection
    service.session.simulation.schematic_hash = service.session.schematic.hash
    service.session.last_updated = datetime.now(timezone.utc)
    
    # Save session
    _save_session()
    
    return {
        "status": "imported",
        "run_id": ingested.run_id,
        "analysis_type": ingested.analysis_type,
        "converged": ingested.converged,
        "warnings": ingested.warnings,
        "errors": ingested.errors,
        "op_point_count": len(ingested.op_points),
        "signal_count": ingested.signal_count,
        "signal_summary_count": len(ingested.signal_summaries),
        "sample_count": ingested.sample_count,
    }



@app.post("/api/llm/generate", response_model=GenerateResponse)
async def generate_patch_plan(request: GenerateRequest):
    """
    Generate a patch-plan proposal using the LLM.
    
    Assembles context from schematic and simulation, sends to LLM,
    and returns the parsed response.
    """
    # Load schematic if provided
    if request.schematic_path:
        await load_schematic(request.schematic_path)
    
    # Configure provider
    if request.provider == "openrouter":
        config = ProviderConfig.openrouter(
            model=request.model or "anthropic/claude-3.5-sonnet",
            timeout_seconds=request.timeout_seconds,
        )
    else:
        config = ProviderConfig.ollama(
            model=request.model or "gemma4:e4b",
            timeout_seconds=request.timeout_seconds,
        )
    
    # Create orchestrator with shared context service
    service = get_context_service()
    orchestrator = LLMOrchestrator(
        provider_config=config,
        context_service=service,
    )
    
    # Generate (run in thread pool to avoid blocking event loop)
    try:
        proposal = await run_in_threadpool(
            orchestrator.generate,
            user_request=request.request,
            include_full_simulation=request.include_full_simulation,
        )
        
        # Record exchange in history
        service.record_exchange(
            user_request=request.request,
            llm_response=proposal.raw_response,
            reasoning_summary=proposal.reasoning,
            patch_plan=proposal.patch_plan,
        )
        
        # Persist to HistoryStore (SQLite)
        if _history_store and service.session.session_id:
            try:
                from hephaistus_context.history_store import HistoryEntryRecord
                import json
                record = HistoryEntryRecord(
                    id=str(uuid.uuid4())[:12],
                    session_id=service.session.session_id,
                    timestamp=datetime.now(timezone.utc),
                    user_request=request.request,
                    user_context=None,
                    llm_response=proposal.raw_response,
                    reasoning_summary=proposal.reasoning,
                    patch_plan_json=json.dumps(proposal.patch_plan) if proposal.patch_plan else None,
                    validation_result=None,
                    validation_json=None,
                    user_action=None,
                    user_feedback=None,
                    context_tokens=0,
                    response_tokens=0,
                )
                _history_store.add_entry(record)
            except Exception as e:
                print(f"Warning: Failed to persist history: {e}")
        
        return GenerateResponse(
            raw_response=proposal.raw_response,
            patch_plan=proposal.patch_plan,
            reasoning=proposal.reasoning,
            is_clarification=proposal.is_clarification,
            clarification_question=proposal.clarification_question,
            parse_error=proposal.parse_error,
            is_valid=proposal.is_valid(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")


@app.post("/api/context/assemble", response_model=ContextAssembleResponse)
async def assemble_context(request: ContextAssembleRequest):
    """
    Assemble LLM context for debugging.
    
    Returns the full assembled context with token breakdown.
    """
    # Load schematic if provided
    if request.schematic_path:
        await load_schematic(request.schematic_path)
    
    service = get_context_service()
    result = service.assemble(
        user_request=request.request,
        include_full_simulation=request.include_full_simulation,
    )
    
    return ContextAssembleResponse(
        session_id=result.session_id,
        assembled_at=result.assembled_at.isoformat(),
        total_tokens=result.total_tokens,
        budget_summary=result.budget.summary() if result.budget else None,
        layers=result.layer_contents,
        prompt=result.prompt,
    )


@app.post("/api/patch/validate")
async def validate_patch(request: PatchValidateRequest):
    """
    Dry-run validate a patch plan against the current schematic.

    Returns validation results, affected components/nets, and delta summary
    without modifying any files. Frontend should call this before showing
    the Apply button.
    """
    service = get_context_service()
    schematic_path = request.schematic_path or service.session.schematic.path
    if not schematic_path:
        raise HTTPException(status_code=400, detail="No schematic loaded. Load a schematic first.")

    from hephaistus_circuit.errors import PatchPlanError
    try:
        result = validate_patch_plan(Path(schematic_path), request.patch_plan)
        return {
            "status": result["status"],
            "plan_id": result["plan_id"],
            "intent": result["intent"],
            "affected": result["affected"],
            "delta": result["delta"],
            "changes": result["changes"],
            "warnings": result["warnings"],
            "round_trip": result.get("round_trip"),
        }
    except PatchPlanError as e:
        return {
            "status": "rejected",
            "error_code": e.code,
            "message": e.message,
            "details": e.details,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@app.post("/api/patch/apply")
async def apply_patch(request: PatchApplyRequest):
    """
    Apply a validated patch plan to the current schematic.

    This modifies the .kicad_sch file on disk. The user must have
    reviewed the validation results before calling this endpoint.
    KiCad's .history/ git repo provides rollback capability.
    """
    service = get_context_service()
    schematic_path = request.schematic_path or service.session.schematic.path
    if not schematic_path:
        raise HTTPException(status_code=400, detail="No schematic loaded. Load a schematic first.")

    from hephaistus_circuit.errors import PatchPlanError
    try:
        result = apply_patch_plan(Path(schematic_path), request.patch_plan)

        # Re-parse the modified schematic to refresh session state
        parsed = parse_schematic(str(schematic_path))
        service.initialize_session(
            schematic_path=str(schematic_path),
            parsed_state=parsed,
        )
        _save_session()

        return {
            "status": result["status"],
            "plan_id": result["plan_id"],
            "intent": result["intent"],
            "affected": result["affected"],
            "delta": result["delta"],
            "changes": result["changes"],
            "warnings": result["warnings"],
            "round_trip": result.get("round_trip"),
            "schematic_path": str(schematic_path),
        }
    except PatchPlanError as e:
        return {
            "status": "rejected",
            "error_code": e.code,
            "message": e.message,
            "details": e.details,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apply failed: {str(e)}")


@app.get("/api/history/search", response_model=HistorySearchResponse)
async def search_history(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100),
    session: Optional[str] = None,
):
    """
    Search conversation history.
    
    Uses FTS5 full-text search across requests, responses, and reasoning.
    """
    store = get_history_store()
    results = store.search(query=q, limit=limit, session_id=session)
    
    return HistorySearchResponse(
        entries=[{
            "id": r.entry.id,
            "session_id": r.entry.session_id,
            "timestamp": r.entry.timestamp.isoformat(),
            "user_request": r.entry.user_request,
            "user_action": r.entry.user_action,
            "relevance_score": r.relevance_score,
            "match_type": r.match_type,
        } for r in results],
    )


@app.get("/api/history/recent", response_model=HistorySearchResponse)
async def get_recent_history(
    limit: int = Query(20, ge=1, le=100),
    session: Optional[str] = None,
):
    """
    Get recent history entries.
    """
    store = get_history_store()
    entries = store.get_recent(limit=limit, session_id=session)
    
    return HistorySearchResponse(
        entries=[{
            "id": e.id,
            "session_id": e.session_id,
            "timestamp": e.timestamp.isoformat(),
            "user_request": e.user_request,
            "llm_response": e.llm_response,
            "reasoning_summary": e.reasoning_summary,
            "patch_plan_json": e.patch_plan_json,
            "user_action": e.user_action,
            "context_tokens": e.context_tokens,
            "response_tokens": e.response_tokens,
        } for e in entries],
    )


@app.get("/api/history/stats")
async def get_history_stats(session: Optional[str] = None):
    """
    Get history statistics.
    """
    store = get_history_store()
    stats = store.get_statistics(session_id=session)
    return stats


@app.get("/api/debug/last-prompt")
async def get_last_prompt():
    """
    Get the last assembled prompt+context for debugging.
    
    Returns the contents of .hephaistus/last_prompt.json from the current project.
    """
    global _project_root
    if not _project_root:
        raise HTTPException(status_code=404, detail="No project loaded")
    
    debug_file = _project_root / '.hephaistus' / 'last_prompt.json'
    if not debug_file.exists():
        raise HTTPException(status_code=404, detail="No last prompt file found")
    
    import json
    with open(debug_file) as f:
        return json.load(f)


# Development server entry point

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def run_server():
    """Entry point for hephaistus-api CLI command."""
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)