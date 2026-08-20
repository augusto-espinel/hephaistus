import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Chat } from './pages/Chat'
import { ContextInspector } from './pages/ContextInspector'
import { PatchPlanDiff } from './pages/PatchPlanDiff'
import { HistoryBrowser } from './pages/HistoryBrowser'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Chat />} />
          <Route path="context" element={<ContextInspector />} />
          <Route path="diff" element={<PatchPlanDiff />} />
          <Route path="history" element={<HistoryBrowser />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}