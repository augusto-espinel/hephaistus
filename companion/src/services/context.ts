export interface ContextAssemblyResult {
  session_id: string
  assembled_at: string
  total_tokens: number
  budget_summary: BudgetSummary | null
  layers: Record<string, string>
  prompt: string
}

export interface BudgetSummary {
  total_tokens: number
  total_budget: number
  remaining_budget: number
  utilization: number
  layers: LayerBudget[]
}

export interface LayerBudget {
  layer: string
  tokens: number
  max_tokens: number
  priority: string
  truncated: boolean
  truncation_note: string | null
}

export interface LayerInfo {
  content_length: number
  preview: string
}

export interface TokenBudget {
  total_context_budget: number
  response_budget: number
  layers: LayerBudget[]
}