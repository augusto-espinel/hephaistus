"""
Simulation data ingestion for HephAIstus.

Handles importing CSV waveforms and console output from user-provided files.
KiCad does not persist simulation data, so users must export manually.
"""

import csv
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from .parser import parse_console_output, parse_dc_op_points
from .run_metadata import RunMetadata, CorrelationStatus


@dataclass
class IngestedSimulation:
    """Result of ingesting simulation data."""
    run_id: str
    timestamp: datetime
    analysis_type: str
    schematic_hash: str
    schematic_path: str
    converged: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    op_points: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    signal_count: int = 0
    sample_count: int = 0
    signal_summaries: List[Dict[str, Any]] = field(default_factory=list)
    csv_path: Optional[str] = None
    console_path: Optional[str] = None


@dataclass
class WaveformSummary:
    """Summary statistics for a signal."""
    name: str
    min: float
    max: float
    mean: float
    std: float
    initial: float
    final: float
    sample_count: int


def ingest_simulation(
    schematic_path: str,
    schematic_hash: str,
    csv_path: Optional[str] = None,
    console_text: Optional[str] = None,
    console_path: Optional[str] = None,
) -> IngestedSimulation:
    """
    Ingest simulation data from CSV and/or console output.
    
    Args:
        schematic_path: Path to the schematic file
        schematic_hash: Hash of the schematic for freshness tracking
        csv_path: Optional path to exported CSV waveform file
        console_text: Optional console output text (pasted by user)
        console_path: Optional path to console output file
    
    Returns:
        IngestedSimulation with parsed data
    """
    import uuid
    
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc)
    
    # Initialize result
    result = IngestedSimulation(
        run_id=run_id,
        timestamp=timestamp,
        analysis_type="unknown",
        schematic_hash=schematic_hash,
        schematic_path=schematic_path,
        converged=True,
        csv_path=csv_path,
        console_path=console_path,
    )
    
    # Parse console output if provided
    if console_text:
        _parse_console(console_text, result)
    elif console_path and Path(console_path).exists():
        with open(console_path, 'r') as f:
            _parse_console(f.read(), result)
    
    # Parse CSV if provided
    if csv_path and Path(csv_path).exists():
        _parse_csv(csv_path, result)
    
    return result


def _parse_console(text: str, result: IngestedSimulation) -> None:
    """Parse ngspice console output and update result."""
    parsed = parse_console_output(text)
    
    # Extract analysis type
    if parsed.analyses:
        analysis = parsed.analyses[0]
        result.analysis_type = analysis.analysis_type
    
    # Convergence status
    if parsed.convergence:
        result.converged = parsed.convergence.converged
    
    # Warnings and errors
    result.warnings = parsed.warnings
    result.errors = parsed.errors
    
    # DC operating points (if present in raw output)
    # Note: op_points would need additional parsing
    # For now, we just store the raw console output


def _parse_csv(csv_path: str, result: IngestedSimulation) -> None:
    """Parse ngspice CSV export and update result."""
    import statistics
    
    try:
        with open(csv_path, 'r') as f:
            # Auto-detect delimiter (ngspice can use ; or ,)
            sample = f.read(1024)
            f.seek(0)
            delimiter = ';' if ';' in sample.split('\n')[0] else ','
            
            reader = csv.reader(f, delimiter=delimiter)
            headers = next(reader, None)
            
            if not headers:
                return
            
            # Clean headers (remove empty strings from trailing delimiter)
            headers = [h.strip() for h in headers if h.strip()]
            result.signals = headers
            result.signal_count = len(result.signals)
            
            # Read ALL values for summary computation
            all_values = {h: [] for h in headers}
            sample_count = 0
            
            for row in reader:
                sample_count += 1
                for i, h in enumerate(headers):
                    if i < len(row):
                        try:
                            all_values[h].append(float(row[i]))
                        except (ValueError, IndexError):
                            pass
            
            # Detect analysis type from CSV signal names
            if not result.analysis_type or result.analysis_type == 'unknown':
                signal_str = ' '.join(headers).lower()
                if 'time' in signal_str:
                    result.analysis_type = 'tran'
                elif 'frequency' in signal_str or 'freq' in signal_str:
                    result.analysis_type = 'ac'
                elif 'sweep' in signal_str:
                    result.analysis_type = 'dc'
            
            result.sample_count = sample_count
            
            # Compute signal summaries for voltage/current signals
            for name, values in all_values.items():
                if name.lower() == 'time' or not values:
                    continue
                
                # Filter out invalid values
                valid_values = [v for v in values if isinstance(v, (int, float))]
                if not valid_values:
                    continue
                
                # Only include V() or I() signals to keep context focused
                if name.startswith('V(') or name.startswith('I('):
                    summary = {
                        'name': name,
                        'min': min(valid_values),
                        'max': max(valid_values),
                        'mean': statistics.mean(valid_values),
                        'initial': valid_values[0],
                        'final': valid_values[-1],
                        'samples': len(valid_values),
                    }
                    # Compute std only if we have enough samples
                    if len(valid_values) > 1:
                        summary['std'] = statistics.stdev(valid_values)
                    
                    result.signal_summaries.append(summary)
                    
    except Exception as e:
        result.errors.append(f"CSV parse error: {str(e)}")


