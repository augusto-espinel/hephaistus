"""
Simulation run metadata and schematic correlation for HephAIstus.

Tracks simulation runs with timestamps, parameters, and schematic state
to enable context freshness detection and run comparison.
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum


class CorrelationStatus(Enum):
    """Status of simulation-to-schematic correlation."""
    CURRENT = "current"  # Simulation matches current schematic
    STALE = "stale"  # Schematic changed after simulation
    UNKNOWN = "unknown"  # Cannot determine correlation


@dataclass
class RunMetadata:
    """
    Metadata for a simulation run.
    
    Tracks the run's parameters, timing, and correlation with schematic state.
    """
    run_id: str
    timestamp: datetime
    analysis_type: str  # "tran", "ac", "dc", "op", etc.
    
    # Schematic correlation
    schematic_path: str
    schematic_hash: str  # SHA-256 of schematic file
    schematic_modified: datetime  # Last modification time
    
    # Simulation parameters
    parameters: dict = field(default_factory=dict)
    # Example for transient: {"stop": "10m", "step": "1u"}
    
    # Status
    converged: bool = True
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    
    # File references
    console_output_path: Optional[str] = None
    raw_file_path: Optional[str] = None
    op_file_path: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "analysis_type": self.analysis_type,
            "schematic_path": self.schematic_path,
            "schematic_hash": self.schematic_hash,
            "schematic_modified": self.schematic_modified.isoformat(),
            "parameters": self.parameters,
            "converged": self.converged,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "console_output_path": self.console_output_path,
            "raw_file_path": self.raw_file_path,
            "op_file_path": self.op_file_path,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RunMetadata":
        """Create from dict (e.g., loaded from JSON)."""
        return cls(
            run_id=data["run_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            analysis_type=data["analysis_type"],
            schematic_path=data["schematic_path"],
            schematic_hash=data["schematic_hash"],
            schematic_modified=datetime.fromisoformat(data["schematic_modified"]),
            parameters=data.get("parameters", {}),
            converged=data.get("converged", True),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
            console_output_path=data.get("console_output_path"),
            raw_file_path=data.get("raw_file_path"),
            op_file_path=data.get("op_file_path"),
        )


@dataclass
class SimulationRun:
    """
    Complete simulation run with parsed outputs.
    
    Combines metadata with parsed console, operating points, and waveform data.
    """
    metadata: RunMetadata
    correlation: CorrelationStatus = CorrelationStatus.UNKNOWN
    
    # Parsed outputs (loaded on demand)
    console_summary: Optional[dict] = None
    op_points: Optional[list] = None
    waveform_summary: Optional[dict] = None
    
    def is_current(self) -> bool:
        """Check if simulation matches current schematic state."""
        return self.correlation == CorrelationStatus.CURRENT
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "metadata": self.metadata.to_dict(),
            "correlation": self.correlation.value,
            "console_summary": self.console_summary,
            "op_points": self.op_points,
            "waveform_summary": self.waveform_summary,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SimulationRun":
        """Create from dict."""
        return cls(
            metadata=RunMetadata.from_dict(data["metadata"]),
            correlation=CorrelationStatus(data.get("correlation", "unknown")),
            console_summary=data.get("console_summary"),
            op_points=data.get("op_points"),
            waveform_summary=data.get("waveform_summary"),
        )


def compute_file_hash(filepath: Path) -> str:
    """
    Compute SHA-256 hash of a file.
    
    Args:
        filepath: Path to file
        
    Returns:
        Hex digest of SHA-256 hash
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_modified_time(filepath: Path) -> datetime:
    """
    Get file modification time as datetime.
    
    Args:
        filepath: Path to file
        
    Returns:
        Modification datetime
    """
    import os
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime)


def create_run_metadata(
    schematic_path: Path,
    analysis_type: str,
    parameters: dict,
    console_output_path: Optional[Path] = None,
    raw_file_path: Optional[Path] = None,
    op_file_path: Optional[Path] = None,
    converged: bool = True,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> RunMetadata:
    """
    Create metadata for a new simulation run.
    
    Args:
        schematic_path: Path to the .kicad_sch file
        analysis_type: Type of analysis (tran, ac, dc, op)
        parameters: Simulation parameters
        console_output_path: Optional path to console output file
        raw_file_path: Optional path to .raw waveform file
        op_file_path: Optional path to operating points file
        converged: Whether simulation converged
        error_type: Error type if not converged
        error_message: Error message if not converged
        
    Returns:
        RunMetadata object
    """
    import uuid
    
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now()
    
    schematic_hash = compute_file_hash(schematic_path)
    schematic_modified = get_file_modified_time(schematic_path)
    
    return RunMetadata(
        run_id=run_id,
        timestamp=timestamp,
        analysis_type=analysis_type,
        schematic_path=str(schematic_path),
        schematic_hash=schematic_hash,
        schematic_modified=schematic_modified,
        parameters=parameters,
        converged=converged,
        error_type=error_type,
        error_message=error_message,
        console_output_path=str(console_output_path) if console_output_path else None,
        raw_file_path=str(raw_file_path) if raw_file_path else None,
        op_file_path=str(op_file_path) if op_file_path else None,
    )


def check_correlation(run: RunMetadata, current_schematic_path: Path) -> CorrelationStatus:
    """
    Check if a simulation run is current with respect to schematic.
    
    Args:
        run: Simulation run metadata
        current_schematic_path: Path to current schematic
        
    Returns:
        CorrelationStatus indicating freshness
    """
    try:
        current_hash = compute_file_hash(current_schematic_path)
        if current_hash == run.schematic_hash:
            return CorrelationStatus.CURRENT
        else:
            return CorrelationStatus.STALE
    except Exception:
        return CorrelationStatus.UNKNOWN


def save_run_metadata(run: RunMetadata, output_path: Path) -> None:
    """
    Save run metadata to JSON file.
    
    Args:
        run: Run metadata to save
        output_path: Path to output JSON file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(run.to_dict(), f, indent=2)


def load_run_metadata(input_path: Path) -> RunMetadata:
    """
    Load run metadata from JSON file.
    
    Args:
        input_path: Path to JSON file
        
    Returns:
        RunMetadata object
    """
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RunMetadata.from_dict(data)