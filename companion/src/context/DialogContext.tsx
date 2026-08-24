import { createContext, useContext, useState, ReactNode } from 'react'

interface DialogContext {
  showLoadDialog: boolean
  setShowLoadDialog: (show: boolean) => void
  showClearConfirm: boolean
  setShowClearConfirm: (show: boolean) => void
  pendingClearHistory: (() => void) | null
  setPendingClearHistory: (fn: (() => void) | null) => void
}

const DialogContext = createContext<DialogContext | null>(null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [pendingClearHistory, setPendingClearHistory] = useState<(() => void) | null>(null)

  return (
    <DialogContext.Provider value={{
      showLoadDialog,
      setShowLoadDialog,
      showClearConfirm,
      setShowClearConfirm,
      pendingClearHistory,
      setPendingClearHistory,
    }}>
      {children}
    </DialogContext.Provider>
  )
}

export function useDialog() {
  const context = useContext(DialogContext)
  if (!context) {
    throw new Error('useDialog must be used within DialogProvider')
  }
  return context
}