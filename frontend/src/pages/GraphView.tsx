import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import cytoscape from 'cytoscape'
import { 
  Network, 
  ZoomIn, 
  ZoomOut, 
  RefreshCw,
  Maximize2,
  Filter
} from 'lucide-react'
import * as api from '../services/api'

export default function GraphView() {
  const cyRef = useRef<HTMLDivElement>(null)
  const [cy, setCy] = useState<cytoscape.Core | null>(null)
  const [centerType, setCenterType] = useState<'Repository' | 'Revision' | 'File' | 'Symbol'>('Symbol')
  const [centerId, setCenterId] = useState<number>(1)
  const [depth, setDepth] = useState(2)
  
  const { data: subgraph, isLoading } = useQuery({
    queryKey: ['subgraph', centerType, centerId, depth],
    queryFn: () => api.getSubgraph({ center_type: centerType, center_id: centerId, depth }),
  })
  
  useEffect(() => {
    if (!cyRef.current || !subgraph) return
    
    // Convert to Cytoscape format
    const elements: cytoscape.ElementDefinition[] = [
      ...subgraph.nodes.map(node => ({
        data: {
          id: String(node.id),
          label: node.label,
          type: node.type,
          isCenter: node.is_center,
        },
        classes: node.is_center ? 'center' : '',
      })),
      ...subgraph.edges.map(edge => ({
        data: {
          id: `${edge.source}-${edge.target}`,
          source: String(edge.source),
          target: String(edge.target),
          label: edge.type,
        },
      })),
    ]
    
    if (!cy) {
      const newCy = cytoscape({
        container: cyRef.current,
        elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': '#3b82f6',
              'label': 'data(label)',
              'width': 40,
              'height': 40,
              'font-size': '12px',
              'text-valign': 'bottom',
              'text-halign': 'center',
              'color': '#374151',
              'text-background-color': '#ffffff',
              'text-background-opacity': 0.8,
              'text-background-padding': '2px',
            },
          },
          {
            selector: 'node.center',
            style: {
              'background-color': '#ef4444',
              'width': 60,
              'height': 60,
              'font-size': '14px',
              'font-weight': 'bold',
            },
          },
          {
            selector: 'edge',
            style: {
              'width': 2,
              'line-color': '#9ca3af',
              'target-arrow-color': '#9ca3af',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'label': 'data(label)',
              'font-size': '10px',
              'color': '#6b7280',
            },
          },
        ],
        layout: {
          name: 'cose',
          padding: 20,
          nodeRepulsion: 400000,
          edgeElasticity: 100,
          nestingFactor: 5,
          gravity: 80,
          numIter: 1000,
          initialTemp: 200,
          coolingFactor: 0.95,
          minTemp: 1.0,
        },
      })
      
      setCy(newCy)
    } else {
      cy.elements().remove()
      cy.add(elements)
      cy.layout({
        name: 'cose',
        padding: 20,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0,
      }).run()
    }
  }, [subgraph, cy])
  
  function handleZoomIn() {
    if (cy) {
      const currentZoom = cy.zoom()
      cy.zoom(currentZoom * 1.2)
    }
  }
  
  function handleZoomOut() {
    if (cy) {
      const currentZoom = cy.zoom()
      cy.zoom(currentZoom * 0.8)
    }
  }
  
  function handleFit() {
    cy?.fit()
  }
  
  return (
    <div className="space-y-4 h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Knowledge Graph</h1>
          <p className="text-muted-foreground mt-1">
            Visualize code relationships and dependencies
          </p>
        </div>
      </div>
      
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 bg-card border border-border rounded-xl p-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Center:</span>
        </div>
        
        <select
          value={centerType}
          onChange={(e) => setCenterType(e.target.value as any)}
          className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="Symbol">Symbol</option>
          <option value="File">File</option>
          <option value="Repository">Repository</option>
        </select>
        
        <input
          type="number"
          value={centerId}
          onChange={(e) => setCenterId(parseInt(e.target.value) || 1)}
          placeholder="ID"
          className="w-24 px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
        
        <div className="h-6 w-px bg-border mx-2" />
        
        <span className="text-sm font-medium">Depth:</span>
        <select
          value={depth}
          onChange={(e) => setDepth(parseInt(e.target.value))}
          className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value={1}>1 hop</option>
          <option value={2}>2 hops</option>
          <option value={3}>3 hops</option>
        </select>
        
        <div className="flex-1" />
        
        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomOut}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg"
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            onClick={handleZoomIn}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg"
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            onClick={handleFit}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg"
            title="Fit to screen"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      
      {/* Graph Container */}
      <div className="flex-1 bg-card border border-border rounded-xl overflow-hidden relative min-h-[400px]">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-card/80 z-10">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}
        
        <div ref={cyRef} className="w-full h-full" />
        
        {!subgraph?.nodes?.length && !isLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
            <Network className="h-16 w-16 mb-4" />
            <p>No graph data available</p>
            <p className="text-sm">Enter a center node to visualize the graph</p>
          </div>
        )}
      </div>
      
      {/* Legend */}
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-red-500" />
          <span className="text-muted-foreground">Center Node</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-blue-500" />
          <span className="text-muted-foreground">Connected Node</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-0.5 bg-gray-400" />
          <span className="text-muted-foreground">Relationship</span>
        </div>
      </div>
    </div>
  )
}
