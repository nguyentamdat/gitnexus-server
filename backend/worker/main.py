"""Background worker for repository indexing."""

import os
import time
import json
from pathlib import Path
from typing import Optional
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.database import (
    get_db, Repository, Revision, IndexJob, File, 
    SymbolSpan, FileChunk, engine
)
from app.neo4j_client import Neo4jClient
from app.parser import get_parser, FileParseResult
from app.embeddings import get_embeddings

logger = structlog.get_logger()


class IndexerWorker:
    """Background worker that indexes repositories."""
    
    def __init__(self):
        self.db = Session(bind=engine)
        self.neo4j = Neo4jClient()
        self.parser = get_parser()
        self.embeddings = get_embeddings()
        self.repo_mirror_path = settings.repo_mirror_path
    
    def run(self):
        """Main worker loop."""
        logger.info("indexer_worker_started")
        
        while True:
            try:
                # Find queued jobs
                job = self.db.query(IndexJob).filter(
                    IndexJob.status == "queued"
                ).order_by(IndexJob.created_at).first()
                
                if job:
                    self._process_job(job)
                else:
                    # No jobs, sleep
                    time.sleep(5)
                    
            except Exception as e:
                logger.error("worker_loop_error", error=str(e))
                time.sleep(10)
    
    def _process_job(self, job: IndexJob):
        """Process a single indexing job."""
        logger.info("processing_job", job_id=job.id, repo_id=job.repository_id)
        
        # Update job status
        job.status = "running"
        job.started_at = time.time()
        self.db.commit()
        
        try:
            # Get repository
            repo = self.db.query(Repository).filter(
                Repository.id == job.repository_id
            ).first()
            
            if not repo:
                raise ValueError(f"Repository {job.repository_id} not found")
            
            # Clone/update repository
            local_path = self._clone_or_update_repo(repo)
            
            # Get commit info
            commit_hash, commit_message, author, committed_at = self._get_commit_info(local_path)
            
            # Create revision
            revision = Revision(
                repository_id=repo.id,
                commit_hash=commit_hash,
                commit_message=commit_message,
                author=author,
                committed_at=committed_at,
                index_status="processing"
            )
            self.db.add(revision)
            self.db.commit()
            self.db.refresh(revision)
            
            job.revision_id = revision.id
            self.db.commit()
            
            # Create Neo4j revision node
            self.neo4j.create_revision(
                revision_id=revision.id,
                repo_id=repo.id,
                commit_hash=commit_hash,
                commit_message=commit_message,
                author=author
            )
            
            # Index files
            self._index_repository(revision, local_path, job)
            
            # Mark revision as active
            # Deactivate previous revisions
            self.db.query(Revision).filter(
                Revision.repository_id == repo.id,
                Revision.id != revision.id
            ).update({"is_active": 0})
            
            revision.is_active = 1
            revision.index_status = "completed"
            self.db.commit()
            
            # Update job
            job.status = "completed"
            job.completed_at = time.time()
            job.progress_percent = 100.0
            self.db.commit()
            
            # Update repository
            repo.status = "active"
            repo.last_indexed_at = time.time()
            self.db.commit()
            
            logger.info("job_completed", job_id=job.id, repo_id=repo.id)
            
        except Exception as e:
            logger.error("job_failed", job_id=job.id, error=str(e))
            
            job.status = "failed"
            job.failed_at = time.time()
            job.error_message = str(e)
            self.db.commit()
            
            # Update repository status
            if repo:
                repo.status = "error"
                repo.last_error = str(e)
                self.db.commit()
    
    def _clone_or_update_repo(self, repo: Repository) -> str:
        """Clone or update repository mirror."""
        from git import Repo as GitRepo
        from git.exc import GitCommandError
        
        local_path = os.path.join(self.repo_mirror_path, f"repo_{repo.id}")
        
        try:
            if os.path.exists(os.path.join(local_path, ".git")):
                # Update
                logger.info("updating_repo", repo_id=repo.id, path=local_path)
                git_repo = GitRepo(local_path)
                git_repo.remotes.origin.fetch()
                git_repo.git.checkout(repo.default_branch)
                git_repo.git.pull("origin", repo.default_branch)
            else:
                # Clone
                logger.info("cloning_repo", repo_id=repo.id, url=repo.url)
                os.makedirs(local_path, exist_ok=True)
                
                clone_url = repo.url
                if settings.github_token and "github.com" in repo.url:
                    clone_url = repo.url.replace(
                        "https://",
                        f"https://{settings.github_token}@"
                    )
                
                GitRepo.clone_from(clone_url, local_path, branch=repo.default_branch, depth=1)
            
            return local_path
            
        except GitCommandError as e:
            logger.error("git_operation_failed", repo_id=repo.id, error=str(e))
            raise
    
    def _get_commit_info(self, local_path: str) -> tuple:
        """Get HEAD commit information."""
        from git import Repo
        
        repo = Repo(local_path)
        head = repo.head.commit
        
        return (
            head.hexsha,
            head.message.strip(),
            str(head.author),
            head.committed_datetime
        )
    
    def _index_repository(self, revision: Revision, local_path: str, job: IndexJob):
        """Index all files in repository."""
        # Find all source files
        source_files = []
        for root, dirs, files in os.walk(local_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in [
                ".git", "node_modules", "__pycache__", "venv", ".venv",
                "dist", "build", ".next", ".cache", "target"
            ]]
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, local_path)
                source_files.append(rel_path)
        
        job.files_total = len(source_files)
        self.db.commit()
        
        logger.info("indexing_files", revision_id=revision.id, total_files=len(source_files))
        
        # Process each file
        for i, rel_path in enumerate(source_files):
            try:
                self._index_file(revision, local_path, rel_path)
                
                # Update progress
                job.files_processed = i + 1
                job.progress_percent = (i + 1) / len(source_files) * 100
                
                if (i + 1) % 10 == 0:
                    self.db.commit()
                    
            except Exception as e:
                logger.warning("file_index_failed", path=rel_path, error=str(e))
                continue
        
        self.db.commit()
        
        logger.info("repository_indexed", revision_id=revision.id, files=len(source_files))
    
    def _index_file(self, revision: Revision, local_path: str, rel_path: str):
        """Index a single file."""
        full_path = os.path.join(local_path, rel_path)
        
        # Read file
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.warning("file_read_failed", path=rel_path, error=str(e))
            return
        
        # Skip very large files
        if len(content) > 1000000:  # 1MB
            logger.debug("skipping_large_file", path=rel_path, size=len(content))
            return
        
        # Detect language
        language = self.parser.detect_language(rel_path)
        
        # Create file record
        file_record = File(
            revision_id=revision.id,
            path=rel_path,
            language=language,
            line_count=len(content.splitlines()),
            content=content if len(content) < 50000 else None  # Store small files
        )
        self.db.add(file_record)
        self.db.flush()
        
        # Create Neo4j file node
        neo4j_file_id = self.neo4j.create_file(
            file_id=file_record.id,
            revision_id=revision.id,
            path=rel_path,
            language=language,
            metadata={"line_count": file_record.line_count}
        )
        file_record.neo4j_node_id = neo4j_file_id
        
        # Parse file
        if language:
            parse_result = self.parser.parse_file(full_path, content)
            
            if parse_result:
                # Index symbols
                for symbol in parse_result.symbols:
                    self._index_symbol(revision, file_record, symbol)
                
                # Index chunks for search
                self._index_chunks(revision, file_record, content, parse_result)
        else:
            # Index as generic text
            self._index_chunks(revision, file_record, content, None)
        
        revision.files_count += 1
    
    def _index_symbol(self, revision: Revision, file_record: File, symbol):
        """Index a code symbol."""
        # Create symbol record
        symbol_record = SymbolSpan(
            file_id=file_record.id,
            revision_id=revision.id,
            name=symbol.name,
            symbol_type=symbol.symbol_type,
            qualified_name=symbol.qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            start_column=symbol.start_column,
            end_column=symbol.end_column,
            docstring=symbol.docstring,
            is_entry_point=symbol.is_entry_point,
            snippet=None  # Would extract from file content
        )
        self.db.add(symbol_record)
        self.db.flush()
        
        # Create Neo4j symbol node
        neo4j_symbol_id = self.neo4j.create_symbol(
            symbol_id=symbol_record.id,
            file_id=file_record.id,
            revision_id=revision.id,
            name=symbol.name,
            symbol_type=symbol.symbol_type,
            qualified_name=symbol.qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            is_entry_point=symbol.is_entry_point
        )
        symbol_record.neo4j_node_id = neo4j_symbol_id
        
        revision.symbols_count += 1
    
    def _index_chunks(self, revision: Revision, file_record: File, content: str, parse_result: Optional[FileParseResult]):
        """Index file chunks for semantic search."""
        lines = content.splitlines()
        
        if parse_result and parse_result.symbols:
            # Create chunks around symbols
            for symbol in parse_result.symbols:
                # Extract symbol content
                start_idx = max(0, symbol.start_line - 1)
                end_idx = min(len(lines), symbol.end_line)
                chunk_content = '\n'.join(lines[start_idx:end_idx])
                
                if len(chunk_content) > 50:  # Skip tiny chunks
                    self._create_chunk(revision, file_record, chunk_content, symbol)
        else:
            # Create chunks by fixed size
            chunk_size = 50
            for i in range(0, len(lines), chunk_size):
                chunk_lines = lines[i:i + chunk_size]
                chunk_content = '\n'.join(chunk_lines)
                
                if len(chunk_content) > 50:
                    self._create_chunk(
                        revision, file_record, chunk_content, None,
                        start_line=i + 1, end_line=min(i + chunk_size, len(lines))
                    )
    
    def _create_chunk(self, revision: Revision, file_record: File, content: str, symbol=None, start_line=0, end_line=0):
        """Create and embed a content chunk."""
        try:
            # Generate embedding
            embedding = self.embeddings.embed_text(content[:1000])  # Limit for speed
            
            # Create chunk record
            chunk = FileChunk(
                file_id=file_record.id,
                revision_id=revision.id,
                symbol_id=symbol.id if symbol else None,
                content=content[:5000],  # Store limited content
                embedding=embedding,
                start_line=start_line or (symbol.start_line if symbol else 0),
                end_line=end_line or (symbol.end_line if symbol else 0),
                chunk_type="symbol" if symbol else "section"
            )
            self.db.add(chunk)
            
            revision.chunks_count += 1
            
        except Exception as e:
            logger.warning("chunk_embedding_failed", error=str(e))


def main():
    """Entry point for worker."""
    worker = IndexerWorker()
    worker.run()


if __name__ == "__main__":
    main()
