# GitNexus Server

A single-team server version of GitNexus — code intelligence with knowledge graphs, persistent storage, and MCP protocol support.

## Features

- 🔍 **Knowledge Graph Construction** — Parse repos into queryable graphs using Tree-sitter
- 🧠 **Hybrid Search** — Vector (pgvector) + Lexical (PostgreSQL FTS) + Graph (Neo4j)
- 💥 **Impact Analysis** — Blast radius detection before making changes
- 🔌 **MCP Protocol** — Native support for Claude, Cursor, Windsurf
- 🌐 **Web Dashboard** — Visual graph exploration and search interface
- 🐳 **Docker Deploy** — Single-command deployment for your team

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitNexus Server                        │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React)  │  FastAPI (REST)  │  MCP Gateway (SSE/HTTP) │
├────────────────────┴──────────────────┴─────────────────────────┤
│                     Shared Python Domain                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  ingest  │  │  parser  │  │  search  │  │ impact_analyzer │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL + pgvector      │      Neo4j                        │
│  (metadata, vectors, jobs)  │      (graph structure)          │
├─────────────────────────────────────────────────────────────────┤
│                     Indexer Worker                               │
│  Tree-sitter → Embeddings → Write to both databases              │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI (Python 3.12) |
| Graph Database | Neo4j 5.x |
| Vector Store | PostgreSQL 16 + pgvector |
| Parsing | Tree-sitter |
| Frontend | React + Vite + TypeScript + Cytoscape.js |
| MCP | Official Python MCP SDK |
| Deployment | Docker Compose |

## Quick Start

```bash
# 1. Clone and start services
docker-compose up -d

# 2. Index your first repo
curl -X POST http://localhost:8000/api/v1/repos \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/your-org/your-repo", "name": "my-repo"}'

# 3. Trigger indexing
curl -X POST http://localhost:8000/api/v1/repos/1/index

# 4. Open dashboard
open http://localhost:3000
```

## API Endpoints

### Repositories
- `POST /api/v1/repos` — Register a repository
- `GET /api/v1/repos` — List repositories
- `POST /api/v1/repos/{id}/index` — Trigger indexing
- `GET /api/v1/repos/{id}/status` — Get indexing status

### Search
- `POST /api/v1/search` — Semantic/code search
- `GET /api/v1/symbols/{id}` — Get symbol details
- `GET /api/v1/files/{id}` — Get file context

### Graph
- `POST /api/v1/graph/subgraph` — Get centered subgraph
- `POST /api/v1/impact-analysis` — Blast radius analysis
- `GET /api/v1/graph/schema` — Graph schema information

### MCP
- `GET /mcp/v1/sse` — MCP SSE endpoint (for Claude/Cursor)
- WebSocket `/mcp/v1/ws` — Alternative transport

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design and data flow
- [API Reference](docs/API.md) — REST API documentation
- [MCP Protocol](docs/MCP.md) — Model Context Protocol integration
- [Deployment](docs/DEPLOYMENT.md) — Docker and production setup
- [Contributing](CONTRIBUTING.md) — Development guidelines

## License

MIT License — See [LICENSE](LICENSE) for details.

## Credits

Inspired by [GitNexus](https://github.com/abhigyanpatwari/gitnexus) — the zero-server code intelligence engine. This is a server-hosted adaptation for team deployments.
