"""Repository management service."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from git import Repo
from git.exc import GitCommandError
import os
import shutil
import structlog

from app.database import Repository, Revision, IndexJob
from app.neo4j_client import Neo4jClient
from app.config import settings

logger = structlog.get_logger()


class RepoService:
    """Service for managing repositories and indexing jobs."""
    
    def __init__(self, db: Session, neo4j: Optional[Neo4jClient] = None):
        self.db = db
        self.neo4j = neo4j
        self.repo_mirror_path = settings.repo_mirror_path
    
    def create_repository(self, repo_data) -> Repository:
        """Create a new repository record."""
        repo = Repository(
            name=repo_data.name,
            url=str(repo_data.url),
            description=repo_data.description,
            default_branch=repo_data.default_branch,
            status="pending"
        )
        
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)
        
        # Create Neo4j node if available
        if self.neo4j:
            self.neo4j.create_repository(
                repo.id,
                repo.name,
                repo.url,
                {"default_branch": repo.default_branch}
            )
        
        return repo
    
    def get_repository(self, repo_id: int) -> Optional[Repository]:
        """Get repository by ID."""
        return self.db.query(Repository).filter(Repository.id == repo_id).first()
    
    def list_repositories(self, skip: int = 0, limit: int = 100) -> List[Repository]:
        """List all repositories."""
        return self.db.query(Repository).offset(skip).limit(limit).all()
    
    def create_index_job(self, repo_id: int, revision_id: Optional[int] = None) -> IndexJob:
        """Create a new indexing job."""
        job = IndexJob(
            repository_id=repo_id,
            revision_id=revision_id,
            status="queued",
            progress_percent=0.0
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        return job
    
    def list_jobs(self, repo_id: int) -> List[IndexJob]:
        """List indexing jobs for a repository."""
        return self.db.query(IndexJob).filter(
            IndexJob.repository_id == repo_id
        ).order_by(IndexJob.created_at.desc()).all()
    
    def get_job(self, job_id: int) -> Optional[IndexJob]:
        """Get indexing job by ID."""
        return self.db.query(IndexJob).filter(IndexJob.id == job_id).first()
    
    def clone_or_update_repo(self, repo: Repository) -> str:
        """
        Clone repository or fetch updates.
        
        Returns:
            Path to local repository mirror
        """
        local_path = os.path.join(self.repo_mirror_path, f"repo_{repo.id}")
        
        try:
            if os.path.exists(local_path):
                # Update existing repo
                logger.info("updating_repo", repo_id=repo.id, path=local_path)
                git_repo = Repo(local_path)
                git_repo.remotes.origin.fetch()
                
                # Checkout default branch
                git_repo.git.checkout(repo.default_branch)
                git_repo.git.pull("origin", repo.default_branch)
            else:
                # Clone new repo
                logger.info("cloning_repo", repo_id=repo.id, url=repo.url)
                os.makedirs(local_path, exist_ok=True)
                
                # Use token if available for private repos
                clone_url = repo.url
                if settings.github_token and "github.com" in repo.url:
                    clone_url = repo.url.replace(
                        "https://",
                        f"https://{settings.github_token}@"
                    )
                
                Repo.clone_from(clone_url, local_path, branch=repo.default_branch, depth=1)
            
            return local_path
            
        except GitCommandError as e:
            logger.error("git_operation_failed", repo_id=repo.id, error=str(e))
            raise
        except Exception as e:
            logger.error("repo_clone_failed", repo_id=repo.id, error=str(e))
            raise
    
    def get_repo_head_commit(self, local_path: str) -> tuple:
        """
        Get HEAD commit info.
        
        Returns:
            (commit_hash, commit_message, author, committed_datetime)
        """
        try:
            repo = Repo(local_path)
            head = repo.head.commit
            return (
                head.hexsha,
                head.message.strip(),
                str(head.author),
                head.committed_datetime
            )
        except Exception as e:
            logger.error("get_head_commit_failed", path=local_path, error=str(e))
            raise
    
    def delete_repository(self, repo_id: int) -> bool:
        """Delete repository and all associated data."""
        repo = self.get_repository(repo_id)
        if not repo:
            return False
        
        # Delete local mirror
        local_path = os.path.join(self.repo_mirror_path, f"repo_{repo.id}")
        if os.path.exists(local_path):
            shutil.rmtree(local_path)
        
        # Delete from database (cascades to jobs, files, etc.)
        self.db.delete(repo)
        self.db.commit()
        
        # Note: Neo4j cleanup would happen via separate job
        
        return True
