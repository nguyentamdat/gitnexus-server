"""Impact analysis (blast radius) service."""

from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
import structlog

from app.database import SymbolSpan, File
from app.neo4j_client import Neo4jClient
from app.models import ImpactAnalysisRequest, ImpactAnalysisResult, ImpactItem

logger = structlog.get_logger()


class ImpactService:
    """Blast radius analysis: what breaks if I change this?"""
    
    def __init__(self, db: Session, neo4j: Neo4jClient):
        self.db = db
        self.neo4j = neo4j
    
    def analyze_impact(self, request: ImpactAnalysisRequest) -> ImpactAnalysisResult:
        """
        Analyze the impact of proposed changes.
        
        Steps:
        1. Identify changed symbols from files/diff
        2. Query Neo4j for dependency graph
        3. Score affected items by distance and confidence
        4. Categorize by severity
        """
        start_time = time.time()
        
        # 1. Get changed symbol IDs
        changed_symbol_ids = self._resolve_changed_symbols(request)
        
        if not changed_symbol_ids:
            return ImpactAnalysisResult(
                target_symbols=[],
                summary={
                    "total_affected": 0,
                    "direct_dependencies": 0,
                    "indirect_dependencies": 0
                },
                direct=[],
                indirect=[],
                by_confidence={"high": [], "medium": [], "low": []},
                execution_time_ms=0,
                graph_traversal_nodes=0
            )
        
        # 2. Query Neo4j for impact analysis
        impact_data = self.neo4j.get_impact_analysis(
            changed_symbol_ids,
            depth=request.depth
        )
        
        # 3. Convert to ImpactItems
        direct = [ImpactItem(**item) for item in impact_data.get("direct", [])]
        indirect = [ImpactItem(**item) for item in impact_data.get("indirect", [])]
        
        by_confidence = {
            "high": [ImpactItem(**item) for item in impact_data.get("by_confidence", {}).get("high", [])],
            "medium": [ImpactItem(**item) for item in impact_data.get("by_confidence", {}).get("medium", [])],
            "low": [ImpactItem(**item) for item in impact_data.get("by_confidence", {}).get("low", [])]
        }
        
        execution_time = (time.time() - start_time) * 1000
        
        return ImpactAnalysisResult(
            target_symbols=changed_symbol_ids,
            summary=impact_data.get("summary", {}),
            direct=direct,
            indirect=indirect,
            by_confidence=by_confidence,
            execution_time_ms=execution_time,
            graph_traversal_nodes=impact_data.get("summary", {}).get("total_affected", 0)
        )
    
    def _resolve_changed_symbols(self, request: ImpactAnalysisRequest) -> list:
        """
        Resolve changed files/diff to symbol IDs.
        
        Priority:
        1. Explicit changed_symbols
        2. Changed files (lookup symbols in those files)
        3. Parse diff text
        """
        symbol_ids = []
        
        # 1. Explicit symbol IDs
        if request.changed_symbols:
            symbol_ids.extend(request.changed_symbols)
        
        # 2. Changed files - find symbols in those files
        if request.changed_files:
            for file_path in request.changed_files:
                # Find file in active revision
                symbols = self.db.query(SymbolSpan).join(File).filter(
                    File.path == file_path,
                    File.revision_id.in_(
                        self.db.query(Revision.id).filter(Revision.is_active == 1)
                    )
                ).all()
                
                symbol_ids.extend([s.id for s in symbols])
        
        # 3. Parse diff (simplified - would use git diff parser in production)
        if request.diff_text and not symbol_ids:
            # Extract file paths from diff
            # For now, skip
            pass
        
        return list(set(symbol_ids))  # Deduplicate
    
    def analyze_file_impact(self, repo_id: int, file_path: str) -> Dict[str, Any]:
        """Quick impact analysis for a single file."""
        # Find file
        file = self.db.query(File).join(Revision).join(Repository).filter(
            File.path == file_path,
            Repository.id == repo_id,
            Revision.is_active == 1
        ).first()
        
        if not file:
            return {"error": "File not found"}
        
        # Get symbols in file
        symbols = self.db.query(SymbolSpan).filter(SymbolSpan.file_id == file.id).all()
        symbol_ids = [s.id for s in symbols]
        
        if not symbol_ids:
            return {
                "file": file_path,
                "symbols_found": 0,
                "impact": "No symbols found to analyze"
            }
        
        # Get impact from Neo4j
        impact = self.neo4j.get_impact_analysis(symbol_ids, depth=2)
        
        return {
            "file": file_path,
            "symbols_found": len(symbols),
            "symbol_names": [s.name for s in symbols[:10]],
            "impact_summary": impact.get("summary", {}),
            "high_risk_dependencies": len(impact.get("by_confidence", {}).get("high", []))
        }
