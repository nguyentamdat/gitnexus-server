import axios from 'axios'
import type { 
  Repository, 
  RepositoryCreate, 
  IndexJob, 
  SearchQuery, 
  SearchResult,
  SubgraphRequest,
  SubgraphResult,
  ImpactAnalysisRequest,
  ImpactAnalysisResult 
} from '../types'

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Repositories
export async function getRepositories(): Promise<Repository[]> {
  const response = await api.get('/repos')
  return response.data
}

export async function getRepository(id: number): Promise<Repository> {
  const response = await api.get(`/repos/${id}`)
  return response.data
}

export async function createRepository(data: RepositoryCreate): Promise<Repository> {
  const response = await api.post('/repos', data)
  return response.data
}

export async function triggerIndexing(repoId: number): Promise<IndexJob> {
  const response = await api.post(`/repos/${repoId}/index`)
  return response.data
}

export async function getRepoJobs(repoId: number): Promise<IndexJob[]> {
  const response = await api.get(`/repos/${repoId}/jobs`)
  return response.data
}

export async function getJobStatus(jobId: number): Promise<IndexJob> {
  const response = await api.get(`/jobs/${jobId}`)
  return response.data
}

// Search
export async function searchCode(query: SearchQuery): Promise<SearchResult> {
  const response = await api.post('/search', query)
  return response.data
}

export async function getSymbol(symbolId: string) {
  const response = await api.get(`/symbols/${symbolId}`)
  return response.data
}

export async function getFileContext(fileId: string, includeNeighbors = true) {
  const response = await api.get(`/files/${fileId}`, {
    params: { include_neighbors: includeNeighbors }
  })
  return response.data
}

// Graph
export async function getSubgraph(request: SubgraphRequest): Promise<SubgraphResult> {
  const response = await api.post('/graph/subgraph', request)
  return response.data
}

export async function analyzeImpact(request: ImpactAnalysisRequest): Promise<ImpactAnalysisResult> {
  const response = await api.post('/impact-analysis', request)
  return response.data
}

export async function getGraphSchema() {
  const response = await api.get('/graph/schema')
  return response.data
}

// System
export async function getHealth() {
  const response = await axios.get(`${API_BASE_URL}/health`)
  return response.data
}

export async function getStatus() {
  const response = await api.get('/status')
  return response.data
}
