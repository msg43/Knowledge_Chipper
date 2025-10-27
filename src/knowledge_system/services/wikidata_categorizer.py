"""
Two-stage WikiData categorization service.

Stage 1: LLM generates free-form category descriptions
Stage 2: Map to WikiData categories via semantic similarity
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class WikiDataCategorizer:
    """
    Two-stage categorization: Free-form LLM → WikiData mapping.
    
    Benefits:
    - Clean prompts (no category lists)
    - Fast (no token masking)
    - Dynamic (update vocabulary anytime)
    - Scalable (works with thousands of categories)
    """
    
    def __init__(
        self,
        vocab_file: Path | None = None,
        embeddings_file: Path | None = None,
    ):
        """
        Initialize categorizer with WikiData vocabulary.
        
        Args:
            vocab_file: Path to wikidata_seed.json
            embeddings_file: Path to cached embeddings (auto-generated if missing)
        """
        if vocab_file is None:
            vocab_file = Path(__file__).parent.parent / "database" / "wikidata_seed.json"
        
        if embeddings_file is None:
            embeddings_file = Path(__file__).parent.parent / "database" / "wikidata_embeddings.pkl"
        
        self.vocab_file = vocab_file
        self.embeddings_file = embeddings_file
        
        # Load vocabulary
        with open(vocab_file) as f:
            data = json.load(f)
            self.categories = data["categories"]
        
        logger.info(f"Loaded {len(self.categories)} WikiData categories from {vocab_file}")
        
        # Load or compute embeddings
        self._load_or_compute_embeddings()
    
    def _load_or_compute_embeddings(self):
        """Load cached embeddings or compute them."""
        if self.embeddings_file.exists():
            # Load cached embeddings
            with open(self.embeddings_file, 'rb') as f:
                cache = pickle.load(f)
                self.embeddings = cache['embeddings']
                self.category_texts = cache['category_texts']
            
            logger.info(f"Loaded cached embeddings from {self.embeddings_file}")
        else:
            # Compute embeddings
            self._compute_embeddings()
    
    def _compute_embeddings(self):
        """Compute embeddings for all WikiData categories."""
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info("Computing embeddings for WikiData categories...")
            
            # Use fast, lightweight model
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Create text representations for each category
            self.category_texts = []
            for cat in self.categories:
                # Combine name, description, and aliases for better matching
                text_parts = [cat['category_name']]
                
                if cat.get('description'):
                    text_parts.append(cat['description'])
                
                if cat.get('aliases'):
                    text_parts.extend(cat['aliases'])
                
                category_text = " | ".join(text_parts)
                self.category_texts.append(category_text)
            
            # Encode all categories
            self.embeddings = model.encode(
                self.category_texts,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            
            # Cache embeddings
            self.embeddings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.embeddings_file, 'wb') as f:
                pickle.dump({
                    'embeddings': self.embeddings,
                    'category_texts': self.category_texts,
                    'vocab_version': self.vocab_file.stat().st_mtime,
                }, f)
            
            logger.info(f"✅ Computed and cached embeddings to {self.embeddings_file}")
            
        except ImportError:
            logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
            raise
    
    def categorize_source(
        self,
        source_content: str,
        llm_generate_func,
        auto_approve_threshold: float = 0.85,
    ) -> list[dict]:
        """
        Two-stage source categorization.
        
        Args:
            source_content: Content to categorize (title + description + transcript)
            llm_generate_func: Function to call LLM (must support structured output)
            auto_approve_threshold: Similarity threshold for auto-approval
        
        Returns:
            List of matched categories with approval status
        """
        # === STAGE 1: Free-form LLM categorization ===
        prompt = f"""
Analyze this content and identify the 3 most important GENERAL topics it covers.

CONTENT:
{source_content[:2000]}  

Provide 3 broad, high-level topics (like "Economics", "Politics", "Technology").
Not specific subtopics, but general domains.

OUTPUT (JSON):
{{
  "categories": [
    {{"name": "General topic 1", "rationale": "Why this fits"}},
    {{"name": "General topic 2", "rationale": "Why this fits"}},
    {{"name": "General topic 3", "rationale": "Why this fits"}}
  ]
}}
"""
        
        response = llm_generate_func(prompt)
        
        if isinstance(response, str):
            response = json.loads(response)
        
        freeform_categories = [cat['name'] for cat in response['categories']]
        logger.info(f"Stage 1 - LLM generated: {freeform_categories}")
        
        # === STAGE 2: Map to WikiData via embeddings ===
        results = []
        
        for rank, freeform_cat in enumerate(freeform_categories, start=1):
            matches = self.find_closest_categories(freeform_cat, top_k=3)
            best_match = matches[0]
            
            result = {
                'wikidata_id': best_match['wikidata_id'],
                'category_name': best_match['category_name'],
                'rank': rank,
                'relevance_score': best_match['similarity'],
                'confidence': best_match['similarity'],
                'freeform_input': freeform_cat,
                'auto_approved': best_match['similarity'] >= auto_approve_threshold,
                'alternatives': matches[1:],  # Other possible matches
            }
            
            results.append(result)
            
            logger.info(
                f"Stage 2 - Mapped '{freeform_cat}' → '{best_match['category_name']}' "
                f"({best_match['similarity']:.2f})"
            )
        
        return results
    
    def categorize_claim(
        self,
        claim_text: str,
        source_categories: list[str] | None,
        llm_generate_func,
        auto_approve_threshold: float = 0.85,
    ) -> dict:
        """
        Two-stage claim categorization.
        
        Args:
            claim_text: The claim to categorize
            source_categories: Categories of the source (for context)
            llm_generate_func: Function to call LLM
            auto_approve_threshold: Similarity threshold for auto-approval
        
        Returns:
            Single matched category with approval status
        """
        # === STAGE 1: Free-form LLM categorization ===
        context = ""
        if source_categories:
            context = f"\nNote: This claim is from a source about: {', '.join(source_categories)}\n"
        
        prompt = f"""
