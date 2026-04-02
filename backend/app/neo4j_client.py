"""Neo4j graph database client."""

from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase, Driver, Session as Neo4jSession
import structlog

from app.config import settings

logger = structlog.get_logger()


class Neo4jClient:
    """Client for Neo4j graph database operations."""
    
    def __init__(self):
        self.driver: Optional[Driver] = None
        self._connect()
    
    def _connect(self):
        """Initialize Neo4j driver."""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            logger.info("neo4j_connected", uri=settings.neo4j_uri)
        except Exception as e:
            logger.error("neo4j_connection_failed", error=str(e))
            raise
    
    def verify_connectivity(self):
        """Verify database connectivity."""
        self.driver.verify_connectivity()
    
    @contextmanager
    def session(self):
        """Get a database session context manager."""
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self):
        """Close the driver connection."""
        if self.driver:
            self.driver.close()
    
    # ==================== Schema Setup ====================
    
    def init_schema(self):
        """Initialize graph schema (constraints and indexes)."""
        with self.session() as session:
            # Constraints
            constraints = [
                "CREATE CONSTRAINT repo_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
                "CREATE CONSTRAINT revision_id IF NOT EXISTS FOR (rev:Revision) REQUIRE rev.id IS UNIQUE",
                "CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE",
                "CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning("constraint_creation_failed", constraint=constraint, error=str(e))
            
            # Indexes
            indexes = [
                "CREATE INDEX symbol_name IF NOT EXISTS FOR (s:Symbol) ON (s.name)",
                "CREATE INDEX symbol_type IF NOT EXISTS FOR (s:Symbol) ON (s.symbol_type)",
                "CREATE INDEX file_path IF NOT EXISTS FOR (f:File) ON (f.path)",
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    logger.warning("index_creation_failed", index=index, error=str(e))
            
            logger.info("neo4j_schema_initialized")
    
    # ==================== Write Operations ====================
    
    def create_repository(self, repo_id: int, name: str, url: str, metadata: Dict = None):
        """Create repository node."""
        with self.session() as session:
            session.run("""
                MERGE (r:Repository {id: $id})
                SET r.name = $name,
                    r.url = $url,
                    r.metadata = $metadata,
                    r.created_at = datetime()
            """, id=repo_id, name=name, url=url, metadata=metadata or {})
    
    def create_revision(
        self, 
        revision_id: int, 
        repo_id: int, 
        commit_hash: str,
        commit_message: str = None,
        author: str = None
    ):
        """Create revision node linked to repository."""
        with self.session() as session:
            session.run("""
                MATCH (repo:Repository {id: $repo_id})
                MERGE (rev:Revision {id: $revision_id})
                SET rev.commit_hash = $commit_hash,
                    rev.commit_message = $commit_message,
                    rev.author = $author,
                    rev.created_at = datetime()
                MERGE (repo)-[:HAS_REVISION]->(rev)
            """, revision_id=revision_id, repo_id=repo_id, 
                 commit_hash=commit_hash, commit_message=commit_message, author=author)
    
    def create_file(
        self, 
        file_id: int,
        revision_id: int,
        path: str,
        language: str = None,
        metadata: Dict = None
    ):
        """Create file node linked to revision."""
        with self.session() as session:
            result = session.run("""
                MATCH (rev:Revision {id: $revision_id})
                MERGE (f:File {id: $file_id})
                SET f.path = $path,
                    f.language = $language,
                    f.metadata = $metadata,
                    f.created_at = datetime()
                MERGE (rev)-[:CONTAINS]->(f)
                RETURN f.id as node_id
            """, file_id=file_id, revision_id=revision_id, path=path,
                 language=language, metadata=metadata or {})
            
            record = result.single()
            return record["node_id"] if record else None
    
    def create_symbol(
        self,
        symbol_id: int,
        file_id: int,
        revision_id: int,
        name: str,
        symbol_type: str,
        qualified_name: str = None,
        start_line: int = None,
        end_line: int = None,
        is_entry_point: bool = False
    ):
        """Create symbol node linked to file."""
        with self.session() as session:
            result = session.run("""
                MATCH (f:File {id: $file_id})
                MATCH (rev:Revision {id: $revision_id})
                MERGE (s:Symbol {id: $symbol_id})
                SET s.name = $name,
                    s.symbol_type = $symbol_type,
                    s.qualified_name = $qualified_name,
                    s.start_line = $start_line,
                    s.end_line = $end_line,
                    s.is_entry_point = $is_entry_point,
                    s.created_at = datetime()
                MERGE (f)-[:DEFINES]->(s)
                MERGE (rev)-[:HAS_SYMBOL]->(s)
                RETURN s.id as node_id
            """, symbol_id=symbol_id, file_id=file_id, revision_id=revision_id,
                 name=name, symbol_type=symbol_type, qualified_name=qualified_name,
                 start_line=start_line, end_line=end_line, is_entry_point=is_entry_point)
            
            record = result.single()
            return record["node_id"] if record else None
    
    def create_call_relationship(self, caller_id: int, callee_id: int, confidence: float = 1.0):
        """Create CALLS relationship between symbols."""
        with self.session() as session:
            session.run("""
                MATCH (caller:Symbol {id: $caller_id})
                MATCH (callee:Symbol {id: $callee_id})
                MERGE (caller)-[r:CALLS]->(callee)
                SET r.confidence = $confidence,
                    r.created_at = datetime()
            """, caller_id=caller_id, callee_id=callee_id, confidence=confidence)
    
    def create_reference_relationship(
        self, 
        from_id: int, 
        to_id: int, 
        ref_type: str = "reference",
        confidence: float = 1.0
    ):
        """Create REFERENCES relationship."""
        with self.session() as session:
            session.run("""
                MATCH (from:Symbol {id: $from_id})
                MATCH (to:Symbol {id: $to_id})
                MERGE (from)-[r:REFERENCES {type: $ref_type}]->(to)
                SET r.confidence = $confidence,
                    r.created_at = datetime()
            """, from_id=from_id, to_id=to_id, ref_type=ref_type, confidence=confidence)
    
    def create_import_relationship(self, file_id: int, symbol_id: int):
        """Create IMPORTS relationship from file to symbol."""
        with self.session() as session:
            session.run("""
                MATCH (f:File {id: $file_id})
                MATCH (s:Symbol {id: $symbol_id})
                MERGE (f)-[r:IMPORTS]->(s)
                SET r.created_at = datetime()
            """, file_id=file_id, symbol_id=symbol_id)
    
    def create_inheritance_relationship(self, child_id: int, parent_id: int):
        """Create INHERITS relationship."""
        with self.session() as session:
            session.run("""
                MATCH (child:Symbol {id: $child_id})
                MATCH (parent:Symbol {id: $parent_id})
                MERGE (child)-[r:INHERITS]->(parent)
                SET r.created_at = datetime()
            """, child_id=child_id, parent_id=parent_id)
    
    # ==================== Read Operations ====================
    
    def get_symbol_neighbors(
        self, 
        symbol_id: int, 
        direction: str = "both",
        depth: int = 2,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get symbol neighborhood via graph traversal.
        
        direction: "in" (callers), "out" (callees), "both"
        """
        with self.session() as session:
            if direction == "in":
                query = """
                    MATCH path = (neighbor)-[*1..$depth]->(s:Symbol {id: $symbol_id})
                    RETURN neighbor, relationships(path), nodes(path)
                    LIMIT $limit
                """
            elif direction == "out":
                query = """
                    MATCH path = (s:Symbol {id: $symbol_id})-[*1..$depth]->(neighbor)
                    RETURN neighbor, relationships(path), nodes(path)
                    LIMIT $limit
                """
            else:  # both
                query = """
                    MATCH path = (neighbor)-[*1..$depth]-(s:Symbol {id: $symbol_id})
                    WHERE neighbor.id <> $symbol_id
                    RETURN neighbor, relationships(path), nodes(path)
                    LIMIT $limit
                """
            
            result = session.run(query, symbol_id=symbol_id, depth=depth, limit=limit)
            
            neighbors = []
            for record in result:
                neighbor = record["neighbor"]
                rels = record["relationships(path)"]
                nodes = record["nodes(path)"]
                
                path_info = []
                for i, rel in enumerate(rels):
                    from_node = nodes[i]
                    to_node = nodes[i+1]
                    path_info.append({
                        "from": from_node.get("name"),
                        "to": to_node.get("name"),
                        "type": rel.type,
                        "confidence": rel.get("confidence", 1.0)
                    })
                
                neighbors.append({
                    "symbol": {
                        "id": neighbor.get("id"),
                        "name": neighbor.get("name"),
                        "type": neighbor.get("symbol_type"),
                        "qualified_name": neighbor.get("qualified_name")
                    },
                    "path": path_info,
                    "distance": len(rels)
                })
            
            return neighbors
    
    def get_impact_analysis(
        self,
        symbol_ids: List[int],
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        Blast radius analysis: what depends on these symbols?
        
        Returns affected symbols organized by depth and confidence.
        """
        with self.session() as session:
            # Get upstream dependencies (what calls/references these symbols)
            result = session.run("""
                MATCH path = (affected)-[*1..$depth]->(target)
                WHERE target.id IN $symbol_ids AND affected.id <> target.id
                RETURN affected, target, relationships(path), length(path) as distance
                ORDER BY distance, affected.qualified_name
                LIMIT 100
            """, symbol_ids=symbol_ids, depth=depth)
            
            upstream = []
            downstream = []
            
            for record in result:
                affected = record["affected"]
                target = record["target"]
                rels = record["relationships(path)"]
                distance = record["distance"]
                
                # Calculate aggregate confidence
                confidence = min(r.get("confidence", 1.0) for r in rels) if rels else 1.0
                
                item = {
                    "symbol": {
                        "id": affected.get("id"),
                        "name": affected.get("name"),
                        "type": affected.get("symbol_type"),
                        "qualified_name": affected.get("qualified_name")
                    },
                    "triggered_by": {
                        "id": target.get("id"),
                        "name": target.get("name")
                    },
                    "distance": distance,
                    "confidence": confidence,
                    "path": [r.type for r in rels]
                }
                
                if distance == 1:
                    upstream.append(item)
                else:
                    downstream.append(item)
            
            # Group by confidence level
            high_confidence = [x for x in upstream + downstream if x["confidence"] >= 0.9]
            medium_confidence = [x for x in upstream + downstream if 0.7 <= x["confidence"] < 0.9]
            low_confidence = [x for x in upstream + downstream if x["confidence"] < 0.7]
            
            return {
                "target_symbols": symbol_ids,
                "summary": {
                    "total_affected": len(upstream) + len(downstream),
                    "direct_dependencies": len(upstream),
                    "indirect_dependencies": len(downstream),
                    "high_confidence": len(high_confidence),
                    "medium_confidence": len(medium_confidence),
                    "low_confidence": len(low_confidence)
                },
                "direct": upstream[:20],  # Limit results
                "indirect": downstream[:30],
                "by_confidence": {
                    "high": high_confidence[:15],
                    "medium": medium_confidence[:15],
                    "low": low_confidence[:10]
                }
            }
    
    def get_subgraph(
        self,
        center_type: str,
        center_id: int,
        depth: int = 2,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get centered subgraph for visualization."""
        with self.session() as session:
            # Match center node
            center_query = f"MATCH (center:{center_type} {{id: $center_id}}) RETURN center"
            center_result = session.run(center_query, center_id=center_id)
            center_record = center_result.single()
            
            if not center_record:
                return {"nodes": [], "edges": [], "center": None}
            
            center_node = center_record["center"]
            
            # Get neighborhood
            result = session.run("""
                MATCH path = (center {id: $center_id})-[*1..$depth]-(neighbor)
                WHERE neighbor.id <> $center_id
                WITH neighbor, relationships(path) as rels, center
                RETURN neighbor, rels, center
                LIMIT $limit
            """, center_id=center_id, depth=depth, limit=limit)
            
            nodes = []
            edges = []
            node_ids = set([center_id])
            
            # Add center node
            nodes.append({
                "id": center_node.get("id"),
                "label": center_node.get("name") or center_node.get("path"),
                "type": center_type,
                "is_center": True,
                "properties": dict(center_node)
            })
            
            for record in result:
                neighbor = record["neighbor"]
                rels = record["relationships"]
                
                neighbor_id = neighbor.get("id")
                
                # Add node if not seen
                if neighbor_id not in node_ids:
                    node_ids.add(neighbor_id)
                    nodes.append({
                        "id": neighbor_id,
                        "label": neighbor.get("name") or neighbor.get("path"),
                        "type": list(neighbor.labels)[0] if neighbor.labels else "Unknown",
                        "is_center": False,
                        "properties": dict(neighbor)
                    })
                
                # Add edges (only direct relationships in the path)
                for rel in rels[:1]:  # Only first hop for clarity
                    edges.append({
                        "source": rel.start_node.get("id"),
                        "target": rel.end_node.get("id"),
                        "type": rel.type,
                        "properties": dict(rel)
                    })
            
            return {
                "center": {
                    "id": center_node.get("id"),
                    "type": center_type,
                    "name": center_node.get("name") or center_node.get("path")
                },
                "nodes": nodes,
                "edges": edges,
                "depth": depth,
                "total_nodes": len(node_ids)
            }
    
    def execute_cypher(self, query: str, parameters: Dict = None) -> List[Dict]:
        """Execute raw Cypher query."""
        with self.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]


# Singleton instance
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j() -> Neo4jClient:
    """Get Neo4j client (FastAPI dependency)."""
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client
