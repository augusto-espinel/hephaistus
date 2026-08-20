"""
HephAIstus Companion API Server.

FastAPI server that wires backend modules to HTTP endpoints
for the React companion UI.
"""

import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Backend modules
from hephaistus_context import (
    ContextService,
    SessionPersistence,
    HistoryStore,
    SimulationStatus,
)
from hephaistus_circuit import parse_schematic
from hephaistus_llm import LLMOrchestrator, ProviderConfig


# Application
app = FastAPI(
    title="HephAIstus Companion API",
    description="Backend API for the HephAIstus companion UI",
    version="0.1.0",
)

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
_context_service: Optional[ContextService] = None
_history_store: Optional[HistoryStore] = None
_session_persistence: Optional[SessionPersistence] = None
_current_schematic: Optional[Path] = None
_schematic_hash: Optional[str] = None


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
    """Get or create the global history store."""
    global _history_store
    if _history_store is None:
        _history_store = HistoryStore()
    return _history_store


# Endpoints

@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "hephaistus-companion-api"}


@app.get("/api/schematic/state", response_model=SchematicStateResponse)
async def get_schematic_state():
    """
    Get current schematic state.
    
    Returns component/net counts, directives, and unsaved status.
    """
    global _current_schematic, _schematic_hash
    
    service = get_context_service()
    session = service.session
    
    # Check if schematic file still exists and hasn't changed
    has_unsaved = False
    if _current_schematic and _current_schematic.exists():
        current_hash = service.session.schematic.compute_hash()
        if _schematic_hash and current_hash != _schematic_hash:
            # File was modified externally (e.g., saved in KiCad)
            _schematic_hash = current_hash
            has_unsaved = False
        elif session.schematic.path:
            # Session has schematic but we need to check if KiCad saved it
            # For now, we assume file is saved (user workflow responsibility)
            has_unsaved = False
    else:
        has_unsaved = bool(session.schematic.path and not session.schematic.hash)
    
    return SchematicStateResponse(
        path=session.schematic.path or None,
        hash=session.schematic.hash or None,
        component_count=session.schematic.component_count,
        net_count=session.schematic.net_count,
        components=session.schematic.components[:25],  # Limit for UI
        nets=[{"name": n.get("name"), "pins": n.get("pins", [])} for n in session.schematic.nets[:10]],
        directives=[{"type": d.get("directive_type"), "text": d.get("text")} for d in session.schematic.directives],
        last_modified=session.schematic.last_modified.isoformat() if session.schematic.last_modified else None,
        has_unsaved_changes=has_unsaved,
    )


@app.post("/api/schematic/load")
async def load_schematic(path: str):
    """
    Load a schematic file.
    
    Parses the .kicad_sch file and updates session state.
    """
    global _current_schematic, _schematic_hash
    
    schematic_path = Path(path)
    if not schematic_path.exists():
        raise HTTPException(status_code=404, detail=f"Schematic not found: {path}")
    
    try:
        # Parse schematic
        parsed = parse_schematic(str(schematic_path))
        
        # Update context service
        service = get_context_service()
        service.initialize_session(
            schematic_path=str(schematic_path),
            parsed_state=parsed,
        )
        
        # Track for unsaved changes detection
        _current_schematic = schematic_path
        _schematic_hash = service.session.schematic.hash
        
        return {
            "status": "loaded",
            "path": str(schematic_path),
            "components": service.session.schematic.component_count,
            "nets": service.session.schematic.net_count,
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
        )
    else:
        config = ProviderConfig.ollama(
            model=request.model or "llama3.1:70b",
        )
    
    # Create orchestrator
    orchestrator = LLMOrchestrator(provider_config=config)
    
    # Generate
    try:
        proposal = orchestrator.generate(
            user_request=request.request,
            include_full_simulation=request.include_full_simulation,
        )
        
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
            "reasoning_summary": e.reasoning_summary,
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


# Development server entry point

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


def run_server():
    """Entry point for hephaistus-api CLI command."""
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)