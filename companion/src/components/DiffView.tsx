import type { PatchPlan, PatchOperation } from '@/services/patch'
import { useState } from 'react'

interface DiffViewProps {
  patchPlan: PatchPlan
}

export function DiffView({ patchPlan }: DiffViewProps) {
  const [selectedOp, setSelectedOp] = useState<number | null>(null)

  return (
    <div className="diff-view">
      <div className="diff-header">
        <h3>Proposed Changes</h3>
        <span className="intent">{patchPlan.intent}</span>
      </div>

      <div className="diff-rationale">
        <h4>Rationale</h4>
        <p>{patchPlan.rationale}</p>
      </div>

      <div className="operations-list">
        <h4>Operations ({patchPlan.operations.length})</h4>
        {patchPlan.operations.map((op, index) => (
          <OperationCard
            key={index}
            operation={op}
            index={index}
            selected={selectedOp === index}
            onClick={() => setSelectedOp(selectedOp === index ? null : index)}
          />
        ))}
      </div>

      <div className="affected-components">
        <h4>Affected Components</h4>
        <AffectedList operations={patchPlan.operations} />
      </div>
    </div>
  )
}

interface OperationCardProps {
  operation: PatchOperation
  index: number
  selected: boolean
  onClick: () => void
}

function OperationCard({ operation, index, selected, onClick }: OperationCardProps) {
  const opType = operation.type
  const opColor = getOperationColor(opType)
  const opIcon = getOperationIcon(opType)

  return (
    <div className={`operation-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div className="operation-header" style={{ borderColor: opColor }}>
        <span className="operation-icon">{opIcon}</span>
        <span className="operation-type">{formatOperationType(opType)}</span>
        <span className="operation-index">#{index + 1}</span>
      </div>
      {selected && (
        <div className="operation-details">
          <pre>{JSON.stringify(operation, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

function AffectedList({ operations }: { operations: PatchOperation[] }) {
  const affected = new Set<string>()

  for (const op of operations) {
    if ('reference' in op) {
      affected.add(op.reference)
    }
    if ('component' in op && op.component) {
      affected.add(op.component.reference)
    }
    if ('origin_net' in op) {
      affected.add(op.origin_net)
    }
    if ('new_net' in op) {
      affected.add(op.new_net)
    }
  }

  return (
    <div className="affected-tags">
      {Array.from(affected).map((item) => (
        <span key={item} className="affected-tag">{item}</span>
      ))}
    </div>
  )
}

function getOperationColor(type: string): string {
  const colors: Record<string, string> = {
    'component.add': '#4caf50',
    'component.remove': '#f44336',
    'component.update_value': '#2196f3',
    'pin.assign_net': '#ff9800',
    'net.split': '#9c27b0',
    'simulation.set_directive': '#00bcd4',
    'simulation.remove_directive': '#795548',
  }
  return colors[type] || '#888'
}

function getOperationIcon(type: string): string {
  const icons: Record<string, string> = {
    'component.add': '+',
    'component.remove': '−',
    'component.update_value': '↻',
    'pin.assign_net': '→',
    'net.split': '⊗',
    'simulation.set_directive': '⚙',
    'simulation.remove_directive': '✕',
  }
  return icons[type] || '?'
}

function formatOperationType(type: string): string {
  return type.replace(/\./g, ' › ').replace(/_/g, ' ')
}