"""Database models and connection."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, 
    Text, ForeignKey, Float, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from pgvector.sqlalchemy import Vector

from app.config import settings

Base = declarative_base()

# Database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Get database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


# ==================== Models ====================

class Repository(Base):
    """Registered git repository."""
    __tablename__ = "repositories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)
    description = Column(Text)
    default_branch = Column(String(100), default="main")
    
    # Status
    status = Column(String(50), default="pending")  # pending, indexing, active, error
    last_indexed_at = Column(DateTime)
    last_error = Column(Text)
    
    # Metadata
    repo_metadata = Column(JSON)  # clone info, stats, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = relationship("IndexJob", back_populates="repository", lazy="dynamic")
    revisions = relationship("Revision", back_populates="repository", lazy="dynamic")


class Revision(Base):
    """Indexed revision (commit) of a repository."""
    __tablename__ = "revisions"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    commit_hash = Column(String(40), nullable=False)
    commit_message = Column(Text)
    author = Column(String(255))
    committed_at = Column(DateTime)
    
    # Status
    is_active = Column(Integer, default=0)  # 0 or 1 (only one active per repo)
    index_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    
    # Stats
    files_count = Column(Integer, default=0)
    symbols_count = Column(Integer, default=0)
    chunks_count = Column(Integer, default=0)
    
    # Neo4j reference (for cleanup)
    neo4j_graph_id = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    repository = relationship("Repository", back_populates="revisions")
    files = relationship("File", back_populates="revision", lazy="dynamic")


class IndexJob(Base):
    """Background indexing job."""
    __tablename__ = "index_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    revision_id = Column(Integer, ForeignKey("revisions.id"), nullable=True)
    
    # Status
    status = Column(String(50), default="queued")  # queued, running, completed, failed, cancelled
    progress_percent = Column(Float, default=0.0)
    
    # Stats
    files_processed = Column(Integer, default=0)
    files_total = Column(Integer, default=0)
    symbols_extracted = Column(Integer, default=0)
    chunks_indexed = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    repository = relationship("Repository", back_populates="jobs")


class File(Base):
    """Source code file."""
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    revision_id = Column(Integer, ForeignKey("revisions.id"), nullable=False)
    
    path = Column(String(512), nullable=False, index=True)
    language = Column(String(50), index=True)
    content_hash = Column(String(64))
    
    # Content (optional, for small files)
    content = Column(Text)
    line_count = Column(Integer)
    
    # Graph reference
    neo4j_node_id = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    revision = relationship("Revision", back_populates="files")
    chunks = relationship("FileChunk", back_populates="file", lazy="dynamic")
    symbols = relationship("SymbolSpan", back_populates="file", lazy="dynamic")
    
    # Indexes
    __table_args__ = (
        Index('idx_file_revision_path', 'revision_id', 'path'),
    )


class SymbolSpan(Base):
    """Extracted symbol (function, class, etc.) location."""
    __tablename__ = "symbol_spans"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    revision_id = Column(Integer, ForeignKey("revisions.id"), nullable=False)
    
    # Symbol info
    name = Column(String(255), nullable=False, index=True)
    symbol_type = Column(String(50), nullable=False, index=True)  # function, class, method, interface, etc.
    qualified_name = Column(String(512), index=True)
    
    # Location
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    start_column = Column(Integer)
    end_column = Column(Integer)
    
    # Code snippet
    snippet = Column(Text)
    
    # Documentation
    docstring = Column(Text)
    
    # Graph reference
    neo4j_node_id = Column(String(100))
    
    # For impact analysis
    is_entry_point = Column(Integer, default=0)
    is_test = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    file = relationship("File", back_populates="symbols")
    
    # Indexes
    __table_args__ = (
        Index('idx_symbol_revision', 'revision_id', 'symbol_type'),
        Index('idx_symbol_name', 'name'),
    )


class FileChunk(Base):
    """Chunk of code for vector search."""
    __tablename__ = "file_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    revision_id = Column(Integer, ForeignKey("revisions.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("symbol_spans.id"), nullable=True)
    
    # Chunk content
    content = Column(Text, nullable=False)
    embedding = Vector(settings.embedding_dimensions)
    
    # Location
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    
    # Search metadata
    chunk_type = Column(String(50))  # symbol, section, doc, etc.
    tsvector = Column(Text)  # PostgreSQL FTS vector (as string for simplicity)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    file = relationship("File", back_populates="chunks")
    
    # Indexes
    __table_args__ = (
        Index('idx_chunk_revision', 'revision_id', 'chunk_type'),
    )


class SearchCache(Base):
    """Cache for expensive search queries."""
    __tablename__ = "search_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    query_hash = Column(String(64), unique=True, index=True)
    query_params = Column(JSON)
    results = Column(JSON)
    hit_count = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
