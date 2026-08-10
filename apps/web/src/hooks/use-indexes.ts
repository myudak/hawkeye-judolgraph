import { useQueries, useQuery } from "@tanstack/react-query"

import { api } from "@/api/client"

export function useIndexes() {
  const [casesQuery, runsQuery] = useQueries({
    queries: [
      { queryKey: ["cases"], queryFn: api.listCases, staleTime: 5_000 },
      { queryKey: ["runs"], queryFn: api.listRuns, staleTime: 5_000 },
    ],
  })
  return {
    cases: casesQuery.data?.cases ?? [],
    runs: runsQuery.data?.runs ?? [],
    isPending: casesQuery.isPending || runsQuery.isPending,
    isError: casesQuery.isError && runsQuery.isError,
    errors: [casesQuery.error, runsQuery.error].filter(Boolean),
  }
}

export function useCapability() {
  return useQuery({
    queryKey: ["capability"],
    queryFn: api.capability,
    staleTime: 30_000,
    retry: 1,
  })
}
