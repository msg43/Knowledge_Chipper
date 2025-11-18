"""
GetReceipts.org Data Uploader for Knowledge_Chipper

This module handles uploading Knowledge_Chipper HCE data to GetReceipts.org
Supabase database with automatic device authentication (Happy-style).

Usage:
    from getreceipts_uploader import GetReceiptsUploader

    uploader = GetReceiptsUploader()  # Auto-authenticates with device credentials
    results = uploader.upload_session_data(session_data)

Author: GetReceipts.org Team
License: MIT
"""

import json
import sys
from pathlib import Path
from typing import Any

from supabase import Client, create_client

# Add parent directory to path to import device_auth
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from knowledge_system.services.device_auth import get_device_auth


class GetReceiptsUploader:
    """
    Handles uploading Knowledge_Chipper data to GetReceipts.org

    This class:
    1. Auto-authenticates with device credentials (silent, Happy-style)
    2. Transforms HCE data format to GetReceipts schema
    3. Uploads data to Supabase with device attribution
    4. Handles all data types (episodes, claims, evidence, knowledge artifacts)
    """

    def __init__(
        self,
        supabase_url: str = "https://sdkxuiqcwlmbpjvjdpkj.supabase.co",
        supabase_anon_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts",
    ):
        """
        Initialize the uploader with automatic device authentication

        Args:
            supabase_url: Supabase project URL
            supabase_anon_key: Supabase anonymous key
        """
        self.device_auth = get_device_auth()
        self.credentials = self.device_auth.get_credentials()

        # Create Supabase client with device credentials in headers
        self.supabase: Client = create_client(
            supabase_url,
            supabase_anon_key,
            options={
                "headers": {
                    "X-Device-ID": self.credentials["device_id"],
                    "X-Device-Key": self.credentials["device_key"],
                }
            },
        )

        print(f"🔐 Using device ID: {self.credentials['device_id'][:8]}...")

    def is_enabled(self) -> bool:
        """Check if auto-upload is enabled"""
        return self.device_auth.is_enabled()

    def upload_session_data(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """
        Upload complete Knowledge_Chipper session data to GetReceipts

        This method processes and uploads all data types in the correct order:
        1. Episodes (must be first for foreign key references)
        2. Claims
        3. Evidence
        4. Knowledge artifacts (people, jargon, mental models)
        5. Relationships

        Args:
            session_data: Dictionary containing all HCE data tables

        Returns:
            Dictionary with upload results for each table (empty if disabled)
        """
        # Check if auto-upload is enabled
        if not self.is_enabled():
            print("⏭️  Auto-upload disabled - skipping GetReceipts upload")
            return {}

        print("🚀 Starting upload to GetReceipts.org...")
        results = {}

        try:
            # Upload in dependency order

            # 1. Episodes first (needed for foreign keys)
            if "episodes" in session_data and session_data["episodes"]:
                print(f"📺 Found {len(session_data['episodes'])} episodes to upload")
                results["episodes"] = self._upload_episodes(session_data["episodes"])

            # 2. Claims second (needed for evidence and artifacts)
            if "claims" in session_data and session_data["claims"]:
                print(f"📝 Found {len(session_data['claims'])} claims to upload")
                results["claims"] = self._upload_claims(session_data["claims"])

            # 3. Evidence (references claims and episodes)
            if "evidence_spans" in session_data and session_data["evidence_spans"]:
                print(
                    f"🎯 Found {len(session_data['evidence_spans'])} evidence spans to upload"
                )
                results["evidence"] = self._upload_evidence(
                    session_data["evidence_spans"]
                )

            # 4. Knowledge artifacts (reference claims and episodes)
            if "people" in session_data and session_data["people"]:
                print(f"👥 Found {len(session_data['people'])} people to upload")
                results["people"] = self._upload_people(session_data["people"])

            if "jargon" in session_data and session_data["jargon"]:
                print(f"📚 Found {len(session_data['jargon'])} jargon terms to upload")
                results["jargon"] = self._upload_jargon(session_data["jargon"])

            if "concepts" in session_data and session_data["concepts"]:
                print(
                    f"🧠 Found {len(session_data['concepts'])} mental models to upload"
                )
                results["mental_models"] = self._upload_mental_models(
                    session_data["concepts"]
                )

            # 5. Relationships last (reference claims)
            if "relations" in session_data and session_data["relations"]:
                print(
                    f"🔗 Found {len(session_data['relations'])} relationships to upload"
                )
                results["claim_relationships"] = self._upload_relationships(
                    session_data["relations"]
                )

            print("✅ Upload completed successfully!")
            self._print_upload_summary(results)
            return results

        except Exception as e:
            print(f"❌ Upload failed: {str(e)}")
            raise

    def _upload_episodes(self, episodes: list[dict]) -> list[dict]:
        """Upload episodes data to GetReceipts"""
        print("📺 Uploading episodes...")

        supabase_episodes = []
        for ep in episodes:
            supabase_ep = {
                "episode_id": ep["episode_id"],
                "title": ep.get("title", f"Episode {ep['episode_id']}"),
                "source_type": self._detect_source_type(ep.get("url", "")),
                "url": ep.get("url"),
                "recorded_at": ep.get("recorded_at"),
                "duration": ep.get("duration_seconds"),
                # created_by will be set automatically by Supabase RLS
            }
            # Remove None values
            supabase_ep = {k: v for k, v in supabase_ep.items() if v is not None}
            supabase_episodes.append(supabase_ep)

        result = (
            self.supabase.table("episodes")
            .upsert(supabase_episodes, on_conflict="episode_id")
            .execute()
        )

        print(f"✅ Episodes uploaded: {len(result.data)}")
        return result.data

    def _upload_claims(self, claims: list[dict]) -> list[dict]:
        """Upload claims data to GetReceipts"""
        print("📝 Uploading claims...")

        supabase_claims = []
        for claim in claims:
            # Parse scores JSON if it exists
            scores = self._parse_json_field(claim.get("scores_json", "{}")) or {}

            # Parse structured categories
            categories = (
                self._parse_json_field(claim.get("structured_categories_json", "[]"))
                or []
            )

            supabase_claim = {
                "slug": claim["claim_id"],  # Use claim_id as slug
                "text_short": claim["canonical"][:500]
                if claim.get("canonical")
                else "",
                "text_long": claim.get("canonical"),
                "episode_id": claim.get("episode_id"),
                # Claim classification
                "claim_type": claim.get("claim_type"),
                "tier": claim.get("tier"),
                # Individual scores from JSON
                "confidence_score": scores.get("confidence", 0.5),
                "importance_score": scores.get("importance", 0.5),
                "novelty_score": scores.get("novelty", 0.5),
                "controversy_score": scores.get("controversy", 0.5),
                "fragility_score": scores.get("fragility", 0.5),
                "temporality_score": claim.get("temporality_score"),
                # JSON fields
                "structured_categories": categories,
                "raw_hce_json": claim,  # Store original for debugging
            }

            # Remove None values and empty strings
            supabase_claim = {
                k: v for k, v in supabase_claim.items() if v is not None and v != ""
            }
            supabase_claims.append(supabase_claim)

        result = (
            self.supabase.table("claims")
            .upsert(supabase_claims, on_conflict="slug")
            .execute()
        )

        print(f"✅ Claims uploaded: {len(result.data)}")
        return result.data

    def _upload_evidence(self, evidence_spans: list[dict]) -> list[dict]:
        """Upload evidence data to GetReceipts"""
        print("🎯 Uploading evidence...")

        supabase_evidence = []
        for evidence in evidence_spans:
            claim_uuid = self._get_claim_uuid(evidence.get("claim_id"))
            episode_uuid = self._get_episode_uuid(evidence.get("episode_id"))

            if not claim_uuid:
                print(
                    f"⚠️ Skipping evidence: claim {evidence.get('claim_id')} not found"
                )
                continue

            supabase_ev = {
                "claim_id": claim_uuid,
                "episode_id": episode_uuid,
                "quote_text": evidence.get("quote", "")[:1000],  # Limit length
                "evidence_type": evidence.get("evidence_type", "supporting"),
                "timestamp_start": evidence.get("t0"),
                "timestamp_end": evidence.get("t1"),
                "youtube_link": evidence.get("youtube_link"),
                "confidence": evidence.get("confidence"),
                "sequence_order": evidence.get("sequence_order"),
            }

            # Remove None values
            supabase_ev = {k: v for k, v in supabase_ev.items() if v is not None}
            supabase_evidence.append(supabase_ev)

        if supabase_evidence:
            result = self.supabase.table("evidence").insert(supabase_evidence).execute()
            print(f"✅ Evidence uploaded: {len(result.data)}")
            return result.data
        else:
            print("⚠️ No evidence to upload (missing claim references)")
            return []

    def _upload_people(self, people: list[dict]) -> list[dict]:
        """Upload people/entities data to GetReceipts"""
        print("👥 Uploading people...")

        supabase_people = []
        for person in people:
            claim_uuid = self._get_claim_uuid(person.get("claim_id"))
            episode_uuid = self._get_episode_uuid(person.get("episode_id"))

            supabase_person = {
                "claim_id": claim_uuid,
                "episode_id": episode_uuid,
                "name": person.get("surface_form") or person.get("name", ""),
                "surface_form": person.get("surface_form"),
                "entity_type": person.get("entity_type", "person"),
                "confidence": person.get("confidence"),
                "external_ids": self._parse_json_field(person.get("external_ids_json")),
                "timestamps": person.get("timestamps"),
                "segment_id": person.get("segment_id"),
            }

            # Remove None values and require name
            supabase_person = {
                k: v for k, v in supabase_person.items() if v is not None
            }
            if supabase_person.get("name"):
                supabase_people.append(supabase_person)

        if supabase_people:
            result = self.supabase.table("people").insert(supabase_people).execute()
            print(f"✅ People uploaded: {len(result.data)}")
            return result.data
        else:
            print("⚠️ No people to upload")
            return []

    def _upload_jargon(self, jargon: list[dict]) -> list[dict]:
        """Upload jargon/terminology data to GetReceipts"""
        print("📚 Uploading jargon...")

        supabase_jargon = []
        for term in jargon:
            claim_uuid = self._get_claim_uuid(term.get("claim_id"))
            episode_uuid = self._get_episode_uuid(term.get("episode_id"))

            supabase_term = {
                "claim_id": claim_uuid,
                "episode_id": episode_uuid,
                "term": term.get("term", ""),
                "definition": term.get("definition", ""),
                "category": term.get("category"),
                "domain": term.get("domain"),
                "related_terms": term.get("related_terms", []),
                "usage_examples": term.get("examples", []),
                "evidence_timestamps": term.get("evidence_timestamps", []),
            }

            # Remove None values and require term
            supabase_term = {k: v for k, v in supabase_term.items() if v is not None}
            if supabase_term.get("term"):
                supabase_jargon.append(supabase_term)

        if supabase_jargon:
            result = self.supabase.table("jargon").insert(supabase_jargon).execute()
            print(f"✅ Jargon uploaded: {len(result.data)}")
            return result.data
        else:
            print("⚠️ No jargon to upload")
            return []

    def _upload_mental_models(self, concepts: list[dict]) -> list[dict]:
        """Upload mental models/concepts data to GetReceipts"""
        print("🧠 Uploading mental models...")

        supabase_models = []
        for concept in concepts:
            claim_uuid = self._get_claim_uuid(concept.get("claim_id"))
            episode_uuid = self._get_episode_uuid(concept.get("episode_id"))

            supabase_model = {
                "claim_id": claim_uuid,
                "episode_id": episode_uuid,
                "name": concept.get("name", ""),
                # Try 'definition' first (new schema), fall back to 'description' (legacy)
                "description": concept.get("definition")
                or concept.get("description", ""),
                "domain": concept.get("domain"),
                "aliases": concept.get("aliases", []),
                "key_concepts": concept.get("key_concepts", []),
                "relationships": self._parse_json_field(
                    concept.get("relationships_json")
                ),
                "evidence_timestamps": concept.get("evidence_timestamps", []),
                "first_mention": concept.get("first_mention"),
            }

            # Remove None values and require name
            supabase_model = {k: v for k, v in supabase_model.items() if v is not None}
            if supabase_model.get("name"):
                supabase_models.append(supabase_model)

        if supabase_models:
            result = (
                self.supabase.table("mental_models").insert(supabase_models).execute()
            )
            print(f"✅ Mental models uploaded: {len(result.data)}")
            return result.data
        else:
            print("⚠️ No mental models to upload")
            return []

    def _upload_relationships(self, relations: list[dict]) -> list[dict]:
        """Upload claim relationships to GetReceipts"""
        print("🔗 Uploading relationships...")

        supabase_relations = []
        for relation in relations:
            source_uuid = self._get_claim_uuid(relation.get("source_claim_id"))
            target_uuid = self._get_claim_uuid(relation.get("target_claim_id"))

            if not (source_uuid and target_uuid):
                print(f"⚠️ Skipping relationship: missing claim references")
                continue

            supabase_rel = {
                "source_claim_id": source_uuid,
                "target_claim_id": target_uuid,
                "relationship_type": relation.get("relation_type", "related"),
                "strength": relation.get("strength", 0.5),
                "rationale": relation.get("rationale"),
                "evidence": relation.get("evidence"),
            }

            # Remove None values
            supabase_rel = {k: v for k, v in supabase_rel.items() if v is not None}
            supabase_relations.append(supabase_rel)

        if supabase_relations:
            result = (
                self.supabase.table("claim_relationships")
                .insert(supabase_relations)
                .execute()
            )
            print(f"✅ Relationships uploaded: {len(result.data)}")
            return result.data
        else:
            print("⚠️ No relationships to upload")
            return []

    # Helper methods

    def _parse_json_field(self, json_str: str | None) -> Any | None:
        """Parse JSON string field safely"""
        if not json_str or json_str.strip() == "":
            return None
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return None

    def _detect_source_type(self, url: str) -> str:
        """Detect source type from URL"""
        if not url:
            return "unknown"
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif any(ext in url_lower for ext in [".mp3", ".wav", ".m4a"]):
            return "audio"
        elif any(ext in url_lower for ext in [".pdf", ".doc", ".txt"]):
            return "document"
        else:
            return "unknown"

    def _get_claim_uuid(self, claim_id: str) -> str | None:
        """Get UUID for claim by slug/claim_id"""
        if not claim_id:
            return None

        try:
            result = (
                self.supabase.table("claims")
                .select("id")
                .eq("slug", claim_id)
                .execute()
            )
            if result.data:
                return result.data[0]["id"]
        except Exception as e:
            print(f"⚠️ Error looking up claim {claim_id}: {e}")

        return None

    def _get_episode_uuid(self, episode_id: str) -> str | None:
        """Get UUID for episode by episode_id"""
        if not episode_id:
            return None

        try:
            result = (
                self.supabase.table("episodes")
                .select("id")
                .eq("episode_id", episode_id)
                .execute()
            )
            if result.data:
                return result.data[0]["id"]
        except Exception as e:
            print(f"⚠️ Error looking up episode {episode_id}: {e}")

        return None

    def _print_upload_summary(self, results: dict[str, list]):
        """Print a summary of upload results"""
        print("\n📊 Upload Summary:")
        for table, data in results.items():
            count = len(data) if data else 0
            print(f"  {table}: {count} records")

        total = sum(len(data) if data else 0 for data in results.values())
        print(f"  Total: {total} records uploaded")


# Example usage
if __name__ == "__main__":
    # Simple test of the upload system (auto-authenticates with device credentials)
    uploader = GetReceiptsUploader()

    try:
        # Check if enabled
        if not uploader.is_enabled():
            print("Auto-upload is disabled. Enable in Settings to upload.")
        else:
            # Example session data
            test_data = {
                "episodes": [
                    {
                        "episode_id": "test_ep_001",
                        "title": "Test Episode",
                        "url": "https://youtube.com/watch?v=test",
                    }
                ],
                "claims": [
                    {
                        "claim_id": "test_claim_001",
                        "canonical": "This is a test claim",
                        "episode_id": "test_ep_001",
                    }
                ],
            }

            # Upload data (automatically uses device credentials)
            results = uploader.upload_session_data(test_data)
            print(f"Upload successful: {results}")

    except Exception as e:
        print(f"Test failed: {e}")
