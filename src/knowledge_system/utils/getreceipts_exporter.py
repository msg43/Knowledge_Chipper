"""
Enhanced GetReceipts integration for Knowledge_Chipper
Maps HCE PipelineOutputs to GetReceipts RF-1 format with rich knowledge artifacts
"""

import time
from typing import TYPE_CHECKING, Any

import requests
from pydantic import BaseModel

from .. import __version__
from ..logger import get_logger

if TYPE_CHECKING:
    from ..processors.hce.types import (
        JargonTerm,
        MentalModel,
        PersonMention,
        PipelineOutputs,
        Relation,
        ScoredClaim,
    )

logger = get_logger(__name__)


class GetReceiptsConfig(BaseModel):
    """Configuration for GetReceipts integration."""

    base_url: str = "https://getreceipts-web.vercel.app"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    min_confidence: float = 0.6
    max_claims_per_export: int = 20
    include_all_tiers: bool = True
    include_tier_c: bool = True
    include_evidence_timestamps: bool = True


class GetReceiptsExporter:
    """Enhanced exporter for HCE data to GetReceipts platform."""

    def __init__(self, config: GetReceiptsConfig | None = None):
        self.config = config or GetReceiptsConfig()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "User-Agent": f"Knowledge_Chipper/{__version__} GetReceipts-Integration",
            }
        )

        logger.info(f"Initialized GetReceipts exporter for {self.config.base_url}")

    def export_hce_pipeline_outputs(
        self,
        pipeline_outputs: "PipelineOutputs",
        source_info: dict[str, Any] | None = None,
        episode_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Export HCE PipelineOutputs to GetReceipts.

        Args:
            pipeline_outputs: HCE pipeline results with claims, entities, relations
            source_info: Optional source metadata (video URL, title, etc.)
            episode_context: Optional context about the episode

        Returns:
            Dictionary with export results and any errors
        """
        logger.info(
            f"Starting GetReceipts export for episode: {pipeline_outputs.episode_id}"
        )

        try:
            # Filter claims based on configuration
            filtered_claims = self._filter_claims(pipeline_outputs.claims)

            if not filtered_claims:
                logger.warning("No claims meet export criteria")
                return {
                    "success": False,
                    "error": "No claims meet minimum confidence or tier requirements",
                    "claims_processed": len(pipeline_outputs.claims),
                    "claims_exported": 0,
                }

            logger.info(
                f"Exporting {len(filtered_claims)} of {len(pipeline_outputs.claims)} claims"
            )

            # Export each claim as a separate receipt
            results = []
            for i, claim in enumerate(filtered_claims):
                try:
                    logger.info(
                        f"Processing claim {i+1}/{len(filtered_claims)}: {claim.claim_id}"
                    )

                    receipt = self._build_rf1_receipt(
                        claim, pipeline_outputs, source_info, episode_context
                    )

                    result = self._submit_receipt_with_retry(receipt)
                    results.append(result)

                    if result.get("success"):
                        logger.info(f"✅ Successfully exported claim {claim.claim_id}")
                    else:
                        logger.error(
                            f"❌ Failed to export claim {claim.claim_id}: {result.get('error')}"
                        )

                except Exception as e:
                    logger.error(f"Error processing claim {claim.claim_id}: {e}")
                    results.append(
                        {"success": False, "claim_id": claim.claim_id, "error": str(e)}
                    )

            # Summary results
            successful_exports = sum(1 for r in results if r.get("success"))
            failed_exports = len(results) - successful_exports

            export_result = {
                "success": successful_exports > 0,
                "claims_processed": len(pipeline_outputs.claims),
                "claims_exported": successful_exports,
                "claims_failed": failed_exports,
                "episode_id": pipeline_outputs.episode_id,
                "results": results,
            }

            logger.info(
                f"GetReceipts export complete: {successful_exports} successful, {failed_exports} failed"
            )
            return export_result

        except Exception as e:
            logger.error(f"GetReceipts export failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "episode_id": pipeline_outputs.episode_id,
                "claims_processed": (
                    len(pipeline_outputs.claims) if pipeline_outputs.claims else 0
                ),
                "claims_exported": 0,
            }

    def _filter_claims(self, claims: list["ScoredClaim"]) -> list["ScoredClaim"]:
        """Filter claims based on configuration criteria."""
        filtered = []

        for claim in claims:
            # Check confidence threshold
            confidence = claim.scores.get(
                "confidence_final", claim.scores.get("importance", 0.0)
            )
            if confidence < self.config.min_confidence:
                logger.debug(
                    f"Skipping claim {claim.claim_id}: confidence {confidence} < {self.config.min_confidence}"
                )
                continue

            # Check tier requirements
            if not self.config.include_all_tiers:
                if claim.tier == "C" and not self.config.include_tier_c:
                    logger.debug(f"Skipping Tier C claim {claim.claim_id}")
                    continue

            filtered.append(claim)

            # Respect max claims limit
            if len(filtered) >= self.config.max_claims_per_export:
                logger.info(
                    f"Reached max claims limit: {self.config.max_claims_per_export}"
                )
                break

        return filtered

    def _build_rf1_receipt(
        self,
        claim: "ScoredClaim",
        pipeline_outputs: "PipelineOutputs",
        source_info: dict[str, Any] | None,
        episode_context: str | None,
    ) -> dict[str, Any]:
        """Build RF-1 formatted receipt from HCE claim data."""

        # Build evidence with timestamps for YouTube links
        evidence_list = []
        for evidence in claim.evidence:
            evidence_item = {
                "text": evidence.quote,
                "timestamp": f"{evidence.t0}-{evidence.t1}",
                "segment_id": evidence.segment_id,
            }

            # Add YouTube timestamp link if source is video
            if source_info and source_info.get("url"):
                video_url = source_info["url"]
                if "youtube.com" in video_url or "youtu.be" in video_url:
                    # Parse timestamp to seconds for YouTube link
                    timestamp_seconds = self._parse_timestamp_to_seconds(evidence.t0)
                    if timestamp_seconds is not None:
                        evidence_item[
                            "youtube_link"
                        ] = f"{video_url}&t={timestamp_seconds}s"

            evidence_list.append(evidence_item)

        # Find related claims
        related_claims = self._find_related_claims(
            claim, pipeline_outputs.relations, pipeline_outputs.claims
        )

        # Build knowledge artifacts
        knowledge_artifacts = {
            "people": self._format_people_artifacts(pipeline_outputs.people),
            "jargon": self._format_jargon_artifacts(pipeline_outputs.jargon),
            "mental_models": self._format_mental_model_artifacts(
                pipeline_outputs.concepts
            ),
            "claim_relationships": related_claims,
        }

        # Build RF-1 receipt
        receipt = {
            "claim_text": claim.canonical,
            "claim_long": self._build_detailed_claim_description(claim, evidence_list),
            "topics": [claim.claim_type]
            + self._extract_topics_from_context(episode_context),
            "sources": self._format_sources(source_info, evidence_list),
            "supporters": evidence_list,
            "opponents": [],  # HCE doesn't extract explicit counterarguments yet
            "provenance": {
                "producer_app": "Knowledge_Chipper",
                "version": __version__,
                "hce_system": "enabled",
                "episode_id": pipeline_outputs.episode_id,
                "claim_id": claim.claim_id,
                "tier": claim.tier,
                "confidence": claim.scores.get("confidence_final", 0.0),
                "importance": claim.scores.get("importance", 0.0),
                "novelty": claim.scores.get("novelty", 0.0),
                "controversy": claim.scores.get("controversy", 0.0),
                "fragility": claim.scores.get("fragility", 0.0),
                "claim_type": claim.claim_type,
                "processed_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "knowledge_artifacts": knowledge_artifacts,
        }

        logger.debug(
            f"Built RF-1 receipt for claim {claim.claim_id} with {len(evidence_list)} evidence items"
        )
        return receipt

    def _parse_timestamp_to_seconds(self, timestamp: str) -> int | None:
        """Parse HCE timestamp to seconds for YouTube links."""
        try:
            # Handle formats like "00:01:30" or "90.5"
            if ":" in timestamp:
                parts = timestamp.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(float, parts)
                    return int(hours * 3600 + minutes * 60 + seconds)
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(float, parts)
                    return int(minutes * 60 + seconds)
            else:
                # Direct seconds
                return int(float(timestamp))
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp: {timestamp}")
            return None

    def _find_related_claims(
        self,
        current_claim: "ScoredClaim",
        relations: list["Relation"],
        all_claims: list["ScoredClaim"],
    ) -> list[dict[str, Any]]:
        """Find and format related claims for the current claim."""
        related = []

        # Create claim lookup
        claim_lookup = {c.claim_id: c for c in all_claims}

        for relation in relations:
            related_claim_id = None
            relationship_type = relation.type

            if relation.source_claim_id == current_claim.claim_id:
                related_claim_id = relation.target_claim_id
            elif relation.target_claim_id == current_claim.claim_id:
                related_claim_id = relation.source_claim_id
                # Reverse relationship direction
                if relationship_type == "supports":
                    relationship_type = "supported_by"
                elif relationship_type == "contradicts":
                    relationship_type = "contradicted_by"

            if related_claim_id and related_claim_id in claim_lookup:
                related_claim = claim_lookup[related_claim_id]
                related.append(
                    {
                        "claim_id": related_claim_id,
                        "claim_text": related_claim.canonical,
                        "relationship_type": relationship_type,
                        "strength": relation.strength,
                        "rationale": relation.rationale,
                    }
                )

        return related

    def _build_detailed_claim_description(
        self, claim: "ScoredClaim", evidence_list: list[dict[str, Any]]
    ) -> str:
        """Build detailed description combining claim and evidence."""
        description_parts = [claim.canonical]

        if evidence_list:
            description_parts.append("\n\nSupporting Evidence:")
            for i, evidence in enumerate(evidence_list[:3], 1):  # Limit to top 3
                description_parts.append(
                    f"{i}. {evidence['text']} (at {evidence['timestamp']})"
                )

        # Add scoring context
        scores = claim.scores
        if scores:
            description_parts.append("\n\nConfidence Metrics:")
            if "importance" in scores:
                description_parts.append(f"• Importance: {scores['importance']:.2f}")
            if "confidence_final" in scores:
                description_parts.append(
                    f"• Confidence: {scores['confidence_final']:.2f}"
                )
            if "controversy" in scores:
                description_parts.append(f"• Controversy: {scores['controversy']:.2f}")

        return "\n".join(description_parts)

    def _extract_topics_from_context(self, episode_context: str | None) -> list[str]:
        """Extract relevant topics from episode context."""
        if not episode_context:
            return []

        # Simple topic extraction - could be enhanced with NLP
        topics = []
        context_lower = episode_context.lower()

        # Common topic keywords
        topic_keywords = {
            "ai": [
                "artificial intelligence",
                "machine learning",
                "ai",
                "ml",
                "neural network",
            ],
            "science": ["research", "study", "experiment", "scientific", "data"],
            "technology": ["tech", "technology", "software", "digital", "computer"],
            "business": ["business", "company", "market", "economy", "finance"],
            "health": ["health", "medical", "medicine", "treatment", "disease"],
            "education": ["education", "learning", "teaching", "school", "university"],
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in context_lower for keyword in keywords):
                topics.append(topic)

        return topics[:5]  # Limit to 5 topics

    def _format_sources(
        self, source_info: dict[str, Any] | None, evidence_list: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format source information for RF-1."""
        sources = []

        if source_info:
            source_type = "video"
            if source_info.get("url"):
                url = source_info["url"]
                if "youtube.com" in url or "youtu.be" in url:
                    source_type = "video"
                elif any(ext in url.lower() for ext in [".pd", ".doc", ".txt"]):
                    source_type = "document"
                else:
                    source_type = "article"

            sources.append(
                {
                    "type": source_type,
                    "title": source_info.get("title", "Processed Content"),
                    "url": source_info.get("url", ""),
                    "date": source_info.get("date"),
                    "duration": source_info.get("duration"),
                    "evidence_timestamps": [
                        e.get("youtube_link")
                        for e in evidence_list
                        if e.get("youtube_link")
                    ],
                }
            )

        return sources

    def _format_people_artifacts(
        self, people: list["PersonMention"]
    ) -> list[dict[str, Any]]:
        """Format people mentions for knowledge artifacts."""
        formatted = []

        for person in people:
            formatted.append(
                {
                    "name": person.normalized or person.surface,
                    "surface_form": person.surface,
                    "entity_type": person.entity_type,
                    "confidence": person.confidence,
                    "timestamps": f"{person.t0}-{person.t1}",
                    "segment_id": person.span_segment_id,
                    "external_ids": person.external_ids,
                }
            )

        return formatted

    def _format_jargon_artifacts(
        self, jargon: list["JargonTerm"]
    ) -> list[dict[str, Any]]:
        """Format jargon terms for knowledge artifacts."""
        formatted = []

        for term in jargon:
            evidence_timestamps = [f"{e.t0}-{e.t1}" for e in term.evidence_spans]

            formatted.append(
                {
                    "term": term.term,
                    "definition": term.definition,
                    "category": term.category,
                    "evidence_timestamps": evidence_timestamps,
                    "usage_examples": [
                        e.quote for e in term.evidence_spans[:3]
                    ],  # Top 3 examples
                }
            )

        return formatted

    def _format_mental_model_artifacts(
        self, concepts: list["MentalModel"]
    ) -> list[dict[str, Any]]:
        """Format mental models for knowledge artifacts."""
        formatted = []

        for model in concepts:
            evidence_timestamps = [f"{e.t0}-{e.t1}" for e in model.evidence_spans]

            formatted.append(
                {
                    "name": model.name,
                    "description": model.definition,
                    "aliases": model.aliases,
                    "evidence_timestamps": evidence_timestamps,
                    "key_concepts": [
                        e.quote for e in model.evidence_spans[:3]
                    ],  # Top 3 concepts
                    "first_mention": model.first_mention_ts,
                }
            )

        return formatted

    def _submit_receipt_with_retry(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Submit receipt with retry logic and comprehensive error handling."""

        for attempt in range(self.config.max_retries):
            try:
                logger.debug(
                    f"Submitting receipt (attempt {attempt + 1}/{self.config.max_retries})"
                )

                response = self.session.post(
                    f"{self.config.base_url}/api/receipts",
                    json=receipt,
                    timeout=self.config.timeout_seconds,
                )

                # Log response details
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")

                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    logger.info("✅ Receipt submitted successfully")
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response": result,
                        "claim_id": receipt.get("provenance", {}).get("claim_id"),
                        "url": result.get("url") or result.get("slug"),
                        "receipt_id": result.get("id"),
                    }
                else:
                    error_text = response.text
                    logger.warning(
                        f"Receipt submission failed: HTTP {response.status_code}"
                    )
                    logger.warning(f"Response: {error_text}")

                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return {
                            "success": False,
                            "status_code": response.status_code,
                            "error": f"Client error: {error_text}",
                            "claim_id": receipt.get("provenance", {}).get("claim_id"),
                            "no_retry": True,
                        }

                    # Retry on server errors (5xx)
                    if attempt < self.config.max_retries - 1:
                        logger.info(f"Retrying in {self.config.retry_delay} seconds...")
                        time.sleep(
                            self.config.retry_delay * (attempt + 1)
                        )  # Exponential backoff
                        continue

                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": f"Server error after {self.config.max_retries} attempts: {error_text}",
                        "claim_id": receipt.get("provenance", {}).get("claim_id"),
                    }

            except requests.exceptions.Timeout:
                error_msg = (
                    f"Request timeout after {self.config.timeout_seconds} seconds"
                )
                logger.warning(error_msg)

                if attempt < self.config.max_retries - 1:
                    logger.info(f"Retrying in {self.config.retry_delay} seconds...")
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue

                return {
                    "success": False,
                    "error": error_msg,
                    "claim_id": receipt.get("provenance", {}).get("claim_id"),
                }

            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {e}"
                logger.warning(error_msg)

                if attempt < self.config.max_retries - 1:
                    logger.info(f"Retrying in {self.config.retry_delay} seconds...")
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue

                return {
                    "success": False,
                    "error": error_msg,
                    "claim_id": receipt.get("provenance", {}).get("claim_id"),
                }

            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                logger.error(error_msg)

                return {
                    "success": False,
                    "error": error_msg,
                    "claim_id": receipt.get("provenance", {}).get("claim_id"),
                }

        return {
            "success": False,
            "error": f"Failed after {self.config.max_retries} attempts",
            "claim_id": receipt.get("provenance", {}).get("claim_id"),
        }


def create_exporter_from_settings(
    settings: dict[str, Any] | None = None,
) -> GetReceiptsExporter:
    """Create GetReceipts exporter from settings configuration."""

    if not settings:
        from ..config import get_settings

        settings = get_settings()

    # Extract GetReceipts config from settings
    getreceipts_config = settings.get("getreceipts", {})

    config = GetReceiptsConfig(
        base_url=getreceipts_config.get(
            "base_url", "https://getreceipts-web.vercel.app"
        ),
        timeout_seconds=getreceipts_config.get("timeout_seconds", 30),
        max_retries=getreceipts_config.get("max_retries", 3),
        retry_delay=getreceipts_config.get("retry_delay", 1.0),
        min_confidence=getreceipts_config.get("min_confidence", 0.6),
        max_claims_per_export=getreceipts_config.get("max_claims_per_export", 20),
        include_all_tiers=getreceipts_config.get("include_all_tiers", True),
        include_tier_c=getreceipts_config.get("include_tier_c", True),
        include_evidence_timestamps=getreceipts_config.get(
            "include_evidence_timestamps", True
        ),
    )

    return GetReceiptsExporter(config)
