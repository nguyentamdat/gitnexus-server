import { useState } from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { 
  GitBranch, 
  Search, 
  Network, 
  Menu, 
  X,
  Settings,
  Activity
} from 'lucide-react'
import { cn } from './utils/cn'
import Dashboard from './pages/Dashboard'
import RepoList from './pages/RepoList'
import RepoDetail from './pages/RepoDetail'
import SearchPage from './pages/Search'
import GraphView from './pages/GraphView'

function NavLink({ 
  to, 
  icon: Icon, 
  label 
}: { 
  to: string
  icon: React.ElementType
  label: string 
}) {
  const location = useLocation()
  const isActive = location.pathname === to || location.pathname.startsWith(`${to}/`)
  
  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg transition-colors",
        isActive 
          ? "bg-primary text-primary-foreground" 
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      <Icon className="h-5 w-5" />
      <span className="font-medium">{label}</span>
    </Link>
  )
}

function Sidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}
      
      {/* Sidebar */}
      <aside className={cn(
        "fixed top-0 left-0 z-50 h-full w-64 bg-card border-r border-border transition-transform lg:translate-x-0 lg:static",
        !isOpen && "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <Network className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="font-bold text-lg">GitNexus</h1>
              <p className="text-xs text-muted-foreground">Code Intelligence</p>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            <NavLink to="/" icon={Activity} label="Dashboard" />
            <NavLink to="/repos" icon={GitBranch} label="Repositories" />
            <NavLink to="/search" icon={Search} label="Search" />
            <NavLink to="/graph" icon={Network} label="Graph" />
          </nav>
          
          {/* Footer */}
          <div className="p-4 border-t border-border">
            <Link 
              to="/settings" 
              className="flex items-center gap-3 px-4 py-3 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              <Settings className="h-5 w-5" />
              <span className="font-medium">Settings</span>
            </Link>
          </div>
        </div>
      </aside>
    </>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  
  return (
    <div className="min-h-screen bg-background">
      {/* Mobile header */}
      <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-card border-b border-border">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <Network className="h-5 w-5 text-primary-foreground" />
          </div>
          <h1 className="font-bold">GitNexus</h1>
        </div>
        <button 
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 rounded-lg hover:bg-muted"
        >
          {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>
      
      <div className="flex">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        
        {/* Main content */}
        <main className="flex-1 min-h-[calc(100vh-60px)] lg:min-h-screen">
          <div className="p-6 lg:p-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/repos" element={<RepoList />} />
              <Route path="/repos/:id" element={<RepoDetail />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/graph" element={<GraphView />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  )
}
