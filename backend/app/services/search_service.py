"""Search service with hybrid retrieval."""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
import structlog

from app.database import FileChunk, SymbolSpan, File, Repository, Revision
from app.neo4j_client import Neo4jClient
from app.models import SearchQuery, SearchResult, SearchResultItem
from app.embeddings import get_embeddings

logger = structlog.get_logger()


class SearchService:
    """Hybrid search: semantic + lexical + graph expansion."""
    
    def __init__(self, db: Session, neo4j: Neo4jClient):
        self.db = db
        self.neo4j = neo4j
        self.embeddings = get_embeddings()
    
    def search(self, query: SearchQuery) -> SearchResult:
        """
        Execute hybrid search across code.
        
        Strategy:
        1. Semantic search (vector similarity)
        2. Lexical search (PostgreSQL FTS)
        3. Merge and rerank
        4. Graph expansion (if enabled)
        5. Return combined results
        """
        start_time = time.time()
        
        results_map = {}  # id -> SearchResultItem with scores
        
        # 1. Semantic search
        if query.semantic_weight > 0:
            semantic_results = self._semantic_search(query)
            for item in semantic_results:
                key = (item.type, item.id)
                if key not in results_map:
                    results_map[key] = item
                else:
                    results_map[key].semantic_score = item.semantic_score
        
        # 2. Lexical search
        if query.lexical_weight > 0:
            lexical_results = self._lexical_search(query)
            for item in lexical_results:
                key = (item.type, item.id)
                if key not in results_map:
                    results_map[key] = item
                else:
                    results_map[key].lexical_score = item.lexical_score
        
        # 3. Calculate combined scores
        for key, item in results_map.items():
            sem_score = item.semantic_score or 0
            lex_score = item.lexical_score or 0
            graph_score = item.graph_score or 0
            
            item.combined_score = (
                sem_score * query.semantic_weight +
                lex_score * query.lexical_weight +
                graph_score * query.graph_weight
            )
        
        # 4. Graph expansion (optional)
        if query.expand_neighbors and query.graph_weight > 0:
            self._expand_with_graph(results_map, query)
        
        # 5. Sort by combined score
        sorted_results = sorted(
            results_map.values(),
            key=lambda x: x.combined_score,
            reverse=True
        )
        
        # 6. Apply limit and offset
        final_results = sorted_results[query.offset:query.offset + query.limit]
        
        # 7. Calculate facets
        languages = {}
        symbol_types = {}
        for item in final_results:
            if item.language:
                languages[item.language] = languages.get(item.language, 0) + 1
            if item.symbol_type:
                symbol_types[item.symbol_type] = symbol_types.get(item.symbol_type, 0) + 1
        
        execution_time = (time.time() - start_time) * 1000
        
        return SearchResult(
            query=query.query,
            total=len(sorted_results),
            items=final_results,
            execution_time_ms=execution_time,
            strategy_used=f"semantic:{query.semantic_weight}, lexical:{query.lexical_weight}, graph:{query.graph_weight}",
            languages=languages,
            symbol_types=symbol_types
        )
    
    def _semantic_search(self, query: SearchQuery) -> List[SearchResultItem]:
        """Vector similarity search using pgvector."""
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query.query)
        
        # Build SQL query
        sql = """
            SELECT 
                c.id as chunk_id,
                c.content as snippet,
                c.start_line,
                c.end_line,
                c.chunk_type,
                c.embedding <=> :embedding as distance,
                f.id as file_id,
                f.path,
                f.language,
                r.id as repo_id,
                repo.name as repo_name,
                s.id as symbol_id,
                s.name as symbol_name,
                s.symbol_type
            FROM file_chunks c
            JOIN files f ON c.file_id = f.id
            JOIN revisions r ON c.revision_id = r.id
            JOIN repositories repo ON r.repository_id = repo.id
            LEFT JOIN symbol_spans s ON c.symbol_id = s.id
            WHERE r.is_active = 1
        """
        
        params = {"embedding": str(query_embedding)}
        
        # Add filters
        if query.repo_id:
            sql += " AND repo.id = :repo_id"
            params["repo_id"] = query.repo_id
        
        if query.language:
            sql += " AND f.language = :language"
            params["language"] = query.language
        
        # Order by distance (smaller is better for <=> operator)
        sql += " ORDER BY distance ASC LIMIT :limit"
        params["limit"] = query.limit * 2  # Get more for reranking
        
        # Execute
        result = self.db.execute(text(sql), params)
        
        items = []
        for row in result:
            # Convert distance to similarity score (normalize 0-1)
            distance = row.distance
            similarity = max(0, 1 - float(distance))
            
            items.append(SearchResultItem(
                type="chunk",
                id=row.chunk_id,
                name=row.symbol_name or f"Lines {row.start_line}-{row.end_line}",
                path=row.path,
                language=row.language,
                symbol_type=row.symbol_type,
                semantic_score=similarity,
                lexical_score=None,
                graph_score=None,
                combined_score=0,  # Will be calculated later
                snippet=row.snippet[:500],  # Truncate
                start_line=row.start_line,
                end_line=row.end_line,
                repo_id=row.repo_id,
                repo_name=row.repo_name
            ))
        
        return items
    
    def _lexical_search(self, query: SearchQuery) -> List[SearchResultItem]:
        """Full-text search using PostgreSQL FTS."""
        # Convert query to tsquery
        tsquery = " & ".join(query.query.split())
        
        sql = """
            SELECT 
                c.id as chunk_id,
                c.content as snippet,
                c.start_line,
                c.end_line,
                c.chunk_type,
                ts_rank_cd(to_tsvector('english', c.content), to_tsquery(:tsquery)) as rank,
                f.id as file_id,
                f.path,
                f.language,
                r.id as repo_id,
                repo.name as repo_name,
                s.id as symbol_id,
                s.name as symbol_name,
                s.symbol_type
            FROM file_chunks c
            JOIN files f ON c.file_id = f.id
            JOIN revisions r ON c.revision_id = r.id
            JOIN repositories repo ON r.repository_id = repo.id
            LEFT JOIN symbol_spans s ON c.symbol_id = s.id
            WHERE r.is_active = 1
            AND to_tsvector('english', c.content) @@ to_tsquery(:tsquery)
        """
        
        params = {"tsquery": tsquery}
        
        if query.repo_id:
            sql += " AND repo.id = :repo_id"
            params["repo_id"] = query.repo_id
        
        if query.language:
            sql += " AND f.language = :language"
            params["language"] = query.language
        
        sql += " ORDER BY rank DESC LIMIT :limit"
        params["limit"] = query.limit * 2
        
        result = self.db.execute(text(sql), params)
        
        items = []
        for row in result:
            items.append(SearchResultItem(
                type="chunk",
                id=row.chunk_id,
                name=row.symbol_name or f"Lines {row.start_line}-{row.end_line}",
                path=row.path,
                language=row.language,
                symbol_type=row.symbol_type,
                semantic_score=None,
                lexical_score=float(row.rank),
                graph_score=None,
                combined_score=0,
                snippet=row.snippet[:500],
                start_line=row.start_line,
                end_line=row.end_line,
                repo_id=row.repo_id,
                repo_name=row.repo_name
            ))
        
        return items
    
    def _expand_with_graph(self, results_map: dict, query: SearchQuery):
        """Expand results using graph neighborhood."""
        # For now, simplified implementation
        # In production, this would query Neo4j for related symbols
        pass
    
    def get_symbol(self, symbol_id: str) -> Optional[dict]:
        """Get detailed symbol information."""
        # Query from PostgreSQL
        symbol = self.db.query(SymbolSpan).filter(SymbolSpan.id == symbol_id).first()
        if not symbol:
            return None
        
        # Get neighbors from Neo4j
        neighbors = self.neo4j.get_symbol_neighbors(int(symbol_id), direction="both", depth=1)
        
        return {
            "id": symbol.id,
            "name": symbol.name,
            "type": symbol.symbol_type,
            "qualified_name": symbol.qualified_name,
            "file_path": symbol.file.path if symbol.file else None,
            "location": {
                "start_line": symbol.start_line,
                "end_line": symbol.end_line
            },
            "snippet": symbol.snippet,
            "docstring": symbol.docstring,
            "neighbors": neighbors[:10]  # Limit for response size
        }
    
    def get_file_context(self, file_id: str, include_neighbors: bool = True) -> dict:
        """Get file context with optional graph neighborhood."""
        file = self.db.query(File).filter(File.id == file_id).first()
        if not file:
            return None
        
        # Get symbols in file
        symbols = self.db.query(SymbolSpan).filter(SymbolSpan.file_id == file_id).all()
        
        result = {
            "id": file.id,
            "path": file.path,
            "language": file.language,
            "line_count": file.line_count,
            "symbols": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.symbol_type,
                    "lines": [s.start_line, s.end_line]
                }
                for s in symbols[:50]  # Limit
            ]
        }
        
        if include_neighbors and self.neo4j:
            # Get file-level relationships from Neo4j
            # Simplified for now
            result["imported_by"] = []  # Would query Neo4j
            result["imports"] = []
        
        return result
