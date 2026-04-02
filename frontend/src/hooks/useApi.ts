import { useQuery } from '@tanstack/react-query'
import * as api from '../services/api'

export function useRepositories() {
  return useQuery({
    queryKey: ['repositories'],
    queryFn: api.getRepositories,
  })
}

export function useRepository(id: number) {
  return useQuery({
    queryKey: ['repository', id],
    queryFn: () => api.getRepository(id),
    enabled: !!id,
  })
}

export function useRepoJobs(repoId: number) {
  return useQuery({
    queryKey: ['jobs', repoId],
    queryFn: () => api.getRepoJobs(repoId),
    enabled: !!repoId,
  })
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: 30000,
  })
}
