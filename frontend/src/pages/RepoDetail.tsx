import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { 
  GitBranch, 
  ArrowLeft, 
  RefreshCw, 
  AlertCircle,
  CheckCircle2,
  Clock,
  FileCode,
  Activity,
  Network
} from 'lucide-react'
import * as api from '../services/api'

export default function RepoDetail() {
  const { id } = useParams<{ id: string }>()
  const repoId = parseInt(id || '0')
  
  const { data: repo, refetch: refetchRepo } = useQuery({
    queryKey: ['repository', repoId],
    queryFn: () => api.getRepository(repoId),
    enabled: !!repoId,
  })
  
  const { data: jobs, refetch: refetchJobs } = useQuery({
    queryKey: ['jobs', repoId],
    queryFn: () => api.getRepoJobs(repoId),
    enabled: !!repoId,
  })
  
  const [isIndexing, setIsIndexing] = useState(false)
  
  async function handleIndex() {
    setIsIndexing(true)
    try {
      await api.triggerIndexing(repoId)
      refetchJobs()
      refetchRepo()
    } catch (error) {
      console.error('Failed to trigger indexing:', error)
    } finally {
      setIsIndexing(false)
    }
  }
  
  if (!repo) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link to="/repos" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft className="h-4 w-4" />
          Repositories
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium">{repo.name}</span>
      </div>
      
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 rounded-xl bg-primary/10 flex items-center justify-center">
            <GitBranch className="h-7 w-7 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">{repo.name}</h1>
            <a 
              href={repo.url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline"
            >
              {repo.url}
            </a>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <span className={`
            inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium
            ${repo.status === 'active' ? 'bg-green-100 text-green-800' : ''}
            ${repo.status === 'indexing' ? 'bg-yellow-100 text-yellow-800' : ''}
            ${repo.status === 'error' ? 'bg-red-100 text-red-800' : ''}
            ${repo.status === 'pending' ? 'bg-gray-100 text-gray-800' : ''}
          `}>
            {repo.status === 'active' && <CheckCircle2 className="h-4 w-4" />}
            {repo.status === 'indexing' && <RefreshCw className="h-4 w-4 animate-spin" />}
            {repo.status === 'error' && <AlertCircle className="h-4 w-4" />}
            {repo.status === 'pending' && <Clock className="h-4 w-4" />}
            {repo.status}
          </span>
          
          <button
            onClick={handleIndex}
            disabled={isIndexing || repo.status === 'indexing'}
            className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isIndexing ? 'animate-spin' : ''}`} />
            {repo.status === 'active' ? 'Re-index' : 'Index Now'}
          </button>
        </div>
      </div>
      
      {/* Description */}
      {repo.description && (
        <p className="text-muted-foreground">{repo.description}</p>
      )}
      
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <FileCode className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Files</p>
              <p className="text-xl font-bold">-</p>
            </div>
          </div>
        </div>
        
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Activity className="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Symbols</p>
              <p className="text-xl font-bold">-</p>
            </div>
          </div>
        </div>
        
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Network className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Relationships</p>
              <p className="text-xl font-bold">-</p>
            </div>
          </div>
        </div>
        
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <Clock className="h-5 w-5 text-orange-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Last Indexed</p>
              <p className="text-xl font-bold">
                {repo.last_indexed_at 
                  ? new Date(repo.last_indexed_at).toLocaleDateString()
                  : 'Never'
                }
              </p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Error message */}
      {repo.last_error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
            <div>
              <h3 className="font-medium text-red-800">Indexing Error</h3>
              <p className="text-sm text-red-600 mt-1">{repo.last_error}</p>
            </div>
          </div>
        </div>
      )}
      
      {/* Indexing Jobs */}
      <div className="bg-card border border-border rounded-xl">
        <div className="p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Indexing History</h2>
        </div>
        <div className="divide-y divide-border">
          {jobs?.map(job => (
            <div key={job.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`
                    inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                    ${job.status === 'completed' ? 'bg-green-100 text-green-800' : ''}
                    ${job.status === 'running' ? 'bg-blue-100 text-blue-800' : ''}
                    ${job.status === 'queued' ? 'bg-gray-100 text-gray-800' : ''}
                    ${job.status === 'failed' ? 'bg-red-100 text-red-800' : ''}
                  `}>
                    {job.status}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Job #{job.id}
                  </span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {new Date(job.created_at).toLocaleString()}
                </span>
              </div>
              
              {/* Progress bar */}
              {job.status === 'running' && (
                <div className="mt-3">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-muted-foreground">
                      {job.files_processed} / {job.files_total} files
                    </span>
                    <span className="font-medium">
                      {Math.round(job.progress_percent)}%
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${job.progress_percent}%` }}
                    />
                  </div>
                </div>
              )}
              
              {/* Stats */}
              {job.status === 'completed' && (
                <div className="mt-3 flex items-center gap-6 text-sm">
                  <span className="text-muted-foreground">
                    <span className="font-medium text-foreground">{job.files_processed}</span> files
                  </span>
                  <span className="text-muted-foreground">
                    <span className="font-medium text-foreground">{job.symbols_extracted}</span> symbols
                  </span>
                  <span className="text-muted-foreground">
                    <span className="font-medium text-foreground">{job.chunks_indexed}</span> chunks
                  </span>
                </div>
              )}
              
              {/* Error */}
              {job.status === 'failed' && job.error_message && (
                <div className="mt-3 text-sm text-red-600">
                  Error: {job.error_message}
                </div>
              )}
            </div>
          ))}
          
          {(!jobs || jobs.length === 0) && (
            <div className="p-8 text-center text-muted-foreground">
              No indexing jobs yet
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
