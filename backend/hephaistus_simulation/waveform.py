"""
Waveform post-processing for LLM context efficiency.

Provides summary statistics, key point extraction, and trend detection
to minimize token usage while preserving essential information.
"""

import statistics
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class WaveformConfig:
    """Configuration for waveform context generation."""
    
    # Raw data limits
    max_raw_points: int = 100  # Max points if raw data included
    max_signals: int = 10  # Max signals in context
    
    # Summary statistics (always included)
    include_stats: bool = True  # min, max, mean, std, final
    include_trend: bool = True  # settling, oscillating, rising, falling
    
    # Key points (configurable)
    include_final_n: int = 50  # Last N points (steady state)
    include_initial_n: int = 20  # First N points (initial transient)
    include_peaks: bool = True  # Local maxima/minima
    include_crossings: bool = True  # Zero/threshold crossings
    
    # Context budget
    max_total_chars: int = 20000  # Total chars for all signals
    
    # Threshold settings
    settling_threshold: float = 0.01  # 1% variation for settling
    overshoot_window: float = 0.1  # Last 10% for overshoot calculation


@dataclass
class WaveformSummary:
    """Summary of a single waveform."""
    
    name: str
    samples: int
    time_range: tuple  # (start, end)
    value_range: tuple  # (min, max)
    mean: float
    std: float
    initial: float
    final: float
    
    # Trend analysis
    trend: Optional[str] = None  # settling, oscillating, rising, falling, stable
    settling_time: Optional[float] = None
    overshoot: Optional[float] = None  # Percentage
    oscillation_freq: Optional[float] = None  # Hz if oscillating
    
    # Key points
    peaks: list = field(default_factory=list)  # [(t, v), ...]
    crossings: list = field(default_factory=list)  # [t, ...]
    
    # Raw data (only if requested)
    raw_data: Optional[dict] = None  # {time: [...], values: [...]}
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "samples": self.samples,
            "time_range": self.time_range,
            "value_range": self.value_range,
            "mean": self.mean,
            "std": self.std,
            "initial": self.initial,
            "final": self.final,
            "trend": self.trend,
            "settling_time": self.settling_time,
            "overshoot": self.overshoot,
            "oscillation_freq": self.oscillation_freq,
            "peaks": self.peaks,
            "crossings": self.crossings,
            "raw_data": self.raw_data,
        }


def detect_trend(time: list, values: list, settling_threshold: float = 0.01) -> str:
    """
    Detect signal trend: settling, oscillating, rising, falling, stable.
    
    Args:
        time: Time values
        values: Signal values
        settling_threshold: Relative variation threshold for settling
        
    Returns:
        Trend string
    """
    if len(values) < 10:
        return "unknown"
    
    # Calculate variation in last 10% of signal
    final_window = max(int(len(values) * 0.1), 5)
    final_values = values[-final_window:]
    final_mean = statistics.mean(final_values)
    final_var = statistics.stdev(final_values) if len(final_values) > 1 else 0
    
    # Check for settling (variation < threshold)
    if abs(final_var / final_mean) < settling_threshold if final_mean != 0 else final_var < settling_threshold:
        # Check if initial differs from final (settling)
        initial_mean = statistics.mean(values[:final_window])
        if abs(initial_mean - final_mean) / (abs(final_mean) + 1e-10) > settling_threshold:
            return "settling"
        return "stable"
    
    # Check for oscillation
    # Count zero crossings around mean
    mean_val = statistics.mean(values)
    crossings = 0
    for i in range(1, len(values)):
        if (values[i-1] - mean_val) * (values[i] - mean_val) < 0:
            crossings += 1
    
    # If many crossings, likely oscillating
    if crossings > len(values) * 0.1:
        return "oscillating"
    
    # Check for rising/falling
    # Compare first half to second half
    mid = len(values) // 2
    first_half_mean = statistics.mean(values[:mid])
    second_half_mean = statistics.mean(values[mid:])
    
    if second_half_mean > first_half_mean * 1.1:
        return "rising"
    elif second_half_mean < first_half_mean * 0.9:
        return "falling"
    
    return "unknown"


