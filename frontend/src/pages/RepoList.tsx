import { useState } from 'react'
import { useRepositories } from '../hooks/useApi'
import { Link } from 'react-router-dom'
import { 
  GitBranch, 
  Plus, 
  Search, 
  RefreshCw, 
  AlertCircle,
  CheckCircle2,
  Clock,
  MoreVertical
} from 'lucide-react'
import * as api from '../services/api'

export default function RepoList() {
  const { data: repos, refetch } = useRepositories()
  const [isAdding, setIsAdding] = useState(false)
  const [newRepo, setNewRepo] = useState({ name: '', url: '', description: '' })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  
  const filteredRepos = repos?.filter(repo => 
    repo.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    repo.url.toLowerCase().includes(searchTerm.toLowerCase())
  )
  
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setIsSubmitting(true)
    
    try {
      await api.createRepository({
        name: newRepo.name,
        url: newRepo.url,
        description: newRepo.description || undefined,
      })
      
      setNewRepo({ name: '', url: '', description: '' })
      setIsAdding(false)
      refetch()
    } catch (error) {
      console.error('Failed to create repository:', error)
    } finally {
      setIsSubmitting(false)
    }
  }
  
  async function handleIndex(repoId: number) {
    try {
      await api.triggerIndexing(repoId)
      refetch()
    } catch (error) {
      console.error('Failed to trigger indexing:', error)
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Repositories</h1>
          <p className="text-muted-foreground mt-1">
            Manage and index your codebases
          </p>
        </div>
        <button
          onClick={() => setIsAdding(true)}
          className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Repository
        </button>
      </div>
      
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search repositories..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      
      {/* Add Repository Form */}
      {isAdding && (
        <div className="bg-card border border-border rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Add New Repository</h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                type="text"
                required
                value={newRepo.name}
                onChange={(e) => setNewRepo({ ...newRepo, name: e.target.value })}
                placeholder="my-project"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Repository URL</label>
              <input
                type="url"
                required
                value={newRepo.url}
                onChange={(e) => setNewRepo({ ...newRepo, url: e.target.value })}
                placeholder="https://github.com/user/repo"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description (optional)</label>
              <input
                type="text"
                value={newRepo.description}
                onChange={(e) => setNewRepo({ ...newRepo, description: e.target.value })}
                placeholder="Brief description of the project"
                className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50"
              >
                {isSubmitting ? 'Adding...' : 'Add Repository'}
              </button>
              <button
                type="button"
                onClick={() => setIsAdding(false)}
                className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/90"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
      
      {/* Repository List */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="divide-y divide-border">
          {filteredRepos?.map(repo => (
            <div 
              key={repo.id} 
              className="flex items-center justify-between p-4 hover:bg-muted/50"
            >
              <Link 
                to={`/repos/${repo.id}`}
                className="flex items-center gap-4 flex-1"
              >
                <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center">
                  <GitBranch className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <h4 className="font-medium">{repo.name}</h4>
                  <p className="text-sm text-muted-foreground">{repo.url}</p>
                  {repo.last_indexed_at && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Last indexed: {new Date(repo.last_indexed_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </Link>
              
              <div className="flex items-center gap-3">
                {/* Status Badge */}
                <span className={`
                  inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium
                  ${repo.status === 'active' ? 'bg-green-100 text-green-800' : ''}
                  ${repo.status === 'indexing' ? 'bg-yellow-100 text-yellow-800' : ''}
                  ${repo.status === 'error' ? 'bg-red-100 text-red-800' : ''}
                  ${repo.status === 'pending' ? 'bg-gray-100 text-gray-800' : ''}
                `}>
                  {repo.status === 'active' && <CheckCircle2 className="h-3 w-3" />}
                  {repo.status === 'indexing' && <RefreshCw className="h-3 w-3 animate-spin" />}
                  {repo.status === 'error' && <AlertCircle className="h-3 w-3" />}
                  {repo.status === 'pending' && <Clock className="h-3 w-3" />}
                  {repo.status}
                </span>
                
                {/* Actions */}
                <button
                  onClick={() => handleIndex(repo.id)}
                  disabled={repo.status === 'indexing'}
                  className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg disabled:opacity-50"
                  title="Re-index repository"
                >
                  <RefreshCw className={`h-4 w-4 ${repo.status === 'indexing' ? 'animate-spin' : ''}`} />
                </button>
                
                <Link
                  to={`/repos/${repo.id}`}
                  className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg"
                >
                  <MoreVertical className="h-4 w-4" />
                </Link>
              </div>
            </div>
          ))}
          
          {(!filteredRepos || filteredRepos.length === 0) && (
            <div className="p-12 text-center">
              <GitBranch className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium">
                {searchTerm ? 'No repositories match your search' : 'No repositories yet'}
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                {searchTerm 
                  ? 'Try adjusting your search terms'
                  : 'Add your first repository to get started'
                }
              </p>
              {!searchTerm && (
                <button
                  onClick={() => setIsAdding(true)}
                  className="mt-4 inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Repository
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
