"""
FIFO archive management for simulation runs.

Keeps the last N simulation runs in history, deleting older runs
when the limit is exceeded.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .run_metadata import RunMetadata


# Default maximum number of historical runs to keep
DEFAULT_MAX_HISTORY = 5


class SimulationArchive:
    """
    Manages FIFO archive of simulation runs.
    
    Directory structure:
        <project>/.hephaistus/simulations/
        ├── current/           # Active simulation
        │   ├── run_metadata.json
        │   ├── console.txt
        │   └── waveform.csv
        └── history/           # Archived runs (FIFO)
            ├── 2026-08-21T22-00-00/
            │   ├── run_metadata.json
            │   ├── console.txt
            │   └── waveform.csv
            └── ...
    """
    
    def __init__(self, project_root: str, max_history: int = DEFAULT_MAX_HISTORY):
        """
        Initialize archive for a project.
        
        Args:
            project_root: Path to KiCad project directory
            max_history: Maximum number of historical runs to keep
        """
        self.project_root = Path(project_root)
        self.simulations_dir = self.project_root / ".hephaistus" / "simulations"
        self.current_dir = self.simulations_dir / "current"
        self.history_dir = self.simulations_dir / "history"
        self.max_history = max_history
    
    def _ensure_dirs(self) -> None:
        """Ensure archive directories exist."""
        self.simulations_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def archive_current(self) -> Optional[str]:
        """
        Archive the current simulation to history.
        
        Returns:
            Path to archived run, or None if no current run exists
        """
        self._ensure_dirs()
        
        if not self.current_dir.exists():
            return None
        
        # Check if current has any content
        if not any(self.current_dir.iterdir()):
            return None
        
        # Generate timestamp-based folder name
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        archive_path = self.history_dir / timestamp
        
        # Move current to history
        shutil.move(str(self.current_dir), str(archive_path))
        
        # Prune old archives
        self._prune_history()
        
        return str(archive_path)
    
    def save_current(
        self,
        metadata: RunMetadata,
        console_text: Optional[str] = None,
        csv_path: Optional[str] = None,
    ) -> str:
        """
        Save simulation data as the current run.
        
        Args:
            metadata: Run metadata
            console_text: Optional console output text
            csv_path: Optional path to CSV file (will be copied)
        
        Returns:
            Path to current run directory
        """
        self._ensure_dirs()
        
        # Clear current directory
        if self.current_dir.exists():
            shutil.rmtree(self.current_dir)
        self.current_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata_path = self.current_dir / "run_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
        
        # Save console output
        if console_text:
            console_path = self.current_dir / "console.txt"
            with open(console_path, 'w') as f:
                f.write(console_text)
        
        # Copy CSV file
        if csv_path and Path(csv_path).exists():
            dest = self.current_dir / "waveform.csv"
            shutil.copy2(csv_path, dest)
        
        return str(self.current_dir)
    
    def load_current(self) -> Optional[RunMetadata]:
        """
        Load metadata for the current simulation.
        
        Returns:
            RunMetadata or None if no current run
        """
        metadata_path = self.current_dir / "run_metadata.json"
        
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r') as f:
            data = json.load(f)
        
        return RunMetadata.from_dict(data)
    
    def load_current_console(self) -> Optional[str]:
        """Load console output for current run."""
        console_path = self.current_dir / "console.txt"
        
        if not console_path.exists():
            return None
        
        with open(console_path, 'r') as f:
            return f.read()
    
    def load_current_csv(self) -> Optional[str]:
        """
        Get path to CSV file for current run.
        
        Returns:
            Path to CSV or None if not present
        """
        csv_path = self.current_dir / "waveform.csv"
        
        if csv_path.exists():
            return str(csv_path)
        
        return None
    
    def list_history(self) -> List[RunMetadata]:
        """
        List all historical runs.
        
        Returns:
            List of RunMetadata, newest first
        """
        if not self.history_dir.exists():
            return []
        
        runs = []
        for run_dir in sorted(self.history_dir.iterdir(), reverse=True):
            metadata_path = run_dir / "run_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                runs.append(RunMetadata.from_dict(data))
        
        return runs
    
    def get_history_path(self, run_id: str) -> Optional[Path]:
        """
        Get path to a historical run by ID.
        
        Args:
            run_id: Run ID to find
        
        Returns:
            Path to run directory or None
        """
        for run_dir in self.history_dir.iterdir():
            metadata_path = run_dir / "run_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                if data.get('run_id') == run_id:
                    return run_dir
        
        return None
    
    def clear_current(self) -> None:
        """Clear the current simulation."""
        if self.current_dir.exists():
            shutil.rmtree(self.current_dir)
    
    def clear_history(self) -> None:
        """Clear all historical simulations."""
        if self.history_dir.exists():
            shutil.rmtree(self.history_dir)
            self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def _prune_history(self) -> None:
        """Remove oldest runs if exceeding max_history."""
        if not self.history_dir.exists():
            return
        
        # Get all run directories sorted by name (timestamp)
        runs = sorted(self.history_dir.iterdir())
        
        # Remove oldest if over limit
        while len(runs) > self.max_history:
            oldest = runs.pop(0)
            shutil.rmtree(oldest)
    
    def get_run_count(self) -> int:
        """Get number of historical runs."""
        if not self.history_dir.exists():
            return 0
        return len(list(self.history_dir.iterdir()))
    
    def get_total_size(self) -> int:
        """Get total size of simulations directory in bytes."""
        if not self.simulations_dir.exists():
            return 0
        
        total = 0
        for path in self.simulations_dir.rglob('*'):
            if path.is_file():
                total += path.stat().st_size
        
        return total