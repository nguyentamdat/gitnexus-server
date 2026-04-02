import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  Search, 
  Filter, 
  Code2, 
  FileCode,
  GitBranch,
  Loader2
} from 'lucide-react'
import * as api from '../services/api'
import type { SearchQuery } from '../types'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({
    repo_id: undefined as number | undefined,
    language: '',
    symbol_type: '',
  })
  const [isSearching, setIsSearching] = useState(false)
  
  const searchParams: SearchQuery | null = query.trim() ? {
    query: query.trim(),
    repo_id: filters.repo_id,
    language: filters.language || undefined,
    symbol_type: filters.symbol_type || undefined,
    limit: 20,
  } : null
  
  const { data: results, isLoading } = useQuery({
    queryKey: ['search', searchParams],
    queryFn: () => searchParams ? api.searchCode(searchParams) : null,
    enabled: !!searchParams,
  })
  
  const { data: repos } = useQuery({
    queryKey: ['repositories'],
    queryFn: api.getRepositories,
  })
  
  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setIsSearching(true)
    // The actual search is triggered by the query change
    setTimeout(() => setIsSearching(false), 100)
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Search Code</h1>
        <p className="text-muted-foreground mt-1">
          Semantic and lexical search across all indexed repositories
        </p>
      </div>
      
      {/* Search Form */}
      <div className="bg-card border border-border rounded-xl p-6">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search for functions, classes, or concepts..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-background border border-border rounded-lg text-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Filter className="h-4 w-4" />
              <span>Filters:</span>
            </div>
            
            <select
              value={filters.repo_id || ''}
              onChange={(e) => setFilters({ ...filters, repo_id: e.target.value ? parseInt(e.target.value) : undefined })}
              className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Repositories</option>
              {repos?.map(repo => (
                <option key={repo.id} value={repo.id}>{repo.name}</option>
              ))}
            </select>
            
            <select
              value={filters.language}
              onChange={(e) => setFilters({ ...filters, language: e.target.value })}
              className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Languages</option>
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
              <option value="typescript">TypeScript</option>
              <option value="go">Go</option>
              <option value="rust">Rust</option>
              <option value="java">Java</option>
            </select>
            
            <select
              value={filters.symbol_type}
              onChange={(e) => setFilters({ ...filters, symbol_type: e.target.value })}
              className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Types</option>
              <option value="function">Function</option>
              <option value="class">Class</option>
              <option value="method">Method</option>
              <option value="interface">Interface</option>
            </select>
          </div>
        </form>
      </div>
      
      {/* Results */}
      <div className="space-y-4">
        {/* Stats */}
        {results && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Found <span className="font-medium text-foreground">{results.total}</span> results
              {results.execution_time_ms > 0 && (
                <span> in {results.execution_time_ms.toFixed(0)}ms</span>
              )}
            </span>
            <span className="text-muted-foreground">
              Strategy: {results.strategy_used}
            </span>
          </div>
        )}
        
        {/* Result Items */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}
        
        {results?.items.map((item, index) => (
          <div 
            key={`${item.type}-${item.id}-${index}`}
            className="bg-card border border-border rounded-xl p-4 hover:border-primary/50 transition-colors"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center mt-1">
                  {item.type === 'symbol' ? (
                    <Code2 className="h-4 w-4 text-muted-foreground" />
                  ) : item.type === 'file' ? (
                    <FileCode className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <GitBranch className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
                <div>
                  <h3 className="font-medium">{item.name}</h3>
                  <p className="text-sm text-muted-foreground">
                    {item.path}
                    {item.start_line && item.end_line && (
                      <span> (lines {item.start_line}-{item.end_line})</span>
                    )}
                  </p>
                  
                  {/* Snippet */}
                  {item.snippet && (
                    <pre className="mt-2 p-3 bg-muted rounded-lg text-sm overflow-x-auto">
                      <code>{item.snippet.length > 300 ? item.snippet.slice(0, 300) + '...' : item.snippet}</code>
                    </pre>
                  )}
                  
                  {/* Metadata */}
                  <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                    {item.language && (
                      <span className="px-2 py-0.5 bg-muted rounded">{item.language}</span>
                    )}
                    {item.symbol_type && (
                      <span className="px-2 py-0.5 bg-muted rounded">{item.symbol_type}</span>
                    )}
                    <span className="flex items-center gap-1">
                      <GitBranch className="h-3 w-3" />
                      {item.repo_name}
                    </span>
                    {item.combined_score > 0 && (
                      <span>Score: {item.combined_score.toFixed(3)}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
        
        {/* Empty State */}
        {!isLoading && query && !results?.items.length && (
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium">No results found</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Try adjusting your search terms or filters
            </p>
          </div>
        )}
        
        {!query && (
          <div className="text-center py-12 text-muted-foreground">
            Enter a search query to find code
          </div>
        )}
      </div>
    </div>
  )
}
