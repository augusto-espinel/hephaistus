"""Simulation output parsing and context assembly for HephAIstus."""

from .parser import (
    parse_ngspice_output,
    parse_dc_op_points,
    parse_waveform_raw,
    parse_console_output,
)
from .run_metadata import (
    SimulationRun,
    RunMetadata,
    CorrelationStatus,
)
from .context import (
    SimulationContext,
    assemble_context,
)
from .waveform import (
    WaveformConfig,
    WaveformSummary,
    summarize_waveform,
    summarize_waveforms,
    format_summary_for_context,
    format_summaries_for_context,
)

__all__ = [
    # Parsing
    "parse_ngspice_output",
    "parse_dc_op_points",
    "parse_waveform_raw",
    "parse_console_output",
    # Run metadata
    "SimulationRun",
    "RunMetadata",
    "CorrelationStatus",
    # Context assembly
    "SimulationContext",
    "assemble_context",
    # Waveform processing
    "WaveformConfig",
    "WaveformSummary",
    "summarize_waveform",
    "summarize_waveforms",
    "format_summary_for_context",
    "format_summaries_for_context",
]