import { useState } from 'react'

interface LoadSchematicDialogProps {
  isOpen: boolean
  onClose: () => void
  onLoad: (path: string) => Promise<void>
  loading?: boolean
  error?: string | null
}

export function LoadSchematicDialog({
  isOpen,
  onClose,
  onLoad,
  loading,
  error
}: LoadSchematicDialogProps) {
  const [path, setPath] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async () => {
    setLocalError(null)

    if (!path.trim()) {
      setLocalError('Please enter a schematic file path')
      return
    }

    if (!path.endsWith('.kicad_sch')) {
      setLocalError('File must be a .kicad_sch file')
      return
    }

    try {
      await onLoad(path.trim())
      // Close dialog immediately after successful load
      // Parent will handle cleanup (clear history, etc.)
      setPath('')
      onClose()
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Failed to load schematic')
    }
  }

  const handleFileSelect = () => {
    // Note: In Tauri, we'd use the native file picker
    // For now, user manually enters the path
    const selected = prompt('Enter path to .kicad_sch file:')
    if (selected) {
      setPath(selected)
    }
  }

  return (
    <div className="dialog-overlay">
      <div className="dialog load-schematic-dialog">
        <div className="dialog-header">
          <h3>Load Schematic</h3>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="dialog-body">
          <p className="dialog-description">
            Load a KiCad schematic file. The schematic must be saved in KiCad first.
          </p>

          <div className="form-section">
            <label>
              <span className="label-text">Schematic File Path</span>
              <span className="label-hint">(.kicad_sch file)</span>
            </label>
            <div className="input-with-button">
              <input
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/path/to/project/schematic.kicad_sch"
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
            disabled={loading || !path.trim()}
          >
            {loading ? 'Loading...' : 'Load'}
          </button>
        </div>
      </div>
    </div>
  )
}