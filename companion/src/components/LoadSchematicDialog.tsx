import { useState, useEffect, useRef } from 'react'

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
  const [visible, setVisible] = useState(false)
  const closingRef = useRef(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Sync visible state with isOpen prop
  useEffect(() => {
    if (isOpen && !closingRef.current) {
      setVisible(true)
    }
  }, [isOpen])

  // Focus input when dialog opens
  useEffect(() => {
    if (visible && inputRef.current) {
      inputRef.current.focus()
    }
  }, [visible])

  // Handle close with proper state cleanup
  const handleClose = () => {
    closingRef.current = true
    setVisible(false)
    // Call parent's onClose after animation starts
    setTimeout(() => {
      onClose()
      closingRef.current = false
    }, 50)
  }

  // Reset form state when dialog closes
  useEffect(() => {
    if (!visible) {
      const timer = setTimeout(() => {
        setPath('')
        setLocalError(null)
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [visible])

  if (!visible) return null

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    
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
      // Close dialog after successful load
      handleClose()
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Failed to load schematic')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !loading && path.trim()) {
      handleSubmit()
    }
    if (e.key === 'Escape') {
      handleClose()
    }
  }

  const handleOverlayClick = (e: React.MouseEvent) => {
    // Only close if clicking the overlay, not the dialog content
    if (e.target === e.currentTarget) {
      handleClose()
    }
  }

  return (
    <div className="dialog-overlay" onClick={handleOverlayClick}>
      <div 
        className="dialog load-schematic-dialog" 
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="dialog-header">
          <h3>Load Schematic</h3>
          <button className="close-button" onClick={handleClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="dialog-body">
            <p className="dialog-description">
              Load a KiCad schematic file. The schematic must be saved in KiCad first.
            </p>

            <div className="form-section">
              <label>
                <span className="label-text">Schematic File Path</span>
                <span className="label-hint">(.kicad_sch file)</span>
              </label>
              <input
                ref={inputRef}
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/path/to/project/schematic.kicad_sch"
                disabled={loading}
                onKeyDown={handleKeyDown}
              />
              <p className="input-hint">
                Tip: Copy the file path from KiCad's title bar or Finder
              </p>
            </div>

            {(error || localError) && (
              <div className="error-message">
                {error || localError}
              </div>
            )}
          </div>

          <div className="dialog-footer">
            <button
              type="button"
              className="cancel-button"
              onClick={handleClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="submit-button"
              disabled={loading || !path.trim()}
            >
              {loading ? 'Loading...' : 'Load'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}