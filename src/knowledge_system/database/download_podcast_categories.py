#!/usr/bin/env python3
"""
Download podcast-specific categories from WikiData.

Fetches:
1. P136 (genre) - What genres podcasts are tagged with
2. P921 (main subject) - What topics podcasts discuss

These represent categories that real content creators actually use,
providing practical vocabulary grounded in real-world usage.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urlencode

import requests
from loguru import logger


class PodcastCategoryDownloader:
    """Download podcast genres and topics from WikiData."""

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

    # Top 2000 podcast genres (P136)
    GENRES_QUERY = """
    SELECT ?genre ?genreLabel (COUNT(*) AS ?usageCount)
    WHERE {
      ?podcast wdt:P31/wdt:P279* wd:Q24634210 .
      ?podcast wdt:P136 ?genre .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    GROUP BY ?genre ?genreLabel
    ORDER BY DESC(?usageCount)
    LIMIT 2000
    """

    # Top 2000 podcast topics (P921 - main subject)
    TOPICS_QUERY = """
    SELECT ?topic ?topicLabel (COUNT(*) AS ?usageCount)
    WHERE {
      ?podcast wdt:P31/wdt:P279* wd:Q24634210 .
      ?podcast wdt:P921 ?topic .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    GROUP BY ?topic ?topicLabel
    ORDER BY DESC(?usageCount)
    LIMIT 2000
    """

    def __init__(self, max_retries: int = 5):
        """Initialize downloader."""
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "KnowledgeChipper/1.0 (podcast category research)"}
        )

    def query_sparql(self, query: str, query_type: str) -> list[dict]:
        """Execute SPARQL query with retry logic."""
        params = {"format": "json", "query": query}

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"  Attempt {attempt}/{self.max_retries} for {query_type}..."
                )

                response = self.session.get(
                    self.SPARQL_ENDPOINT, params=params, timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_results(data)
                    logger.info(f"  Retrieved {len(results)} {query_type}")
                    return results

                elif response.status_code == 429:
                    wait_time = 5 * attempt
                    logger.warning(f"  Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)

                else:
                    logger.error(
                        f"  HTTP {response.status_code}: {response.text[:200]}"
                    )
                    time.sleep(2 * attempt)

            except requests.exceptions.Timeout:
                logger.warning(f"  Timeout on attempt {attempt}")
                time.sleep(3 * attempt)

            except Exception as e:
                logger.error(f"  Error: {e}")
                time.sleep(2 * attempt)

        logger.error(f"Failed to fetch {query_type} after {self.max_retries} attempts")
        return []

    def _parse_results(self, data: dict) -> list[dict]:
        """Parse SPARQL JSON results."""
        results = []

        for binding in data.get("results", {}).get("bindings", []):
            # Extract Q-ID from URI
            uri = binding.get("genre", binding.get("topic", {})).get("value", "")
            qid = uri.split("/")[-1] if "/" in uri else ""

            # Get label
            label = binding.get("genreLabel", binding.get("topicLabel", {})).get(
                "value", ""
            )

            # Get usage count
            usage = int(binding.get("usageCount", {}).get("value", 0))

            if qid and label:
                results.append({"qid": qid, "label": label, "usage_count": usage})

        return results

    def download_all(self, output_file: Path) -> dict:
        """Download both genres and topics."""
        logger.info("Starting podcast category download from WikiData...")

        # Download genres (P136)
        logger.info("\nDownloading podcast genres (P136)...")
        genres = self.query_sparql(self.GENRES_QUERY, "genres")

        # Small delay between queries
        time.sleep(2)

        # Download topics (P921)
        logger.info("\nDownloading podcast topics (P921)...")
        topics = self.query_sparql(self.TOPICS_QUERY, "topics")

        # Combine and deduplicate
        combined = self._combine_categories(genres, topics)

        # Convert to our vocabulary format
        vocabulary = self._convert_to_vocabulary(combined)

        # Save
        with open(output_file, "w") as f:
            json.dump(vocabulary, f, indent=2)

        logger.info(
            f"\n✅ Saved {len(vocabulary['categories'])} podcast categories to {output_file}"
        )

        return {
            "genres": len(genres),
            "topics": len(topics),
            "combined": len(combined),
            "final": len(vocabulary["categories"]),
        }

    def _combine_categories(self, genres: list[dict], topics: list[dict]) -> list[dict]:
        """Combine genres and topics, deduplicating by QID."""
        seen_qids: set[str] = set()
        combined = []

        # Add genres first (they're more specific to podcasting)
        for genre in genres:
            if genre["qid"] not in seen_qids:
                seen_qids.add(genre["qid"])
                combined.append(
                    {**genre, "source": "P136_genre", "rank": len(combined) + 1}
                )

        # Add topics that aren't already in genres
        for topic in topics:
            if topic["qid"] not in seen_qids:
                seen_qids.add(topic["qid"])
                combined.append(
                    {**topic, "source": "P921_topic", "rank": len(combined) + 1}
                )

        return combined

    def _convert_to_vocabulary(self, categories: list[dict]) -> dict:
        """Convert to our vocabulary format."""
        vocab_categories = []

        for cat in categories:
            vocab_categories.append(
                {
                    "wikidata_id": cat["qid"],
                    "category_name": cat["label"],
                    "description": f"Podcast {cat['source'].split('_')[1]} (used by {cat['usage_count']} podcasts)",
                    "aliases": [],
                    "level": "specific",  # All podcast categories are specific
                    "parent_id": None,
                    "usage_count": cat["usage_count"],
                    "source": cat["source"],
                }
            )

        return {
            "metadata": {
                "source": "wikidata_podcast_categories",
                "download_date": time.strftime("%Y-%m-%d"),
                "total_categories": len(vocab_categories),
                "from_genres": len(
                    [c for c in categories if c["source"] == "P136_genre"]
                ),
                "from_topics": len(
                    [c for c in categories if c["source"] == "P921_topic"]
                ),
            },
            "categories": vocab_categories,
        }


def main():
    """Download podcast categories from WikiData."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download podcast categories from WikiData"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/knowledge_system/database/wikidata_podcast.json"),
        help="Output file path",
    )
    parser.add_argument(
        "--merge", type=Path, help="Merge with existing vocabulary file"
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("PODCAST CATEGORY DOWNLOADER")
    print("=" * 70 + "\n")

    # Download
    downloader = PodcastCategoryDownloader()
    stats = downloader.download_all(args.output)

    print(f"\n✅ Download complete!")
    print(f"   Genres (P136): {stats['genres']}")
    print(f"   Topics (P921): {stats['topics']}")
    print(f"   Combined unique: {stats['combined']}")
    print(f"   Final categories: {stats['final']}")

    # Merge if requested
    if args.merge:
        print(f"\nMerging with {args.merge}...")

        with open(args.output) as f:
            podcast_data = json.load(f)

        with open(args.merge) as f:
            existing_data = json.load(f)

        # Combine categories, deduplicating by wikidata_id
        seen_ids = set()
        merged_categories = []

        # Add existing first (they're our curated/conceptual base)
        for cat in existing_data["categories"]:
            wid = cat["wikidata_id"]
            if wid not in seen_ids:
                seen_ids.add(wid)
                merged_categories.append(cat)

        # Add podcast categories
        added = 0
        for cat in podcast_data["categories"]:
            wid = cat["wikidata_id"]
            if wid not in seen_ids:
                seen_ids.add(wid)
                merged_categories.append(cat)
                added += 1

        # Save merged
        merged_output = args.output.parent / "wikidata_with_podcast.json"
        merged_data = {
            "metadata": {
                "source": "conceptual_taxonomy + podcast_categories",
                "download_date": time.strftime("%Y-%m-%d"),
                "total_categories": len(merged_categories),
                "from_conceptual": len(existing_data["categories"]),
                "from_podcast": added,
            },
            "categories": merged_categories,
        }

        with open(merged_output, "w") as f:
            json.dump(merged_data, f, indent=2)

        print(f"✅ Merged vocabulary saved to {merged_output}")
        print(f"   Total: {len(merged_categories)} categories")
        print(f"   From conceptual: {len(existing_data['categories'])}")
        print(f"   From podcast: {added}")
        print(f"   Overlap: {stats['final'] - added}")


if __name__ == "__main__":
    main()
