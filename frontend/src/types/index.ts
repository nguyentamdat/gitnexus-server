export interface Repository {
  id: number
  name: string
  url: string
  description?: string
  default_branch: string
  status: 'pending' | 'indexing' | 'active' | 'error'
  last_indexed_at?: string
  last_error?: string
  created_at: string
  updated_at: string
}

export interface RepositoryCreate {
  name: string
  url: string
  description?: string
  default_branch?: string
}

export interface IndexJob {
  id: number
  repository_id: number
  revision_id?: number
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress_percent: number
  files_processed: number
  files_total: number
  symbols_extracted: number
  chunks_indexed: number
  started_at?: string
  completed_at?: string
  failed_at?: string
  error_message?: string
  created_at: string
}

export interface SearchQuery {
  query: string
  repo_id?: number
  language?: string
  symbol_type?: string
  semantic_weight?: number
  lexical_weight?: number
  graph_weight?: number
  limit?: number
  offset?: number
  expand_neighbors?: boolean
  neighbor_depth?: number
}

export interface SearchResultItem {
  type: 'symbol' | 'file' | 'chunk'
  id: number
  name: string
  path: string
  language?: string
  symbol_type?: string
  semantic_score?: number
  lexical_score?: number
  graph_score?: number
  combined_score: number
  snippet?: string
  start_line?: number
  end_line?: number
  neighbors?: unknown[]
  repo_id: number
  repo_name: string
}

export interface SearchResult {
  query: string
  total: number
  items: SearchResultItem[]
  execution_time_ms: number
  strategy_used: string
  languages: Record<string, number>
  symbol_types: Record<string, number>
}

export interface GraphNode {
  id: number
  label: string
  type: string
  is_center: boolean
  properties: Record<string, unknown>
}

export interface GraphEdge {
  source: number
  target: number
  type: string
  properties: Record<string, unknown>
}

export interface SubgraphRequest {
  center_type: 'Repository' | 'Revision' | 'File' | 'Symbol'
  center_id: number
  depth?: number
  limit?: number
}

export interface SubgraphResult {
  center: {
    id: number
    type: string
    name: string
  }
  nodes: GraphNode[]
  edges: GraphEdge[]
  depth: number
  total_nodes: number
}

export interface ImpactItem {
  symbol: {
    id: number
    name: string
    type: string
    qualified_name?: string
  }
  triggered_by: {
    id: number
    name: string
  }
  distance: number
  confidence: number
  path: string[]
}

export interface ImpactAnalysisRequest {
  repo_id: number
  changed_files?: string[]
  changed_symbols?: number[]
  diff_text?: string
  depth?: number
  min_confidence?: number
  include_tests?: boolean
  include_indirect?: boolean
}

export interface ImpactAnalysisResult {
  target_symbols: number[]
  summary: {
    total_affected: number
    direct_dependencies: number
    indirect_dependencies: number
    high_confidence?: number
    medium_confidence?: number
    low_confidence?: number
  }
  direct: ImpactItem[]
  indirect: ImpactItem[]
  by_confidence: {
    high: ImpactItem[]
    medium: ImpactItem[]
    low: ImpactItem[]
  }
  execution_time_ms: number
  graph_traversal_nodes: number
}
