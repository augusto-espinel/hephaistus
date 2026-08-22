import { useState, useCallback } from 'react'

// Vite injects VITE_ prefixed env vars at build time
const API_BASE_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL) || 'http://localhost:8000'

interface UseApiResult<T> {
  data: T | null
  loading: boolean
  error: string | null
  execute: (url: string, options?: RequestInit) => Promise<T>
}

export function useApi<T>(): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const execute = useCallback(async (url: string, options?: RequestInit): Promise<T> => {
    setLoading(true)
    setError(null)

    // Prepend base URL if not already absolute
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`

    try {
      const response = await fetch(fullUrl, {
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        ...options,
      })

      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText)
        throw new Error(`HTTP ${response.status}: ${errorText}`)
      }

      const result = await response.json()
      setData(result)
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
      throw err // Re-throw so callers can catch it
    } finally {
      setLoading(false)
    }
  }, [])

  return { data, loading, error, execute }
}

export { API_BASE_URL }