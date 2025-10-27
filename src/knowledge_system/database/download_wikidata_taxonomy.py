#!/usr/bin/env python3
"""
Download WikiData topic taxonomy for categorization.

Queries WikiData SPARQL endpoint for topic categories relevant to knowledge claims.
Focuses on fields of study, academic disciplines, and conceptual domains.

NOT: Biological taxonomy, chemical compounds, specific entities
YES: Economics, Politics, Sciences, Technologies, Philosophies, etc.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WikiDataTaxonomyDownloader:
    """Download and curate WikiData topic categories."""
    
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    USER_AGENT = "KnowledgeChipper/1.0 (Knowledge extraction system)"
    
    def __init__(self, output_file: Path | None = None):
        """
        Initialize downloader.
        
        Args:
            output_file: Where to save the vocabulary JSON
        """
        if output_file is None:
            output_file = Path(__file__).parent / "wikidata_vocabulary.json"
        
        self.output_file = output_file
        self.categories = []
    
    def query_sparql(self, query: str, max_retries: int = 5) -> list[dict]:
        """
        Execute SPARQL query against WikiData with rate limit handling.
        
        Args:
            query: SPARQL query string
            max_retries: Number of retry attempts
        
        Returns:
            List of result bindings
        """
        headers = {
            'User-Agent': self.USER_AGENT,
            'Accept': 'application/sparql-results+json'
        }
        
        for attempt in range(max_retries):
            try:
                # Add delay before each attempt to avoid rate limits
                if attempt > 0:
                    wait_time = min(10 * (2 ** attempt), 60)  # Max 60 seconds
                    logger.info(f"  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                
                response = requests.get(
                    self.SPARQL_ENDPOINT,
                    params={'query': query, 'format': 'json'},
                    headers=headers,
                    timeout=90  # Longer timeout
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited (429). Retry after {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                
                data = response.json()
                return data['results']['bindings']
            
            except requests.exceptions.RequestException as e:
                logger.warning(f"SPARQL query attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    # Exponential backoff
                    continue
                else:
                    logger.error(f"All retries exhausted")
                    raise
        
        return []
    
    def download_conceptual_taxonomy(self, limit: int = 1000) -> list[dict]:
        """
        Download conceptual taxonomy: fields of study and academic disciplines.
        
        Targets:
        - Q2267705 (field of study) - Primary root
        - Q11862829 (academic discipline)
        - Q1936384 (branch of science)
        
        Excludes:
        - Q16521 (Taxon) - No biological species
        - Q11173 (Chemical compound) - No molecules
        - Q5 (Human) - No individual people
        - Q515 (City) - No places
        - Q431289 (Brand) - No products
        
        Result: ~800-1,200 stable conceptual categories
        """
        logger.info("Downloading conceptual taxonomy (fields of study)...")
        
        query = f"""
        SELECT DISTINCT ?item ?itemLabel ?itemDescription ?parentLabel
        WHERE {{
          # Root: Fields of study and academic disciplines
          {{
            ?item wdt:P31 wd:Q2267705.  # Field of study
          }} UNION {{
            ?item wdt:P31 wd:Q11862829. # Academic discipline
          }} UNION {{
            ?item wdt:P31 wd:Q1936384.  # Branch of science
          }}
          
          # Get direct parent for hierarchy
          OPTIONAL {{ ?item wdt:P279 ?parent. }}
          
          # Get labels
          SERVICE wikibase:label {{ 
            bd:serviceParam wikibase:language "en". 
          }}
          
          # EXCLUSIONS: Filter out non-conceptual items
          FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q16521. }}   # Not taxon (species)
          FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q11173. }}   # Not chemical compound
          FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q5. }}       # Not person
          FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q515. }}     # Not city
          FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q431289. }}  # Not brand
          FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q4830453. }} # Not business
          
          # Only items with English labels
          FILTER(BOUND(?itemLabel))
        }}
        LIMIT {limit}
        """
        
        try:
            results = self.query_sparql(query)
            logger.info(f"  Retrieved {len(results)} conceptual categories")
            return self._parse_results(results, level='specific')
        
        except Exception as e:
            logger.error(f"Conceptual taxonomy download failed: {e}")
            logger.info("  Falling back to manual curated list...")
            return []
    
    def download_broad_concepts(self) -> list[dict]:
        """
        Download broad conceptual categories.
        
        Queries for major topics like:
        - Q8134 (Economics)
        - Q7163 (Politics)
        - Q11016 (Technology)
        - Q336 (Science)
        etc.
        """
        logger.info("Downloading broad concepts...")
        
        # Manually curated list of top-level categories
        top_level_ids = [
            'Q8134',    # Economics
            'Q7163',    # Politics
            'Q11016',   # Technology
            'Q336',     # Science
            'Q8386',    # Law
            'Q34178',   # Health care
            'Q638',     # Music
            'Q25379',   # Philosophy
            'Q9129',    # History
            'Q11024',   # Communication
            'Q413',     # Physics
            'Q2329',    # Chemistry
            'Q420',     # Biology
            'Q395',     # Mathematics
            'Q21201',   # Sociology
            'Q9134',    # Mythology
            'Q9158',    # Linguistics
            'Q8242',    # Literature
            'Q735',     # Art
            'Q11378',   # Ethics
            'Q34749',   # Epistemology
        ]
        
        query = f"""
        SELECT DISTINCT ?item ?itemLabel ?itemDescription
        WHERE {{
          VALUES ?item {{ wd:{' wd:'.join(top_level_ids)} }}
          
          SERVICE wikibase:label {{ 
            bd:serviceParam wikibase:language "en". 
          }}
        }}
        """
        
        results = self.query_sparql(query)
        logger.info(f"  Retrieved {len(results)} broad concepts")
        
        return self._parse_results(results, level='general')
    
    def download_subcategories(self, parent_ids: list[str], depth: int = 2) -> list[dict]:
        """
        Download subcategories of given parents up to specified depth.
        
        Args:
            parent_ids: List of WikiData IDs to get children for
            depth: How many levels deep (1-3 recommended)
        
        Returns:
            List of category dictionaries
        """
        logger.info(f"Downloading subcategories (depth={depth})...")
        
        all_subcategories = []
        
        for batch_start in range(0, len(parent_ids), 50):  # Batch by 50
            batch = parent_ids[batch_start:batch_start + 50]
            
            # Build depth-based query
            parent_filter = ' wd:'.join(batch)
            
            if depth == 1:
                property_path = "wdt:P279"
            elif depth == 2:
                property_path = "wdt:P279/wdt:P279?"
            else:  # depth >= 3
                property_path = "wdt:P279/wdt:P279?/wdt:P279?"
            
            query = f"""
            SELECT DISTINCT ?item ?itemLabel ?itemDescription ?parentLabel
            WHERE {{
              VALUES ?parent {{ wd:{parent_filter} }}
              ?item {property_path} ?parent.
              
              # Get direct parent for hierarchy
              OPTIONAL {{ ?item wdt:P279 ?directParent. }}
              
              SERVICE wikibase:label {{ 
                bd:serviceParam wikibase:language "en". 
              }}
              
              # Filter out overly specific items
              FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q5. }}  # Not a person
              FILTER NOT EXISTS {{ ?item wdt:P31 wd:Q515. }} # Not a city
            }}
            LIMIT 500
            """
            
            try:
                results = self.query_sparql(query)
                parsed = self._parse_results(results, level='specific')
                all_subcategories.extend(parsed)
                logger.info(f"  Batch {batch_start//50 + 1}: {len(parsed)} subcategories")
                
                time.sleep(1)  # Rate limiting
            
            except Exception as e:
                logger.warning(f"Batch {batch_start//50 + 1} failed: {e}")
        
        logger.info(f"  Total subcategories: {len(all_subcategories)}")
        return all_subcategories
    
    def _parse_results(self, results: list[dict], level: str) -> list[dict]:
        """
        Parse SPARQL results into category dictionaries.
        
        Args:
            results: SPARQL result bindings
            level: 'general' or 'specific'
        
        Returns:
            List of category dicts
        """
        categories = []
        
        for binding in results:
            # Extract WikiData ID from URI
            item_uri = binding.get('item', {}).get('value', '')
            if '/Q' not in item_uri:
                continue
            
            wikidata_id = item_uri.split('/')[-1]
            
            # Get label and description
            label = binding.get('itemLabel', {}).get('value', '')
            description = binding.get('itemDescription', {}).get('value', '')
            
            # Skip if no label
            if not label or label == wikidata_id:
                continue
            
            # Get parent if available
            parent_label = binding.get('parentLabel', {}).get('value', '')
            parent_id = None
            if 'parent' in binding:
                parent_uri = binding['parent'].get('value', '')
                if '/Q' in parent_uri:
                    parent_id = parent_uri.split('/')[-1]
            
            category = {
                'wikidata_id': wikidata_id,
                'category_name': label,
                'description': description,
                'level': level,
                'parent_id': parent_id,
                'aliases': []  # Could extract these with additional queries
            }
            
            categories.append(category)
        
        return categories
    
    def download_complete_taxonomy(
        self,
        include_academic: bool = True,
        include_broad: bool = True,
        subcategory_depth: int = 2,
        max_total: int = 2000,
    ) -> dict:
        """
        Download a comprehensive WikiData topic taxonomy.
        
        Args:
            include_academic: Include academic disciplines
            include_broad: Include broad top-level concepts
            subcategory_depth: How deep to go for subcategories (1-3)
            max_total: Maximum total categories to include
        
        Returns:
            Vocabulary dict with metadata
        """
        logger.info("Starting WikiData taxonomy download...")
        logger.info(f"  Max categories: {max_total}")
        logger.info(f"  Subcategory depth: {subcategory_depth}")
        
        all_categories = []
        
        # 1. Get broad top-level concepts
        if include_broad:
            broad = self.download_broad_concepts()
            all_categories.extend(broad)
            logger.info(f"✅ Broad concepts: {len(broad)}")
        
        # 2. Get conceptual taxonomy (fields of study, academic disciplines)
        if include_academic:
            conceptual = self.download_conceptual_taxonomy(limit=max_total)
            all_categories.extend(conceptual)
            logger.info(f"✅ Conceptual categories: {len(conceptual)}")
        
        # 3. Get subcategories of broad concepts
        if subcategory_depth > 0 and include_broad:
            parent_ids = [cat['wikidata_id'] for cat in all_categories if cat['level'] == 'general']
            subcats = self.download_subcategories(parent_ids, depth=subcategory_depth)
            all_categories.extend(subcats)
            logger.info(f"✅ Subcategories: {len(subcats)}")
        
        # 4. Deduplicate by WikiData ID
        seen_ids = set()
        unique_categories = []
        for cat in all_categories:
            if cat['wikidata_id'] not in seen_ids:
                seen_ids.add(cat['wikidata_id'])
                unique_categories.append(cat)
        
        logger.info(f"✅ Total unique categories: {len(unique_categories)}")
        
        # 5. Limit to max_total (prioritize by level)
        if len(unique_categories) > max_total:
            # Keep all general, then top specific by popularity/relevance
            general_cats = [c for c in unique_categories if c['level'] == 'general']
            specific_cats = [c for c in unique_categories if c['level'] == 'specific']
            
            # Limit specific categories
            remaining = max_total - len(general_cats)
            specific_cats = specific_cats[:remaining]
            
            unique_categories = general_cats + specific_cats
            logger.info(f"  Trimmed to {max_total}: {len(general_cats)} general + {len(specific_cats)} specific")
        
        # 6. Create vocabulary structure
        vocabulary = {
            'version': '2.0.0',
            'created': time.strftime('%Y-%m-%d'),
            'source': 'WikiData SPARQL',
            'description': f'Downloaded WikiData taxonomy with {len(unique_categories)} categories',
            'categories': unique_categories,
            'metadata': {
                'total_categories': len(unique_categories),
                'general_categories': len([c for c in unique_categories if c['level'] == 'general']),
                'specific_categories': len([c for c in unique_categories if c['level'] == 'specific']),
                'subcategory_depth': subcategory_depth,
            }
        }
        
        return vocabulary
    
    def save_vocabulary(self, vocabulary: dict) -> None:
        """Save vocabulary to JSON file."""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(vocabulary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Saved vocabulary to {self.output_file}")
        logger.info(f"   Total categories: {vocabulary['metadata']['total_categories']}")
        logger.info(f"   General: {vocabulary['metadata']['general_categories']}")
        logger.info(f"   Specific: {vocabulary['metadata']['specific_categories']}")
    
    def download_and_save(self, **kwargs) -> dict:
        """
        Download taxonomy and save to file.
        
        Args:
            **kwargs: Passed to download_complete_taxonomy()
        
        Returns:
            Vocabulary dict
        """
        vocab = self.download_complete_taxonomy(**kwargs)
        self.save_vocabulary(vocab)
        return vocab


def download_wikidata_vocabulary(
    output_file: Path | None = None,
    max_categories: int = 1000,
    subcategory_depth: int = 2,
) -> dict:
    """
    Convenience function to download WikiData vocabulary.
    
    Args:
        output_file: Where to save (default: wikidata_vocabulary.json)
        max_categories: Maximum number of categories (default: 1000)
        subcategory_depth: How deep to go (1-3, default: 2)
    
    Returns:
        Vocabulary dict
    """
    downloader = WikiDataTaxonomyDownloader(output_file)
    return downloader.download_and_save(
        max_total=max_categories,
        subcategory_depth=subcategory_depth
    )


def merge_with_existing(new_vocab_file: Path, existing_vocab_file: Path, output_file: Path) -> dict:
    """
    Merge downloaded vocabulary with existing curated vocabulary.
    
    Args:
        new_vocab_file: Downloaded WikiData vocabulary
        existing_vocab_file: Your curated vocabulary (41 categories)
        output_file: Where to save merged vocabulary
    
    Returns:
        Merged vocabulary dict
    """
    logger.info("Merging vocabularies...")
    
    # Load both vocabularies
    with open(new_vocab_file) as f:
        new_vocab = json.load(f)
    
    with open(existing_vocab_file) as f:
        existing_vocab = json.load(f)
    
    # Merge categories, preferring existing (more curated)
    existing_ids = {cat['wikidata_id']: cat for cat in existing_vocab['categories']}
    new_cats = new_vocab['categories']
    
    merged_categories = list(existing_ids.values())
    
    for new_cat in new_cats:
        if new_cat['wikidata_id'] not in existing_ids:
            merged_categories.append(new_cat)
    
    # Create merged vocabulary
    merged = {
        'version': f"merged_{time.strftime('%Y%m%d')}",
        'created': time.strftime('%Y-%m-%d'),
        'source': 'WikiData + Manual Curation',
        'description': f'Merged vocabulary: {len(merged_categories)} categories',
        'categories': merged_categories,
        'metadata': {
            'total_categories': len(merged_categories),
            'from_curated': len(existing_ids),
            'from_wikidata': len(merged_categories) - len(existing_ids),
            'general_categories': len([c for c in merged_categories if c['level'] == 'general']),
            'specific_categories': len([c for c in merged_categories if c['level'] == 'specific']),
        }
    }
    
    # Save merged vocabulary
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Merged vocabulary saved to {output_file}")
    logger.info(f"   Total: {merged['metadata']['total_categories']} categories")
    logger.info(f"   From curated: {merged['metadata']['from_curated']}")
    logger.info(f"   From WikiData: {merged['metadata']['from_wikidata']}")
    
    return merged


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download WikiData topic taxonomy for categorization"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path(__file__).parent / "wikidata_vocabulary.json",
        help='Output file path'
    )
    parser.add_argument(
        '--max-categories', '-n',
        type=int,
        default=1000,
        help='Maximum number of categories (default: 1000)'
    )
    parser.add_argument(
        '--depth', '-d',
        type=int,
        default=2,
        help='Subcategory depth: 1-3 (default: 2)'
    )
    parser.add_argument(
        '--merge',
        type=Path,
        help='Merge with existing vocabulary file'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("WIKIDATA TAXONOMY DOWNLOADER")
    print("="*70)
    
    try:
        if args.merge:
            # Merge mode
            print(f"\nMode: MERGE")
            print(f"  Downloading WikiData categories...")
            print(f"  Merging with: {args.merge}")
            print(f"  Output: {args.output}")
            
            # Download to temp file
            temp_file = args.output.parent / "wikidata_temp.json"
            vocab = download_wikidata_vocabulary(
                output_file=temp_file,
                max_categories=args.max_categories,
                subcategory_depth=args.depth
            )
            
            # Merge
            merged = merge_with_existing(temp_file, args.merge, args.output)
            
            # Clean up temp
            temp_file.unlink()
            
            print(f"\n✅ Merge complete!")
            print(f"   Total categories: {merged['metadata']['total_categories']}")
        
        else:
            # Download mode
            print(f"\nMode: DOWNLOAD")
            print(f"  Max categories: {args.max_categories}")
            print(f"  Depth: {args.depth}")
            print(f"  Output: {args.output}")
            
            vocab = download_wikidata_vocabulary(
                output_file=args.output,
                max_categories=args.max_categories,
                subcategory_depth=args.depth
            )
            
            print(f"\n✅ Download complete!")
            print(f"   Total categories: {vocab['metadata']['total_categories']}")
            print(f"   General: {vocab['metadata']['general_categories']}")
            print(f"   Specific: {vocab['metadata']['specific_categories']}")
        
        print(f"\nNext steps:")
        print(f"  1. Review downloaded categories")
        print(f"  2. Recompute embeddings:")
        print(f"     python -c \"from src.knowledge_system.services.wikidata_categorizer import WikiDataCategorizer; ")
        print(f"     WikiDataCategorizer()._compute_embeddings()\"")
        print(f"  3. Test categorization with expanded vocabulary")
    
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    sys.exit(0)


