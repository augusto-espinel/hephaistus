import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ContextInspector } from './pages/ContextInspector'
import { PatchPlanDiff } from './pages/PatchPlanDiff'
import { HistoryBrowser } from './pages/HistoryBrowser'
import { SchematicView } from './pages/SchematicView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<SchematicView />} />
          <Route path="context" element={<ContextInspector />} />
          <Route path="diff" element={<PatchPlanDiff />} />
          <Route path="history" element={<HistoryBrowser />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}