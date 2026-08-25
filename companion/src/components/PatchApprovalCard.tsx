import { useState } from 'react'
import { useApi } from '@/hooks/useApi'

interface PatchApprovalCardProps {
  patchPlan: { intent?: string; rationale?: string; operations?: unknown[] }
  onApplied?: () => void
}

interface ValidationResult {
  status: string
  plan_id?: string
  intent?: string
  affected?: {
    components: string[]
    nets: string[]
  }
  delta?: Record<string, unknown>
  changes?: string[]
  warnings?: string[]
  round_trip?: {
    parse_ok: boolean
    erc_exit?: number | null
  }
  error_code?: string
  message?: string
  details?: unknown
}

export function PatchApprovalCard({ patchPlan, onApplied }: PatchApprovalCardProps) {
  const [phase, setPhase] = useState<'idle' | 'validated' | 'applying' | 'applied' | 'rejected'>('idle')
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [expanded, setExpanded] = useState(false)

  const {
    execute: doValidate,
    loading: validating,
    error: validateError,
  } = useApi<ValidationResult>()

  const {
    execute: doApply,
    loading: applying,
    error: applyError,
  } = useApi<ValidationResult>()

  const handleValidate = async () => {
    const result = await doValidate('/api/patch/validate', {
      method: 'POST',
      body: JSON.stringify({ patch_plan: patchPlan }),
    })
    if (result) {
      setValidation(result)
      setPhase(result.status === 'validated' ? 'validated' : 'rejected')
    }
  }

  const handleApply = async () => {
    setPhase('applying')
    const result = await doApply('/api/patch/apply', {
      method: 'POST',
      body: JSON.stringify({ patch_plan: patchPlan }),
    })
    if (result) {
      if (result.status === 'applied') {
        setPhase('applied')
        setValidation(result)
        onApplied?.()
      } else {
        setPhase('rejected')
        setValidation(result)
      }
    }
  }

  const handleReject = () => {
    setPhase('idle')
    setValidation(null)
  }

  const operations = patchPlan.operations ?? []
  const intent = patchPlan.intent || 'Proposed schematic changes'
  const rationale = patchPlan.rationale

  const hasWarnings = validation?.warnings && validation.warnings.length > 0
  const hasErrors = validateError || applyError || validation?.status === 'rejected'

  return (
    <div className="patch-approval-card">
      <div className="patch-header" onClick={() => setExpanded(!expanded)}>
        <div className="patch-title">
          <span className="patch-icon">🔧</span>
          <strong>{String(intent)}</strong>
        </div>
        <div className="patch-meta">
          <span className="op-count">{operations.length} operation{operations.length !== 1 ? 's' : ''}</span>
          <span className={`expand-icon ${expanded ? 'open' : ''}`}>▸</span>
        </div>
      </div>

      {rationale && (
        <div className="patch-rationale">
          <p>{String(rationale)}</p>
        </div>
      )}

      {expanded && (
        <div className="patch-operations">
          {operations.map((op, i) => {
            const typedOp = op as Record<string, unknown>
            return (
              <div key={i} className="patch-op">
                <span className={`op-badge op-${String(typedOp.type).replace('.', '-')}`}>
                  {formatOpType(typedOp.type as string)}
                </span>
                <span className="op-summary">{summarizeOp(typedOp)}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Validation results */}
      {validation && phase === 'validated' && (
        <div className="validation-result success">
          <span className="result-icon">✅</span>
          <div>
            <strong>Validation passed</strong>
            {validation.affected && (
              <div className="affected-summary">
                {validation.affected.components.length > 0 && (
                  <span>Components: {validation.affected.components.join(', ')}</span>
                )}
                {validation.affected.nets.length > 0 && (
                  <span> · Nets: {validation.affected.nets.join(', ')}</span>
                )}
              </div>
            )}
            {hasWarnings && (
              <div className="warnings">
                {validation.warnings!.map((w, i) => (
                  <div key={i} className="warning-item">⚠️ {typeof w === 'string' ? w : JSON.stringify(w)}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {(validation?.status === 'rejected' || hasErrors) && (
        <div className="validation-result error">
          <span className="result-icon">❌</span>
          <div>
            <strong>Validation failed</strong>
            <p>{String(validation?.message || validateError || applyError || 'Unknown error')}</p>
            {validation?.details != null && (
              <pre className="error-details">{JSON.stringify(validation.details, null, 2)}</pre>
            )}
          </div>
        </div>
      )}

      {phase === 'applied' && (
        <div className="validation-result success">
          <span className="result-icon">✅</span>
          <div>
            <strong>Changes applied successfully</strong>
            <p className="rollback-hint">Restore via KiCad → File → Local History if needed</p>
          </div>
        </div>
      )}

      {/* Action buttons */}
      {phase === 'idle' && (
        <div className="patch-actions">
          <button
            className="validate-btn"
            onClick={handleValidate}
            disabled={validating}
          >
            {validating ? 'Validating...' : 'Validate'}
          </button>
          <button
            className="reject-btn"
            onClick={handleReject}
          >
            Dismiss
          </button>
        </div>
      )}

      {phase === 'validated' && (
        <div className="patch-actions">
          <button
            className="apply-btn"
            onClick={handleApply}
            disabled={applying}
          >
            {applying ? 'Applying...' : 'Apply Changes'}
          </button>
          <button
            className="reject-btn"
            onClick={handleReject}
          >
            Reject
          </button>
        </div>
      )}

      {(phase === 'rejected' || phase === 'applied') && (
        <div className="patch-actions">
          <button
            className="dismiss-btn"
            onClick={handleReject}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}

function formatOpType(type: string): string {
  return type
    .replace(/\./g, ' › ')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

function summarizeOp(op: Record<string, unknown>): string {
  const type = op.type as string | undefined
  switch (type) {
    case 'pin.assign_net':
      return `${op.reference as string}.${op.pin as string} → ${op.net as string}`
    case 'net.split':
      return `${op.origin_net as string} → ${op.new_net as string} (move ${(op.move_pins as unknown[])?.length || 0} pins)`
    case 'component.add':
      return `${op.reference as string} (${op.lib_id as string} = ${op.value as string})`
    case 'component.update_value':
      return `${op.reference as string} → ${op.value as string}`
    case 'component.remove':
      return op.reference as string
    case 'simulation.set_directive':
      return `.${op.directive as string} ${JSON.stringify(op.parameters)}`
    case 'simulation.remove_directive':
      return `.${op.directive_type as string}`
    default:
      return JSON.stringify(op)
  }
}
