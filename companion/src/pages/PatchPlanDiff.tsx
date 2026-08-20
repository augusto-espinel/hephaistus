import { useState } from 'react'
import { useApi } from '@/hooks/useApi'
import { DiffView } from '@/components/DiffView'
import type { PatchPlan } from '@/services/patch'

export function PatchPlanDiff() {
  const [request, setRequest] = useState('')
  const { data, loading, error, execute } = useApi<{ proposal: PatchPlan }>()

  const handleGenerate = async () => {
    await execute('/api/llm/generate', {
      method: 'POST',
      body: JSON.stringify({ request }),
    })
  }

  return (
    <div className="patch-plan-diff">
      <div className="page-header">
        <h1>Patch-Plan Diff View</h1>
        <p className="page-description">
          See exactly what changes will be applied before accepting them.
        </p>
      </div>

      <div className="request-panel">
        <div className="input-group">
          <label htmlFor="request">Modification Request</label>
          <textarea
            id="request"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
            placeholder="e.g., Add a snubber circuit across D1"
            rows={3}
          />
        </div>
        <button onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generating...' : 'Generate Patch-Plan'}
        </button>
      </div>

      {error && (
        <div className="error-panel">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {data?.proposal && (
        <div className="diff-panel">
          <DiffView patchPlan={data.proposal} />
          <div className="actions">
            <button className="accept">Apply Changes</button>
            <button className="reject">Reject</button>
            <button className="modify">Modify</button>
          </div>
        </div>
      )}
    </div>
  )
}