import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useState, useCallback } from 'react'
import { Layout } from './components/Layout'
import { Chat } from './pages/Chat'
import { ContextInspector } from './pages/ContextInspector'
import { PatchPlanDiff } from './pages/PatchPlanDiff'
import { HistoryBrowser } from './pages/HistoryBrowser'
import { Settings } from './pages/Settings'
import { AppProvider, useAppState } from './context/AppContext'
import { useSession } from './hooks/useSession'

function AppInner() {
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const { setLastResponse, setLastContext, fetchHistory } = useAppState()
  const { clearHistory, clearLoading } = useSession()

  const handleLoadSchematic = useCallback(() => {
    setShowLoadDialog(true)
  }, [])

  const handleClearHistory = useCallback(async () => {
    if (!confirm('Clear all design history for this project?\n\nThis will remove all previous prompts and responses. You can start fresh on this circuit.')) {
      return
    }
    try {
      await clearHistory()
      setLastResponse(null)
      setLastContext(null) // Clear context inspector
      fetchHistory()
    } catch (err) {
      console.error('Failed to clear history:', err)
    }
  }, [clearHistory, setLastResponse, setLastContext, fetchHistory])

  return (
    <Routes>
      <Route path="/" element={
        <Layout 
          onLoadSchematic={handleLoadSchematic}
          onClearHistory={handleClearHistory}
          clearLoading={clearLoading}
        />
      }>
        <Route index element={
          <Chat 
            showLoadDialog={showLoadDialog}
            onLoadDialogClose={() => setShowLoadDialog(false)}
          />
        } />
        <Route path="context" element={<ContextInspector />} />
        <Route path="diff" element={<PatchPlanDiff />} />
        <Route path="history" element={<HistoryBrowser />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <AppInner />
      </AppProvider>
    </BrowserRouter>
  )
}
