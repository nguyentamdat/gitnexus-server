import { useRepositories, useSystemStatus } from '../hooks/useApi'
import { 
  GitBranch, 
  Activity, 
  CheckCircle2, 
  AlertCircle, 
  Clock,
  Database,
  Network
} from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  const { data: repos } = useRepositories()
  const { data: status } = useSystemStatus()
  
  const activeRepos = repos?.filter(r => r.status === 'active') || []
  const indexingRepos = repos?.filter(r => r.status === 'indexing') || []
  const errorRepos = repos?.filter(r => r.status === 'error') || []
  
  const postgresStatus = status?.postgres === 'connected' ? 'Connected' : 'Disconnected'
  const neo4jStatus = status?.neo4j === 'connected' ? 'Connected' : 'Disconnected'
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-2">
          Overview of your code intelligence system
        </p>
      </div>
      
      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Repos */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Total Repositories</p>
              <h3 className="text-2xl font-bold mt-1">{repos?.length || 0}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <GitBranch className="h-5 w-5 text-primary" />
            </div>
          </div>
          <div className="mt-4 flex items-center text-sm">
            <CheckCircle2 className="h-4 w-4 text-green-500 mr-1" />
            <span className="text-green-600 font-medium">{activeRepos.length}</span>
            <span className="text-muted-foreground ml-1">active</span>
          </div>
        </div>
        
        {/* Indexing */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Indexing</p>
              <h3 className="text-2xl font-bold mt-1">{indexingRepos.length}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
              <Activity className="h-5 w-5 text-yellow-500" />
            </div>
          </div>
          <div className="mt-4 flex items-center text-sm">
            <Clock className="h-4 w-4 text-yellow-500 mr-1" />
            <span className="text-muted-foreground">In progress</span>
          </div>
        </div>
        
        {/* Errors */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Errors</p>
              <h3 className="text-2xl font-bold mt-1">{errorRepos.length}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-red-500/10 flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-red-500" />
            </div>
          </div>
          <div className="mt-4 flex items-center text-sm">
            {errorRepos.length > 0 ? (
              <span className="text-red-600">Requires attention</span>
            ) : (
              <span className="text-green-600">All systems operational</span>
            )}
          </div>
        </div>
        
        {/* System Status */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">System Status</p>
              <h3 className="text-lg font-bold mt-1">{status?.status || 'Unknown'}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Database className="h-5 w-5 text-blue-500" />
            </div>
          </div>
          <div className="mt-4 space-y-1 text-sm">
            <div className="flex items-center">
              <span className="text-muted-foreground">Postgres:</span>
              <span className={postgresStatus === 'Connected' ? 'text-green-600 ml-2' : 'text-red-600 ml-2'}>
                {postgresStatus}
              </span>
            </div>
            <div className="flex items-center">
              <span className="text-muted-foreground">Neo4j:</span>
              <span className={neo4jStatus === 'Connected' ? 'text-green-600 ml-2' : 'text-red-600 ml-2'}>
                {neo4jStatus}
              </span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Recent Repositories */}
      <div className="bg-card border border-border rounded-xl">
        <div className="p-6 border-b border-border">
          <h2 className="text-lg font-semibold">Recent Repositories</h2>
          <p className="text-sm text-muted-foreground">Recently added or updated repositories</p>
        </div>
        <div className="divide-y divide-border">
          {repos?.slice(0, 5).map(repo => (
            <Link 
              key={repo.id} 
              to={`/repos/${repo.id}`}
              className="flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center">
                  <GitBranch className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <h4 className="font-medium">{repo.name}</h4>
                  <p className="text-sm text-muted-foreground">{repo.url}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className={`
                  inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                  ${repo.status === 'active' ? 'bg-green-100 text-green-800' : ''}
                  ${repo.status === 'indexing' ? 'bg-yellow-100 text-yellow-800' : ''}
                  ${repo.status === 'error' ? 'bg-red-100 text-red-800' : ''}
                  ${repo.status === 'pending' ? 'bg-gray-100 text-gray-800' : ''}
                `}>
                  {repo.status}
                </span>
              </div>
            </Link>
          ))}
          
          {(!repos || repos.length === 0) && (
            <div className="p-8 text-center">
              <Network className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium">No repositories yet</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Add your first repository to start indexing code
              </p>
              <Link 
                to="/repos"
                className="mt-4 inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
              >
                <GitBranch className="h-4 w-4 mr-2" />
                Add Repository
              </Link>
            </div>
          )}
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-3">
        <Link 
          to="/repos"
          className="flex items-center gap-4 p-4 bg-card border border-border rounded-xl hover:border-primary/50 transition-colors"
        >
          <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
            <GitBranch className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold">Add Repository</h3>
            <p className="text-sm text-muted-foreground">Index a new codebase</p>
          </div>
        </Link>
        
        <Link 
          to="/search"
          className="flex items-center gap-4 p-4 bg-card border border-border rounded-xl hover:border-primary/50 transition-colors"
        >
          <div className="h-12 w-12 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Activity className="h-6 w-6 text-blue-500" />
          </div>
          <div>
            <h3 className="font-semibold">Search Code</h3>
            <p className="text-sm text-muted-foreground">Semantic + lexical search</p>
          </div>
        </Link>
        
        <Link 
          to="/graph"
          className="flex items-center gap-4 p-4 bg-card border border-border rounded-xl hover:border-primary/50 transition-colors"
        >
          <div className="h-12 w-12 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <Network className="h-6 w-6 text-purple-500" />
          </div>
          <div>
            <h3 className="font-semibold">Explore Graph</h3>
            <p className="text-sm text-muted-foreground">Visualize code relationships</p>
          </div>
        </Link>
      </div>
    </div>
  )
}
