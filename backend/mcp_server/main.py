"""MCP (Model Context Protocol) server implementation."""

import asyncio
import json
from typing import Any, Dict, List, Optional
import structlog
from mcp.server import Server
from mcp.types import TextContent, Tool, ImageContent, EmbeddedResource
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
import httpx

from app.config import settings

logger = structlog.get_logger()

# API client for backend
API_BASE_URL = settings.api_base_url or "http://api:8000"


async def api_request(method: str, path: str, json_data: Dict = None) -> Dict:
    """Make request to backend API."""
    async with httpx.AsyncClient() as client:
        url = f"{API_BASE_URL}{path}"
        
        if method == "GET":
            response = await client.get(url)
        elif method == "POST":
            response = await client.post(url, json=json_data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


# MCP Server
mcp_server = Server("gitnexus")


@mcp_server.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="index_repository",
            description="Trigger indexing for a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {"type": "integer", "description": "Repository ID"}
                },
                "required": ["repo_id"]
            }
        ),
        Tool(
            name="get_index_status",
            description="Get indexing status for a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {"type": "integer", "description": "Repository ID"}
                },
                "required": ["repo_id"]
            }
        ),
        Tool(
            name="search_code",
            description="Search code using semantic and lexical search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "repo_id": {"type": "integer", "description": "Optional: limit to specific repository"},
                    "language": {"type": "string", "description": "Optional: filter by language"},
                    "limit": {"type": "integer", "default": 20}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_symbol_context",
            description="Get 360° context for a symbol (callers, callees, references)",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol_id": {"type": "string", "description": "Symbol ID"}
                },
                "required": ["symbol_id"]
            }
        ),
        Tool(
            name="impact_analysis",
            description="Analyze blast radius: what breaks if I change this?",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {"type": "integer", "description": "Repository ID"},
                    "changed_files": {"type": "array", "items": {"type": "string"}, "description": "List of changed file paths"},
                    "changed_symbols": {"type": "array", "items": {"type": "integer"}, "description": "List of changed symbol IDs"},
                    "depth": {"type": "integer", "default": 3}
                },
                "required": ["repo_id"]
            }
        ),
        Tool(
            name="get_subgraph",
            description="Get centered subgraph for visualization",
            inputSchema={
                "type": "object",
                "properties": {
                    "center_type": {"type": "string", "enum": ["Repository", "Revision", "File", "Symbol"]},
                    "center_id": {"type": "integer", "description": "ID of center node"},
                    "depth": {"type": "integer", "default": 2}
                },
                "required": ["center_type", "center_id"]
            }
        ),
        Tool(
            name="get_file_context",
            description="Get file context with graph neighborhood",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "File ID"},
                    "include_neighbors": {"type": "boolean", "default": True}
                },
                "required": ["file_id"]
            }
        ),
        Tool(
            name="list_repositories",
            description="List all indexed repositories",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute an MCP tool."""
    logger.info("mcp_tool_called", tool=name, arguments=arguments)
    
    try:
        if name == "index_repository":
            result = await api_request(
                "POST", 
                f"/api/v1/repos/{arguments['repo_id']}/index"
            )
            return [TextContent(
                type="text",
                text=f"Indexing job created: ID {result.get('id')}, Status: {result.get('status')}"
            )]
        
        elif name == "get_index_status":
            result = await api_request(
                "GET",
                f"/api/v1/repos/{arguments['repo_id']}"
            )
            return [TextContent(
                type="text",
                text=f"Repository: {result.get('name')}\nStatus: {result.get('status')}\nLast Indexed: {result.get('last_indexed_at')}"
            )]
        
        elif name == "search_code":
            result = await api_request(
                "POST",
                "/api/v1/search",
                {
                    "query": arguments["query"],
                    "repo_id": arguments.get("repo_id"),
                    "language": arguments.get("language"),
                    "limit": arguments.get("limit", 20)
                }
            )
            
            items = result.get("items", [])
            text = f"Found {result.get('total')} results:\n\n"
            
            for item in items[:10]:
                text += f"• {item.get('name')} ({item.get('type')})\n"
                text += f"  Path: {item.get('path')}\n"
                text += f"  Score: {item.get('combined_score', 0):.3f}\n"
                if item.get('snippet'):
                    snippet = item.get('snippet')[:200].replace('\n', ' ')
                    text += f"  Snippet: {snippet}...\n"
                text += "\n"
            
            return [TextContent(type="text", text=text)]
        
        elif name == "get_symbol_context":
            result = await api_request(
                "GET",
                f"/api/v1/symbols/{arguments['symbol_id']}"
            )
            
            text = f"Symbol: {result.get('name')}\n"
            text += f"Type: {result.get('type')}\n"
            text += f"Path: {result.get('file_path')}\n\n"
            
            neighbors = result.get('neighbors', [])
            if neighbors:
                text += f"Related symbols ({len(neighbors)}):\n"
                for n in neighbors[:10]:
                    text += f"  • {n.get('symbol', {}).get('name')} ({n.get('symbol', {}).get('type')})\n"
            
            return [TextContent(type="text", text=text)]
        
        elif name == "impact_analysis":
            result = await api_request(
                "POST",
                "/api/v1/impact-analysis",
                {
                    "repo_id": arguments["repo_id"],
                    "changed_files": arguments.get("changed_files", []),
                    "changed_symbols": arguments.get("changed_symbols", []),
                    "depth": arguments.get("depth", 3)
                }
            )
            
            summary = result.get("summary", {})
            text = f"Impact Analysis Summary:\n\n"
            text += f"Total Affected: {summary.get('total_affected', 0)}\n"
            text += f"Direct Dependencies: {summary.get('direct_dependencies', 0)}\n"
            text += f"Indirect Dependencies: {summary.get('indirect_dependencies', 0)}\n\n"
            
            high_conf = result.get("by_confidence", {}).get("high", [])
            if high_conf:
                text += f"High Confidence Impact ({len(high_conf)} items):\n"
                for item in high_conf[:5]:
                    sym = item.get("symbol", {})
                    text += f"  • {sym.get('name')} (confidence: {item.get('confidence', 0):.2f})\n"
            
            return [TextContent(type="text", text=text)]
        
        elif name == "get_subgraph":
            result = await api_request(
                "POST",
                "/api/v1/graph/subgraph",
                {
                    "center_type": arguments["center_type"],
                    "center_id": arguments["center_id"],
                    "depth": arguments.get("depth", 2)
                }
            )
            
            center = result.get("center", {})
            nodes = result.get("nodes", [])
            edges = result.get("edges", [])
            
            text = f"Subgraph centered on {center.get('name')} ({center.get('type')})\n\n"
            text += f"Nodes: {len(nodes)}\n"
            text += f"Edges: {len(edges)}\n\n"
            
            text += "Connected nodes:\n"
            for node in nodes[:15]:
                if not node.get("is_center"):
                    text += f"  • {node.get('label')} ({node.get('type')})\n"
            
            return [TextContent(type="text", text=text)]
        
        elif name == "get_file_context":
            result = await api_request(
                "GET",
                f"/api/v1/files/{arguments['file_id']}",
                {"include_neighbors": arguments.get("include_neighbors", True)}
            )
            
            text = f"File: {result.get('path')}\n"
            text += f"Language: {result.get('language')}\n"
            text += f"Lines: {result.get('line_count')}\n\n"
            
            symbols = result.get("symbols", [])
            if symbols:
                text += f"Symbols ({len(symbols)}):\n"
                for sym in symbols[:10]:
                    text += f"  • {sym.get('name')} ({sym.get('type')})\n"
            
            return [TextContent(type="text", text=text)]
        
        elif name == "list_repositories":
            result = await api_request("GET", "/api/v1/repos")
            
            text = f"Repositories ({len(result)}):\n\n"
            for repo in result[:20]:
                text += f"• {repo.get('name')} (ID: {repo.get('id')})\n"
                text += f"  Status: {repo.get('status')}\n"
                text += f"  URL: {repo.get('url')}\n\n"
            
            return [TextContent(type="text", text=text)]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        logger.error("mcp_tool_error", tool=name, error=str(e))
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# SSE transport setup
sse = SseServerTransport("/mcp/v1/sse")


async def handle_sse(scope, receive, send):
    """Handle SSE connection."""
    async with sse.connect_sse(scope, receive, send) as streams:
        await mcp_server.run(
            streams[0], streams[1],
            mcp_server.create_initialization_options()
        )


# Starlette app for HTTP transport
app = Starlette(
    debug=settings.debug,
    routes=[
        Route("/mcp/v1/sse", endpoint=handle_sse),
    ]
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