def estimate_settling_time(time: list, values: list, threshold: float = 0.01) -> Optional[float]:
    """
    Estimate time to settle within threshold of final value.
    
    Args:
        time: Time values
        values: Signal values
        threshold: Relative threshold (default 1%)
        
    Returns:
        Settling time in same units as time, or None if doesn't settle
    """
    if len(values) < 10:
        return None
    
    final_value = values[-1]
    tolerance = abs(final_value * threshold) if final_value != 0 else 0.01
    
    # Find last time outside tolerance
    for i in range(len(values) - 1, -1, -1):
        if abs(values[i] - final_value) > tolerance:
            if i < len(values) - 1:
                return time[i + 1]
            return None
    
    # Always within tolerance
    return time[0]


def calculate_overshoot(values: list, final_window: float = 0.1) -> Optional[float]:
    """
    Calculate overshoot percentage from final value.
    
    Args:
        values: Signal values
        final_window: Fraction of final points to average for final value
        
    Returns:
        Overshoot percentage, or None if can't calculate
    """
    if len(values) < 10:
        return None
    
    # Final value is average of last window
    final_n = max(int(len(values) * final_window), 5)
    final_value = statistics.mean(values[-final_n:])
    
    if final_value == 0:
        return None
    
    # Find peak deviation from final
    max_val = max(values)
    min_val = min(values)
    
    # Determine if overshoot or undershoot
    if final_value > 0:
        overshoot = ((max_val - final_value) / final_value) * 100
    else:
        overshoot = ((min_val - final_value) / abs(final_value)) * 100
    
    return max(0, overshoot)


def find_peaks(time: list, values: list, min_distance: int = 10) -> list:
    """
    Find local maxima and minima.
    
    Args:
        time: Time values
        values: Signal values
        min_distance: Minimum distance between peaks
        
    Returns:
        List of (time, value) tuples for peaks
    """
    if len(values) < 3:
        return []
    
    peaks = []
    
    for i in range(1, len(values) - 1):
        # Local maximum
        if values[i] > values[i-1] and values[i] > values[i+1]:
            # Check distance from last peak
            if not peaks or (time[i] - peaks[-1][0]) >= min_distance:
                peaks.append((time[i], values[i]))
        # Local minimum
        elif values[i] < values[i-1] and values[i] < values[i+1]:
            if not peaks or (time[i] - peaks[-1][0]) >= min_distance:
                peaks.append((time[i], values[i]))
    
    return peaks


def find_zero_crossings(time: list, values: list, threshold: float = 0.0) -> list:
    """
    Find zero crossings (or threshold crossings).
    
    Args:
        time: Time values
        values: Signal values
        threshold: Crossing threshold (default 0)
        
    Returns:
        List of crossing times
    """
    if len(values) < 2:
        return []
    
    crossings = []
    
    for i in range(1, len(values)):
        if (values[i-1] - threshold) * (values[i] - threshold) < 0:
            # Linear interpolation for crossing time
            t0, t1 = time[i-1], time[i]
            v0, v1 = values[i-1] - threshold, values[i] - threshold
            t_cross = t0 + (t1 - t0) * (-v0 / (v1 - v0)) if (v1 - v0) != 0 else t0
            crossings.append(t_cross)
    
    return crossings


def summarize_waveform(
    name: str,
    time: list,
    values: list,
    config: WaveformConfig = None,
) -> WaveformSummary:
    """
    Generate LLM-friendly waveform summary.
    
    Args:
        name: Signal name
        time: Time values
        values: Signal values
        config: Waveform configuration
        
    Returns:
        WaveformSummary with statistics and key points
    """
    config = config or WaveformConfig()
    
    # Basic statistics
    summary = WaveformSummary(
        name=name,
        samples=len(values),
        time_range=(time[0], time[-1]) if time else (0, 0),
        value_range=(min(values), max(values)) if values else (0, 0),
        mean=statistics.mean(values) if values else 0,
        std=statistics.stdev(values) if len(values) > 1 else 0,
        initial=values[0] if values else 0,
        final=values[-1] if values else 0,
    )
    
    # Trend analysis
    if config.include_trend:
        summary.trend = detect_trend(time, values, config.settling_threshold)
        summary.settling_time = estimate_settling_time(time, values, config.settling_threshold)
        summary.overshoot = calculate_overshoot(values, config.overshoot_window)
    
    # Key points
    if config.include_peaks:
        summary.peaks = find_peaks(time, values)
    
    if config.include_crossings:
        summary.crossings = find_zero_crossings(time, values)
    
    # Raw data (only if requested and within limits)
    if config.max_raw_points > 0 and len(values) <= config.max_raw_points:
        summary.raw_data = {
            "time": time,
            "values": values,
        }
    elif config.max_raw_points > 0:
        # Down-sample
        step = len(values) // config.max_raw_points
        summary.raw_data = {
            "time": time[::step],
            "values": values[::step],
        }
    
    return summary


