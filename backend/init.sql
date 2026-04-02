-- Initialize PostgreSQL schema for GitNexus Server

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(512) NOT NULL,
    description TEXT,
    default_branch VARCHAR(100) DEFAULT 'main',
    status VARCHAR(50) DEFAULT 'pending',
    last_indexed_at TIMESTAMP,
    last_error TEXT,
    repo_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create revisions table
CREATE TABLE IF NOT EXISTS revisions (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    commit_hash VARCHAR(40) NOT NULL,
    commit_message TEXT,
    author VARCHAR(255),
    committed_at TIMESTAMP,
    is_active INTEGER DEFAULT 0,
    index_status VARCHAR(50) DEFAULT 'pending',
    files_count INTEGER DEFAULT 0,
    symbols_count INTEGER DEFAULT 0,
    chunks_count INTEGER DEFAULT 0,
    neo4j_graph_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index_jobs table
CREATE TABLE IF NOT EXISTS index_jobs (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    revision_id INTEGER REFERENCES revisions(id),
    status VARCHAR(50) DEFAULT 'queued',
    progress_percent FLOAT DEFAULT 0.0,
    files_processed INTEGER DEFAULT 0,
    files_total INTEGER DEFAULT 0,
    symbols_extracted INTEGER DEFAULT 0,
    chunks_indexed INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    failed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create files table
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
    path VARCHAR(512) NOT NULL,
    language VARCHAR(50),
    content_hash VARCHAR(64),
    content TEXT,
    line_count INTEGER,
    neo4j_node_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create symbol_spans table
CREATE TABLE IF NOT EXISTS symbol_spans (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    symbol_type VARCHAR(50) NOT NULL,
    qualified_name VARCHAR(512),
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_column INTEGER,
    end_column INTEGER,
    snippet TEXT,
    docstring TEXT,
    neo4j_node_id VARCHAR(100),
    is_entry_point INTEGER DEFAULT 0,
    is_test INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create file_chunks table with vector embeddings
CREATE TABLE IF NOT EXISTS file_chunks (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    revision_id INTEGER NOT NULL REFERENCES revisions(id) ON DELETE CASCADE,
    symbol_id INTEGER REFERENCES symbol_spans(id),
    content TEXT NOT NULL,
    embedding vector(768),  -- For jina-embeddings-v2-base-code
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    chunk_type VARCHAR(50),
    tsvector TSVECTOR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create search_cache table
CREATE TABLE IF NOT EXISTS search_cache (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(64) UNIQUE NOT NULL,
    query_params JSONB,
    results JSONB,
    hit_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_repo_status ON repositories(status);
CREATE INDEX IF NOT EXISTS idx_revision_repo ON revisions(repository_id);
CREATE INDEX IF NOT EXISTS idx_revision_active ON revisions(is_active) WHERE is_active = 1;
CREATE INDEX IF NOT EXISTS idx_job_status ON index_jobs(status);
CREATE INDEX IF NOT EXISTS idx_job_repo ON index_jobs(repository_id);
CREATE INDEX IF NOT EXISTS idx_file_revision ON files(revision_id);
CREATE INDEX IF NOT EXISTS idx_file_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_symbol_file ON symbol_spans(file_id);
CREATE INDEX IF NOT EXISTS idx_symbol_revision ON symbol_spans(revision_id);
CREATE INDEX IF NOT EXISTS idx_symbol_name ON symbol_spans(name);
CREATE INDEX IF NOT EXISTS idx_symbol_type ON symbol_spans(symbol_type);
CREATE INDEX IF NOT EXISTS idx_chunk_revision ON file_chunks(revision_id);
CREATE INDEX IF NOT EXISTS idx_chunk_symbol ON file_chunks(symbol_id);

-- Create vector index for embeddings
CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON file_chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Create full-text search index
CREATE INDEX IF NOT EXISTS idx_chunk_tsvector ON file_chunks USING GIN(tsvector);

-- Create trigger to update tsvector
CREATE OR REPLACE FUNCTION update_tsvector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.tsvector := to_tsvector('english', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_tsvector ON file_chunks;
CREATE TRIGGER trigger_update_tsvector
    BEFORE INSERT OR UPDATE ON file_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_tsvector();

-- Insert test repository (optional)
-- INSERT INTO repositories (name, url, description, default_branch)
-- VALUES ('example-repo', 'https://github.com/example/repo', 'Example repository', 'main');
