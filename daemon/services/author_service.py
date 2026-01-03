"""
Author Management Service

Manages authors and channels from both local database and potentially GetReceipts.
Provides search, create, and list functionality.
"""

import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.knowledge_system.services.database_service import DatabaseService
    from src.knowledge_system.database.models import MediaSource
    from sqlalchemy import select, func, distinct
    DATABASE_AVAILABLE = True
except ImportError as e:
    DATABASE_AVAILABLE = False
    import_error = str(e)

from daemon.models.schemas import Author, AuthorListResponse, CreateAuthorRequest

logger = logging.getLogger(__name__)


class AuthorService:
    """
    Service for managing authors and channels.
    
    Queries the local SQLite database for existing authors (from uploaded content)
    and provides functionality to create new manual authors.
    """

    def __init__(self, db_service: Optional[any] = None):
        """Initialize author service."""
        if not DATABASE_AVAILABLE:
            raise RuntimeError(f"Database not available: {import_error}")
        
        self.db_service = db_service or DatabaseService()
        logger.info("AuthorService initialized")

    def get_authors(
        self, 
        search: Optional[str] = None, 
        limit: int = 100,
        offset: int = 0
    ) -> AuthorListResponse:
        """
        Get list of authors from database.
        
        Args:
            search: Optional search query to filter authors by name
            limit: Maximum number of authors to return
            offset: Number of authors to skip (for pagination)
            
        Returns:
            AuthorListResponse with authors and total count
        """
        logger.info(f"Getting authors (search='{search}', limit={limit}, offset={offset})")
        
        try:
            with self.db_service.get_session() as session:
                # Query for unique uploaders from media_sources
                query = (
                    select(
                        MediaSource.uploader.label('name'),
                        MediaSource.uploader_id.label('id'),
                        MediaSource.organization.label('type_hint'),
                        func.count(MediaSource.source_id).label('source_count')
                    )
                    .where(MediaSource.uploader.isnot(None))
                    .group_by(MediaSource.uploader, MediaSource.uploader_id, MediaSource.organization)
                )
                
                # Apply search filter if provided
                if search:
                    query = query.where(MediaSource.uploader.ilike(f"%{search}%"))
                
                # Apply pagination
                query = query.offset(offset).limit(limit)
                
                results = session.execute(query).all()
                
                # Get total count (without pagination)
                count_query = (
                    select(func.count(distinct(MediaSource.uploader)))
                    .where(MediaSource.uploader.isnot(None))
                )
                if search:
                    count_query = count_query.where(MediaSource.uploader.ilike(f"%{search}%"))
                
                total = session.execute(count_query).scalar() or 0
                
                # Convert to Author objects
                authors = []
                for row in results:
                    # Determine author type based on available information
                    author_type = "channel"  # Default for YouTube content
                    if row.type_hint:
                        author_type = "organization"
                    
                    author = Author(
                        id=row.id or str(uuid.uuid4()),  # Generate ID if not available
                        name=row.name,
                        type=author_type,
                        bio=None,  # No bio available from media_sources
                        source_count=row.source_count
                    )
                    authors.append(author)
                
                logger.info(f"Found {len(authors)} authors (total: {total})")
                
                return AuthorListResponse(
                    authors=authors,
                    total=total
                )
        
        except Exception as e:
            logger.error(f"Failed to get authors: {e}")
            # Return empty response on error
            return AuthorListResponse(authors=[], total=0)

    def create_author(self, request: CreateAuthorRequest) -> Author:
        """
        Create a new author entry.
        
        For now, this creates a virtual author that can be used for metadata.
        In the future, this could be persisted to a dedicated authors table.
        
        Args:
            request: CreateAuthorRequest with author details
            
        Returns:
            Created Author object
        """
        logger.info(f"Creating new author: {request.name} (type: {request.type})")
        
        # Generate a unique ID for the new author
        author_id = f"manual_{uuid.uuid4().hex[:12]}"
        
        author = Author(
            id=author_id,
            name=request.name,
            type=request.type,
            bio=request.bio,
            source_count=0  # New author starts with 0 sources
        )
        
        logger.info(f"Created author: {author.name} (ID: {author.id})")
        
        return author

    def get_author_by_id(self, author_id: str) -> Optional[Author]:
        """
        Get a specific author by ID.
        
        Args:
            author_id: Author ID to lookup
            
        Returns:
            Author object if found, None otherwise
        """
        try:
            with self.db_service.get_session() as session:
                # Query for specific uploader_id
                result = session.execute(
                    select(
                        MediaSource.uploader.label('name'),
                        MediaSource.uploader_id.label('id'),
                        MediaSource.organization.label('type_hint'),
                        func.count(MediaSource.source_id).label('source_count')
                    )
                    .where(MediaSource.uploader_id == author_id)
                    .group_by(MediaSource.uploader, MediaSource.uploader_id, MediaSource.organization)
                ).first()
                
                if not result:
                    return None
                
                # Determine author type
                author_type = "channel"
                if result.type_hint:
                    author_type = "organization"
                
                return Author(
                    id=result.id,
                    name=result.name,
                    type=author_type,
                    bio=None,
                    source_count=result.source_count
                )
        
        except Exception as e:
            logger.error(f"Failed to get author by ID: {e}")
            return None


# Global instance
author_service = AuthorService() if DATABASE_AVAILABLE else None