def summarize_waveform(
    csv_path: str,
    signal_name: str,
    max_samples: int = 10000,
) -> Optional[WaveformSummary]:
    """
    Compute summary statistics for a single signal from CSV.
    
    Args:
        csv_path: Path to CSV file
        signal_name: Name of signal to summarize
        max_samples: Maximum samples to read (for large files)
    
    Returns:
        WaveformSummary or None if signal not found
    """
    import statistics
    
    try:
        with open(csv_path, 'r') as f:
            # Auto-detect delimiter
            sample = f.read(1024)
            f.seek(0)
            delimiter = ';' if ';' in sample.split('\n')[0] else ','
            
            reader = csv.reader(f, delimiter=delimiter)
            headers = next(reader, None)
            
            if not headers:
                return None
            
            # Find signal index
            headers = [h.strip() for h in headers]
            try:
                idx = headers.index(signal_name)
            except ValueError:
                return None
            
            # Read values
            values = []
            count = 0
            for row in reader:
                if count >= max_samples:
                    break
                if len(row) > idx:
                    try:
                        values.append(float(row[idx]))
                        count += 1
                    except (ValueError, IndexError):
                        pass
            
            if not values:
                return None
            
            # Compute statistics
            return WaveformSummary(
                name=signal_name,
                min=min(values),
                max=max(values),
                mean=statistics.mean(values),
                std=statistics.stdev(values) if len(values) > 1 else 0.0,
                initial=values[0],
                final=values[-1],
                sample_count=len(values),
            )
            
    except Exception:
        return None


def detect_analysis_type(console_text: str) -> str:
    """Detect analysis type from console output."""
    text = console_text.lower()
    
    if '.tran' in text or 'transient' in text:
        return 'tran'
    elif '.ac' in text or 'ac analysis' in text:
        return 'ac'
    elif '.dc' in text or 'dc sweep' in text:
        return 'dc'
    elif '.op' in text or 'operating point' in text:
        return 'op'
    else:
        return 'unknown'


def strip_spice_comments(lib_content: str) -> str:
    """
    Strip comments from SPICE library content.
    
    Removes lines starting with * (comments) while preserving
    all circuit definitions (.MODEL, .SUBCKT, components).
    
    Args:
        lib_content: Raw SPICE library content
    
    Returns:
        Content with comments stripped
    """
    lines = lib_content.split('\n')
    stripped = []
    
    for line in lines:
        # Preserve non-empty lines that don't start with *
        stripped_line = line.strip()
        if stripped_line and not stripped_line.startswith('*'):
            stripped.append(line)
    
    return '\n'.join(stripped)


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def to_run_metadata(ingested: IngestedSimulation) -> RunMetadata:
    """Convert IngestedSimulation to RunMetadata."""
    return RunMetadata(
        run_id=ingested.run_id,
        timestamp=ingested.timestamp,
        analysis_type=ingested.analysis_type,
        schematic_path=ingested.schematic_path,
        schematic_hash=ingested.schematic_hash,
        schematic_modified=ingested.timestamp,
        converged=ingested.converged,
        error_type=None if ingested.converged else "simulation_failed",
        error_message="; ".join(ingested.errors) if ingested.errors else None,
        console_output_path=ingested.console_path,
        raw_file_path=ingested.csv_path,
    )