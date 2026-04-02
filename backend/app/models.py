"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl


# ==================== Repository Models ====================

class RepositoryCreate(BaseModel):
    """Request to create a repository."""
    name: str = Field(..., description="Repository name")
    url: HttpUrl = Field(..., description="Git repository URL")
    description: Optional[str] = Field(None, description="Repository description")
    default_branch: str = Field("main", description="Default branch to index")


class RepositoryResponse(BaseModel):
    """Repository information."""
    id: int
    name: str
    url: str
    description: Optional[str]
    default_branch: str
    status: str
    last_indexed_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Indexing Models ====================

class IndexJobResponse(BaseModel):
    """Indexing job status."""
    id: int
    repository_id: int
    revision_id: Optional[int]
    status: str
    progress_percent: float
    files_processed: int
    files_total: int
    symbols_extracted: int
    chunks_indexed: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    failed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Search Models ====================

class SearchQuery(BaseModel):
    """Search request."""
    query: str = Field(..., description="Search query text")
    repo_id: Optional[int] = Field(None, description="Limit to specific repository")
    language: Optional[str] = Field(None, description="Filter by language")
    symbol_type: Optional[str] = Field(None, description="Filter by symbol type")
    
    # Search strategy
    semantic_weight: float = Field(0.5, ge=0, le=1, description="Weight for semantic search")
    lexical_weight: float = Field(0.3, ge=0, le=1, description="Weight for lexical search")
    graph_weight: float = Field(0.2, ge=0, le=1, description="Weight for graph expansion")
    
    # Limits
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    
    # Graph expansion
    expand_neighbors: bool = Field(True, description="Expand to graph neighbors")
    neighbor_depth: int = Field(1, ge=1, le=3)


class SearchResultItem(BaseModel):
    """Individual search result."""
    type: Literal["symbol", "file", "chunk"]
    id: int
    name: str
    path: str
    language: Optional[str]
    symbol_type: Optional[str]
    
    # Scoring
    semantic_score: Optional[float]
    lexical_score: Optional[float]
    graph_score: Optional[float]
    combined_score: float
    
    # Content
    snippet: Optional[str]
    start_line: Optional[int]
    end_line: Optional[int]
    
    # Graph context
    neighbors: Optional[List[Dict]] = None
    
    # Source info
    repo_id: int
    repo_name: str


class SearchResult(BaseModel):
    """Search response."""
    query: str
    total: int
    items: List[SearchResultItem]
    
    # Query metadata
    execution_time_ms: float
    strategy_used: str
    
    # Facets
    languages: Dict[str, int]
    symbol_types: Dict[str, int]


# ==================== Graph Models ====================

class SubgraphRequest(BaseModel):
    """Request for centered subgraph."""
    center_type: Literal["Repository", "Revision", "File", "Symbol"] = "Symbol"
    center_id: int
    depth: int = Field(2, ge=1, le=4, description="Graph traversal depth")
    limit: int = Field(100, ge=10, le=500, description="Max nodes to return")


class GraphNode(BaseModel):
    """Graph node for visualization."""
    id: int
    label: str
    type: str
    is_center: bool
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    """Graph edge for visualization."""
    source: int
    target: int
    type: str
    properties: Dict[str, Any]


class SubgraphResult(BaseModel):
    """Subgraph response."""
    center: Dict[str, Any]
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    depth: int
    total_nodes: int


# ==================== Impact Analysis Models ====================

class ImpactAnalysisRequest(BaseModel):
    """Request for blast radius analysis."""
    repo_id: int
    
    # What changed
    changed_files: Optional[List[str]] = Field(None, description="List of changed file paths")
    changed_symbols: Optional[List[int]] = Field(None, description="List of changed symbol IDs")
    diff_text: Optional[str] = Field(None, description="Git diff text")
    
    # Analysis depth
    depth: int = Field(3, ge=1, le=5)
    
    # Filtering
    min_confidence: float = Field(0.5, ge=0, le=1)
    include_tests: bool = Field(True)
    include_indirect: bool = Field(True)


class ImpactItem(BaseModel):
    """Single impact item."""
    symbol: Dict[str, Any]
    triggered_by: Dict[str, Any]
    distance: int
    confidence: float
    path: List[str]


class ImpactAnalysisResult(BaseModel):
    """Blast radius analysis response."""
    target_symbols: List[int]
    
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    
    # Categorized results
    direct: List[ImpactItem] = Field(..., description="Direct dependencies (distance 1)")
    indirect: List[ImpactItem] = Field(..., description="Indirect dependencies")
    
    by_confidence: Dict[str, List[ImpactItem]]
    
    # Execution info
    execution_time_ms: float
    graph_traversal_nodes: int


# ==================== MCP Models ====================

class MCPToolCall(BaseModel):
    """MCP tool invocation."""
    tool: str
    parameters: Dict[str, Any]
    request_id: str


class MCPToolResult(BaseModel):
    """MCP tool response."""
    request_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # Metadata
    execution_time_ms: float
    data_sources: List[str]  # postgres, neo4j, etc.
