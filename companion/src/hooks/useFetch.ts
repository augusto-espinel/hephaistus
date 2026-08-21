import { useEffect, useCallback } from 'react'
import { useApi } from './useApi'

/**
 * Hook that auto-fetches on mount for simple GET requests.
 * Use this for pages that just need to load data once.
 */
export function useFetch<T>(url: string) {
  const { data, loading, error, execute } = useApi<T>()

  const fetch = useCallback(() => {
    execute(url)
  }, [execute, url])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refresh: fetch }
}