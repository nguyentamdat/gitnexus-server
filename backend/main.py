"""GitNexus Server - Main FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import structlog

from app.config import settings
from app.database import engine, get_db, init_db
from app.neo4j_client import Neo4jClient, get_neo4j
from app.models import (
    RepositoryCreate, RepositoryResponse, IndexJobResponse,
    SearchQuery, SearchResult, ImpactAnalysisRequest, ImpactAnalysisResult,
    SubgraphRequest, SubgraphResult
)
from app.services.repo_service import RepoService
from app.services.search_service import SearchService
from app.services.impact_service import ImpactService
from app.services.graph_service import GraphService

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("starting_gitnexus_server")
    init_db()
    yield
    # Shutdown
    logger.info("shutting_down_gitnexus_server")


app = FastAPI(
    title="GitNexus Server",
    description="Code intelligence with knowledge graphs for AI agents",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Health & Status ====================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/v1/status")
async def api_status(
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """Get system status including database connections."""
    status = {
        "postgres": "unknown",
        "neo4j": "unknown",
        "status": "healthy"
    }
    
    # Check PostgreSQL
    try:
        db.execute("SELECT 1")
        status["postgres"] = "connected"
    except Exception as e:
        status["postgres"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Check Neo4j
    try:
        neo4j.verify_connectivity()
        status["neo4j"] = "connected"
    except Exception as e:
        status["neo4j"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    return status


# ==================== Repository Management ====================

@app.post("/api/v1/repos", response_model=RepositoryResponse)
async def create_repository(
    repo: RepositoryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Register a new repository for indexing."""
    service = RepoService(db)
    created = service.create_repository(repo)
    logger.info("repository_created", repo_id=created.id, name=created.name)
    return created


@app.get("/api/v1/repos", response_model=list[RepositoryResponse])
async def list_repositories(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all registered repositories."""
    service = RepoService(db)
    return service.list_repositories(skip=skip, limit=limit)


@app.get("/api/v1/repos/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: int, db: Session = Depends(get_db)):
    """Get repository details."""
    service = RepoService(db)
    repo = service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@app.post("/api/v1/repos/{repo_id}/index", response_model=IndexJobResponse)
async def trigger_indexing(
    repo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """Trigger indexing for a repository."""
    service = RepoService(db, neo4j)
    repo = service.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    job = service.create_index_job(repo_id)
    logger.info("index_job_created", job_id=job.id, repo_id=repo_id)
    
    # The actual indexing is done by the worker, not here
    return job


@app.get("/api/v1/repos/{repo_id}/jobs", response_model=list[IndexJobResponse])
async def list_index_jobs(repo_id: int, db: Session = Depends(get_db)):
    """List indexing jobs for a repository."""
    service = RepoService(db)
    return service.list_jobs(repo_id)


@app.get("/api/v1/jobs/{job_id}", response_model=IndexJobResponse)
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """Get indexing job status."""
    service = RepoService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ==================== Search ====================

@app.post("/api/v1/search", response_model=SearchResult)
async def search_code(
    query: SearchQuery,
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """
    Hybrid search across code: semantic + lexical + graph expansion.
    
    - Semantic: Vector similarity search
    - Lexical: Full-text search (PostgreSQL FTS)
    - Graph: Expand to related symbols via Neo4j
    """
    service = SearchService(db, neo4j)
    return service.search(query)


@app.get("/api/v1/symbols/{symbol_id}")
async def get_symbol(
    symbol_id: str,
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """Get detailed information about a symbol."""
    service = SearchService(db, neo4j)
    symbol = service.get_symbol(symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return symbol


@app.get("/api/v1/files/{file_id}")
async def get_file_context(
    file_id: str,
    include_neighbors: bool = True,
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """Get file context with optional graph neighborhood."""
    service = SearchService(db, neo4j)
    return service.get_file_context(file_id, include_neighbors)


# ==================== Graph Queries ====================

@app.post("/api/v1/graph/subgraph", response_model=SubgraphResult)
async def get_subgraph(
    request: SubgraphRequest,
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """
    Get a centered subgraph for visualization.
    
    Always returns a bounded subgraph (depth-limited, node-limited)
    to prevent browser overload.
    """
    service = GraphService(db, neo4j)
    return service.get_subgraph(request)


@app.post("/api/v1/impact-analysis", response_model=ImpactAnalysisResult)
async def impact_analysis(
    request: ImpactAnalysisRequest,
    db: Session = Depends(get_db),
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """
    Blast radius analysis: what breaks if I change this?
    
    Input: changed files, symbols, or diff
    Output: affected files, symbols, call chains with confidence scores
    """
    service = ImpactService(db, neo4j)
    return service.analyze_impact(request)


@app.get("/api/v1/graph/schema")
async def get_graph_schema(neo4j: Neo4jClient = Depends(get_neo4j)):
    """Get the graph schema (node types, edge types, properties)."""
    service = GraphService(None, neo4j)
    return service.get_schema()


# ==================== Raw Cypher (Advanced) ====================

@app.post("/api/v1/graph/cypher")
async def execute_cypher(
    query: str,
    parameters: dict = None,
    neo4j: Neo4jClient = Depends(get_neo4j)
):
    """
    Execute raw Cypher query (use with caution).
    
    Only available for admin/token-authenticated users in production.
    """
    service = GraphService(None, neo4j)
    return service.execute_cypher(query, parameters or {})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
