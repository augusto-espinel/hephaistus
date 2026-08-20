export interface HistoryEntry {
  id: string
  session_id: string
  timestamp: string
  user_request: string
  llm_response: string
  reasoning_summary: string
  patch_plan_json: string | null
  validation_result: string | null
  user_action: string | null
  context_tokens: number
  response_tokens: number
}