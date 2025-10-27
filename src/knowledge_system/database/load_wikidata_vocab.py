"""Load WikiData vocabulary from JSON seed file into database."""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from .claim_models import WikiDataCategory, WikiDataAlias

logger = logging.getLogger(__name__)


def load_wikidata_vocabulary(session: Session, seed_file: Path | None = None) -> int:
    """
    Load WikiData categories from JSON seed file into database.
    
    Args:
        session: SQLAlchemy session
        seed_file: Path to seed JSON file (defaults to wikidata_seed.json)
    
    Returns:
        Number of categories loaded
    """
    if seed_file is None:
        seed_file = Path(__file__).parent / "wikidata_seed.json"
    
    if not seed_file.exists():
        logger.error(f"WikiData seed file not found: {seed_file}")
        return 0
    
    # Load seed data
    with open(seed_file) as f:
        data = json.load(f)
    
    categories = data.get("categories", [])
    logger.info(f"Loading {len(categories)} WikiData categories from {seed_file}")
    
    loaded_count = 0
    
    for cat_data in categories:
        wikidata_id = cat_data["wikidata_id"]
        
        # Check if category already exists
        existing = session.query(WikiDataCategory).filter_by(
            wikidata_id=wikidata_id
        ).first()
        
        if existing:
            # Update existing category
            existing.category_name = cat_data["category_name"]
            existing.category_description = cat_data.get("description")
            existing.parent_wikidata_id = cat_data.get("parent_id")
            existing.level = cat_data.get("level")
            logger.debug(f"Updated WikiData category: {wikidata_id} ({cat_data['category_name']})")
        else:
            # Create new category
            category = WikiDataCategory(
                wikidata_id=wikidata_id,
                category_name=cat_data["category_name"],
                category_description=cat_data.get("description"),
                parent_wikidata_id=cat_data.get("parent_id"),
                level=cat_data.get("level")
            )
            session.add(category)
            loaded_count += 1
            logger.debug(f"Created WikiData category: {wikidata_id} ({cat_data['category_name']})")
        
        # Add aliases
        aliases = cat_data.get("aliases", [])
        if aliases:
            # Delete existing aliases
            session.query(WikiDataAlias).filter_by(wikidata_id=wikidata_id).delete()
            
            # Add new aliases
            for alias in aliases:
                alias_obj = WikiDataAlias(
                    wikidata_id=wikidata_id,
                    alias=alias
                )
                session.add(alias_obj)
    
    session.commit()
    
    logger.info(f"✅ Loaded {loaded_count} new WikiData categories, updated {len(categories) - loaded_count}")
    return loaded_count


def get_vocabulary_stats(session: Session) -> dict:
    """Get statistics about the WikiData vocabulary."""
    total = session.query(WikiDataCategory).count()
    general = session.query(WikiDataCategory).filter_by(level='general').count()
    specific = session.query(WikiDataCategory).filter_by(level='specific').count()
    
    return {
        "total_categories": total,
        "general_categories": general,
        "specific_categories": specific,
    }


if __name__ == "__main__":
    # Standalone script to load vocabulary
    import sys
    from ..database import DatabaseService
    
    logging.basicConfig(level=logging.INFO)
    
    db = DatabaseService()
    
    with db.get_session() as session:
        count = load_wikidata_vocabulary(session)
        stats = get_vocabulary_stats(session)
        
        print(f"\nWikiData Vocabulary Loaded:")
        print(f"  New categories: {count}")
        print(f"  Total categories: {stats['total_categories']}")
        print(f"  General: {stats['general_categories']}")
        print(f"  Specific: {stats['specific_categories']}")

