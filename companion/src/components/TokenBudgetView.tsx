import type { TokenBudget } from '@/services/context'

interface TokenBudgetViewProps {
  budget: TokenBudget | null
  totalTokens: number
}

export function TokenBudgetView({ budget, totalTokens }: TokenBudgetViewProps) {
  if (!budget) return null

  const layers = budget.layers || []
  const utilization = budget.total_context_budget > 0 
    ? (totalTokens / budget.total_context_budget) * 100 
    : 0

  return (
    <div className="token-budget">
      <h3>Token Budget</h3>
      <div className="budget-summary">
        <span className="total-tokens">{totalTokens.toLocaleString()} tokens</span>
        <span className="utilization">{utilization.toFixed(1)}% of budget</span>
      </div>
      
      <div className="layer-bars">
        {layers.map((layer) => (
          <div key={layer.layer} className="layer-bar">
            <div className="layer-info">
              <span className="layer-name">{layer.layer}</span>
              <span className="layer-tokens">
                {layer.tokens.toLocaleString()} / {layer.max_tokens.toLocaleString()}
              </span>
            </div>
            <div className="bar-container">
              <div 
                className={`bar ${layer.truncated ? 'truncated' : ''}`}
                style={{ 
                  width: `${layer.utilization * 100}%`,
                  backgroundColor: getLayerColor(layer.layer),
                }}
              />
            </div>
            {layer.truncated && (
              <span className="truncated-badge">truncated</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function getLayerColor(layer: string): string {
  const colors: Record<string, string> = {
    system: '#4caf50',
    session: '#2196f3',
    history: '#9c27b0',
    reasoning: '#ff9800',
    simulation: '#f44336',
  }
  return colors[layer] || '#888'
}