Analyze this claim and identify the single most SPECIFIC topic it's about.
{context}
CLAIM:
{claim_text}

Provide ONE specific topic (like "Monetary policy", not just "Economics").
Be as specific as possible.

OUTPUT (JSON):
{{
  "category": {{"name": "Specific topic", "rationale": "Why this fits"}}
}}
"""
        
        response = llm_generate_func(prompt)
        
        if isinstance(response, str):
            response = json.loads(response)
        
        freeform_category = response['category']['name']
        logger.info(f"Stage 1 - LLM generated: {freeform_category}")
        
        # === STAGE 2: Map to WikiData via embeddings ===
        matches = self.find_closest_categories(freeform_category, top_k=3)
        best_match = matches[0]
        
        result = {
            'wikidata_id': best_match['wikidata_id'],
            'category_name': best_match['category_name'],
            'relevance_score': best_match['similarity'],
            'confidence': best_match['similarity'],
            'freeform_input': freeform_category,
            'auto_approved': best_match['similarity'] >= auto_approve_threshold,
            'alternatives': matches[1:],
        }
        
        logger.info(
            f"Stage 2 - Mapped '{freeform_category}' → '{best_match['category_name']}' "
            f"({best_match['similarity']:.2f})"
        )
        
        return result
    
    def find_closest_categories(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Find closest WikiData categories using semantic similarity.
        
        Args:
            query: Free-form category description
            top_k: Number of matches to return
        
        Returns:
            List of matches with similarity scores
        """
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Encode query
            model = SentenceTransformer('all-MiniLM-L6-v2')
            query_embedding = model.encode([query])
            
            # Compute similarities
            similarities = cosine_similarity(query_embedding, self.embeddings)[0]
            
            # Get top-K matches
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            matches = []
            for idx in top_indices:
                similarity = float(similarities[idx])
                category = self.categories[idx]
                
                matches.append({
                    'wikidata_id': category['wikidata_id'],
                    'category_name': category['category_name'],
                    'description': category.get('description', ''),
                    'similarity': similarity,
                    'confidence': 'high' if similarity > 0.8 else 'medium' if similarity > 0.6 else 'low',
                })
            
            return matches
            
        except ImportError:
            logger.error("sentence-transformers or sklearn not installed")
            raise
    
    def add_category_to_vocabulary(
        self,
        wikidata_id: str,
        category_name: str,
        description: str = "",
        level: str = "specific",
        parent_id: str | None = None,
        aliases: list[str] | None = None,
    ) -> None:
        """
        Add a new category to the vocabulary and recompute embeddings.
        
        Args:
            wikidata_id: WikiData Q-number
            category_name: Human-readable name
            description: Category description
            level: 'general' or 'specific'
            parent_id: Parent WikiData ID (for hierarchy)
            aliases: Alternative names
        """
        # Load current vocabulary
        with open(self.vocab_file) as f:
            data = json.load(f)
        
        # Add new category
        new_category = {
            'wikidata_id': wikidata_id,
            'category_name': category_name,
            'description': description,
            'level': level,
            'parent_id': parent_id,
            'aliases': aliases or [],
        }
        
        data['categories'].append(new_category)
        
        # Save updated vocabulary
        with open(self.vocab_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Added category to vocabulary: {category_name} ({wikidata_id})")
        
        # Recompute embeddings
        self.categories = data['categories']
        self._compute_embeddings()
        
        logger.info("✅ Vocabulary updated and embeddings recomputed")


def create_categorizer(
    vocab_file: Path | None = None,
    embeddings_file: Path | None = None,
) -> WikiDataCategorizer:
    """Create a WikiDataCategorizer instance."""
    return WikiDataCategorizer(vocab_file, embeddings_file)


if __name__ == "__main__":
    # Test the categorizer
    categorizer = WikiDataCategorizer()
    
    # Test free-form matching
    test_queries = [
        "Central banking",
        "Federal Reserve policy",
        "Economics and finance",
        "Monetary policies",
        "Fed stuff",
        "Interest rates",
    ]
    
    print("\nTesting WikiData matching:")
    print("=" * 60)
    
    for query in test_queries:
        matches = categorizer.find_closest_categories(query, top_k=3)
        print(f"\nQuery: '{query}'")
        for i, match in enumerate(matches, 1):
            print(f"  {i}. {match['category_name']} ({match['wikidata_id']}) - {match['similarity']:.3f} [{match['confidence']}]")

