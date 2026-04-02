"""Configuration settings for GitNexus Server."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # Application
    app_name: str = "GitNexus Server"
    debug: bool = False
    secret_key: str = "change-me-in-production"
    
    # Database
    database_url: str = "postgresql://gitnexus:gitnexus_secret@localhost:5432/gitnexus"
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "gitnexus_graph"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Embeddings
    embedding_model: str = "jina-embeddings-v2-base-code"
    embedding_provider: str = "local"  # local, openai
    openai_api_key: str | None = None
    embedding_dimensions: int = 768  # For jina-embeddings-v2-base-code
    
    # Indexing
    max_workers: int = 2
    repo_mirror_path: str = "/app/repos"
    github_token: str | None = None
    
    # Search
    default_search_limit: int = 20
    max_search_limit: int = 100
    graph_expansion_depth: int = 2
    
    # MCP
    mcp_transport: str = "sse"  # sse, stdio
    
    class Config:
        env_prefix = ""  # Use exact env var names
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
