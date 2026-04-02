"""Graph query service."""

from typing import Dict, Any
from sqlalchemy.orm import Session
import structlog

from app.neo4j_client import Neo4jClient
from app.models import SubgraphRequest, SubgraphResult, GraphNode, GraphEdge

logger = structlog.get_logger()


class GraphService:
    """Graph query and visualization service."""
    
    def __init__(self, db: Session, neo4j: Neo4jClient):
        self.db = db
        self.neo4j = neo4j
    
    def get_subgraph(self, request: SubgraphRequest) -> SubgraphResult:
        """Get centered subgraph for visualization."""
        result = self.neo4j.get_subgraph(
            center_type=request.center_type,
            center_id=request.center_id,
            depth=request.depth,
            limit=request.limit
        )
        
        # Convert to response models
        nodes = [GraphNode(**node) for node in result.get("nodes", [])]
        edges = [GraphEdge(**edge) for edge in result.get("edges", [])]
        
        return SubgraphResult(
            center=result.get("center", {}),
            nodes=nodes,
            edges=edges,
            depth=request.depth,
            total_nodes=result.get("total_nodes", 0)
        )
    
    def get_schema(self) -> Dict[str, Any]:
        """Get graph schema information."""
        with self.neo4j.session() as session:
            # Get node labels
            node_result = session.run("""
                CALL db.labels() YIELD label
                RETURN collect(label) as labels
            """)
            labels = node_result.single()["labels"]
            
            # Get relationship types
            rel_result = session.run("""
                CALL db.relationshipTypes() YIELD relationshipType
                RETURN collect(relationshipType) as types
            """)
            rel_types = rel_result.single()["types"]
            
            # Get property keys
            prop_result = session.run("""
                CALL db.propertyKeys() YIELD propertyKey
                RETURN collect(propertyKey) as keys
            """)
            properties = prop_result.single()["keys"]
            
            return {
                "node_labels": labels,
                "relationship_types": rel_types,
                "property_keys": properties[:100],  # Limit
                "description": {
                    "Repository": "Root node for a codebase",
                    "Revision": "Specific commit/version",
                    "File": "Source code file",
                    "Symbol": "Function, class, method, etc.",
                    "relationships": {
                        "CONTAINS": "Revision contains Files",
                        "DEFINES": "File defines Symbols",
                        "CALLS": "Symbol calls another Symbol",
                        "REFERENCES": "Symbol references another Symbol",
                        "IMPORTS": "File imports Symbol",
                        "INHERITS": "Class/Interface inheritance"
                    }
                }
            }
    
    def execute_cypher(self, query: str, parameters: Dict) -> List[Dict]:
        """Execute raw Cypher query."""
        return self.neo4j.execute_cypher(query, parameters)
    
    def get_symbol_dependencies(self, symbol_id: int, direction: str = "both") -> Dict[str, Any]:
        """Get symbol dependencies (callers and callees)."""
        neighbors = self.neo4j.get_symbol_neighbors(
            symbol_id=symbol_id,
            direction=direction,
            depth=1,
            limit=50
        )
        
        # Categorize
        callers = [n for n in neighbors if any(p.get("from") == n["symbol"]["name"] for p in n.get("path", []))]
        callees = [n for n in neighbors if any(p.get("to") == n["symbol"]["name"] for p in n.get("path", []))]
        
        return {
            "symbol_id": symbol_id,
            "total_relationships": len(neighbors),
            "callers": callers[:20],
            "callees": callees[:20],
            "sample_paths": neighbors[:5]
        }
    
    def find_paths(
        self,
        from_symbol_id: int,
        to_symbol_id: int,
        max_depth: int = 4
    ) -> Dict[str, Any]:
        """Find all paths between two symbols."""
        with self.neo4j.session() as session:
            result = session.run("""
                MATCH path = (start:Symbol {id: $from_id})-[*1..$max_depth]-(end:Symbol {id: $to_id})
                RETURN path, length(path) as path_length
                LIMIT 10
            """, from_id=from_symbol_id, to_id=to_symbol_id, max_depth=max_depth)
            
            paths = []
            for record in result:
                path = record["path"]
                path_length = record["path_length"]
                
                # Extract nodes and relationships
                nodes = []
                for node in path.nodes:
                    nodes.append({
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "type": list(node.labels)[0] if node.labels else "Unknown"
                    })
                
                rels = []
                for rel in path.relationships:
                    rels.append({
                        "type": rel.type,
                        "from": rel.start_node.get("name"),
                        "to": rel.end_node.get("name")
                    })
                
                paths.append({
                    "length": path_length,
                    "nodes": nodes,
                    "relationships": rels
                })
            
            return {
                "from": from_symbol_id,
                "to": to_symbol_id,
                "paths_found": len(paths),
                "paths": paths
            }