def summarize_waveforms(
    signals: dict,
    config: WaveformConfig = None,
) -> dict:
    """
    Summarize multiple waveforms for LLM context.
    
    Args:
        signals: Dict of {signal_name: values} or {signal_name: {"time": [...], "values": [...]}}
        config: Waveform configuration
        
    Returns:
        Dict of {signal_name: WaveformSummary}
    """
    config = config or WaveformConfig()
    summaries = {}
    
    # Find time signal
    time = signals.get("time", [])
    if isinstance(time, dict):
        time = time.get("values", [])
    
    # Process each signal
    signal_names = [k for k in signals.keys() if k != "time"][:config.max_signals]
    
    for name in signal_names:
        values = signals[name]
        if isinstance(values, dict):
            values = values.get("values", [])
        
        if not values:
            continue
        
        # Use signal's own time if available
        signal_time = time if time else list(range(len(values)))
        
        summaries[name] = summarize_waveform(name, signal_time, values, config)
    
    return summaries


def format_summary_for_context(summary: WaveformSummary, config: WaveformConfig = None) -> str:
    """
    Format waveform summary for LLM context.
    
    Args:
        summary: Waveform summary
        config: Waveform configuration
        
    Returns:
        Formatted string for LLM context
    """
    config = config or WaveformConfig()
    lines = []
    
    lines.append(f"### {summary.name}")
    lines.append(f"  Range: [{summary.value_range[0]:.6e}, {summary.value_range[1]:.6e}]")
    lines.append(f"  Mean: {summary.mean:.6e}")
    
    if summary.std != 0:
        lines.append(f"  Std: {summary.std:.6e}")
    
    lines.append(f"  Initial: {summary.initial:.6e}")
    lines.append(f"  Final: {summary.final:.6e}")
    lines.append(f"  Samples: {summary.samples}")
    
    if summary.trend:
        lines.append(f"  Trend: {summary.trend}")
    
    if summary.settling_time is not None:
        lines.append(f"  Settling time: {summary.settling_time:.6e}")
    
    if summary.overshoot is not None and summary.overshoot > 0:
        lines.append(f"  Overshoot: {summary.overshoot:.1f}%")
    
    if summary.peaks:
        lines.append(f"  Peaks: {len(summary.peaks)} detected")
        if len(summary.peaks) <= 10:
            for t, v in summary.peaks:
                lines.append(f"    t={t:.6e}: {v:.6e}")
    
    if summary.crossings:
        lines.append(f"  Crossings: {len(summary.crossings)}")
        if len(summary.crossings) <= 10:
            lines.append(f"    Times: {', '.join(f'{t:.6e}' for t in summary.crossings[:10])}")
    
    return "\n".join(lines)


def format_summaries_for_context(summaries: dict, config: WaveformConfig = None) -> str:
    """
    Format multiple waveform summaries for LLM context.
    
    Args:
        summaries: Dict of {signal_name: WaveformSummary}
        config: Waveform configuration
        
    Returns:
        Formatted string for LLM context
    """
    lines = ["## Waveform Summary", ""]
    
    for name, summary in summaries.items():
        lines.append(format_summary_for_context(summary, config))
        lines.append("")
    
    # Add context efficiency note
    lines.append("## Simulation Context Efficiency")
    lines.append("Waveform data is summarized to preserve context.")
    lines.append("To request specific data, use:")
    lines.append("  - 'show raw v(out)' for full data")
    lines.append("  - 'show v(out) from 5ms to 10ms' for time range")
    lines.append("  - 'show peaks v(out)' for peak values")
    
    return "\n".join(lines)