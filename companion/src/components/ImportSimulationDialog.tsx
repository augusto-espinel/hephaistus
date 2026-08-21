import { useState } from 'react'

interface ImportSimulationDialogProps {
  isOpen: boolean
  onClose: () => void
  onImport: (csvPath: string | null, consoleText: string | null) => Promise<void>
  loading?: boolean
  error?: string | null
}

export function ImportSimulationDialog({ 
  isOpen, 
  onClose, 
  onImport, 
  loading,
  error 
}: ImportSimulationDialogProps) {
  const [csvPath, setCsvPath] = useState('')
  const [consoleText, setConsoleText] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async () => {
    setLocalError(null)

    const hasCsv = csvPath.trim().length > 0
    const hasConsole = consoleText.trim().length > 0

    if (!hasCsv && !hasConsole) {
      setLocalError('Provide either a CSV path or console output (or both)')
      return
    }

    try {
      await onImport(
        hasCsv ? csvPath.trim() : null,
        hasConsole ? consoleText.trim() : null
      )
      // Reset on success
      setCsvPath('')
      setConsoleText('')
      onClose()
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Import failed')
    }
  }

  const handleFileSelect = async () => {
    // Note: In a Tauri/desktop app, we'd use the native file picker
    // For now, user manually enters the path
    // Future: Use Tauri dialog API
    setCsvPath(prompt('Enter CSV file path:') || csvPath)
  }

  return (
    <div className="dialog-overlay">
      <div className="dialog import-simulation-dialog">
        <div className="dialog-header">
          <h3>Import Simulation Results</h3>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="dialog-body">
          <p className="dialog-description">
            KiCad simulations run in-memory and aren't automatically saved.
            Export your results and import them here.
          </p>

          <div className="form-section">
            <label>
              <span className="label-text">CSV Export Path</span>
              <span className="label-hint">(from KiCad: File → Export current plot as CSV)</span>
            </label>
            <div className="input-with-button">
              <input
                type="text"
                value={csvPath}
                onChange={(e) => setCsvPath(e.target.value)}
                placeholder="/path/to/simulation.csv"
                disabled={loading}
              />
              <button 
                type="button"
                onClick={handleFileSelect}
                disabled={loading}
              >
                Browse...
              </button>
            </div>
          </div>

          <div className="form-section">
            <label>
              <span className="label-text">Console Output</span>
              <span className="label-hint">(paste from ngspice console)</span>
            </label>
            <textarea
              value={consoleText}
              onChange={(e) => setConsoleText(e.target.value)}
              placeholder="Circuit: * rectifier
Doing analysis at TEMP = 27.000000
...
Operating point information:
V(out) = 12.000000"
              rows={8}
              disabled={loading}
            />
          </div>

          {(error || localError) && (
            <div className="error-message">
              {error || localError}
            </div>
          )}
        </div>

        <div className="dialog-footer">
          <button 
            className="cancel-button"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button 
            className="submit-button"
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? 'Importing...' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  )
}