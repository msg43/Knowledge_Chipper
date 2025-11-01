import logging
from pathlib import Path

from .models.llm_system2 import System2LLM
from .types import PersonMention, Segment

logger = logging.getLogger(__name__)


class PeopleExtractor:
    def __init__(
        self,
        llm_local: System2LLM,
        detect_prompt: Path,
        disambig_prompt: Path,
        flagship: System2LLM | None = None,
        use_entity_cache: bool = True,
    ):
        self.local = llm_local
        self.detect_t = detect_prompt.read_text()
        self.disambig_t = disambig_prompt.read_text()
        self.flagship = flagship
        self.use_entity_cache = use_entity_cache

        # Initialize entity cache if enabled
        if self.use_entity_cache:
            try:
                from ...utils.entity_cache import get_entity_cache

                self.entity_cache = get_entity_cache()
            except ImportError:
                logger.warning("Entity cache not available, continuing without cache")
                self.entity_cache = None
                self.use_entity_cache = False
        else:
            self.entity_cache = None

    def detect(self, source_id: str, segments: list[Segment]) -> list[PersonMention]:
        out: list[PersonMention] = []

        # Check cache for suggested entities if enabled
        suggested_entities = []
        if self.use_entity_cache and self.entity_cache:
            # Get full text for cache suggestions
            full_text = " ".join(seg.text for seg in segments)
            suggested_entities = self.entity_cache.get_suggested_entities(
                full_text, "person"
            )

            if suggested_entities:
                logger.info(
                    f"Found {len(suggested_entities)} suggested people from cache"
                )

        for seg in segments:
            # Check if any cached entities appear in this segment
            cached_matches = []
            if suggested_entities:
                for entity in suggested_entities:
                    if entity.name.lower() in seg.text.lower():
                        cached_matches.append(entity)

            # Generate new detections
            js = self.local.generate_json(
                self.detect_t
                + f"\n[segment_id={seg.segment_id} t0={seg.t0} t1={seg.t1}]\n"
                + seg.text
            )

            for i, r in enumerate(js):
                # Ensure r is a dictionary before calling .get()
                if not isinstance(r, dict):
                    logger.warning(
                        f"Skipping invalid person result type {type(r)} at index {i}: {r}"
                    )
                    continue

                # Validate normalized field - ensure it's a string or None
                normalized_value = r.get("normalized")
                if normalized_value is not None and not isinstance(
                    normalized_value, str
                ):
                    # Convert non-string values to None to avoid validation errors
                    normalized_value = None
                    logger.debug(
                        f"Invalid normalized value type {type(normalized_value)} for {r.get('surface', 'unknown')}, setting to None"
                    )

                # Check if required 'surface' field exists
                if "surface" not in r:
                    logger.warning(
                        f"Skipping person mention without required 'surface' field: {r}"
                    )
                    continue

                # Ensure timestamp values are strings
                t0_val = r.get("t0", seg.t0)
                t1_val = r.get("t1", seg.t1)
                t0_str = str(t0_val) if t0_val is not None else seg.t0
                t1_str = str(t1_val) if t1_val is not None else seg.t1

                person_mention = PersonMention(
                    source_id=source_id,
                    mention_id=f"pm_{seg.segment_id}_{i}",
                    span_segment_id=seg.segment_id,
                    t0=t0_str,
                    t1=t1_str,
                    surface=r["surface"],
                    normalized=normalized_value,
                    entity_type=r.get("entity_type", "person"),
                    confidence=float(r.get("confidence") or 0.5),
                )
                out.append(person_mention)

                # Update entity cache with new detection
                if self.use_entity_cache and self.entity_cache:
                    try:
                        self.entity_cache.add_or_update_entity(
                            name=person_mention.surface,
                            description=r.get("description", ""),
                            entity_type="person",
                            confidence=person_mention.confidence,
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update entity cache: {e}")

        # Save cache after processing
        if self.use_entity_cache and self.entity_cache:
            try:
                self.entity_cache.save()
            except Exception as e:
                logger.debug(f"Failed to save entity cache: {e}")

        return out

    def disambiguate(self, mentions: list[PersonMention]) -> list[PersonMention]:
        if not self.flagship:
            return mentions
        out = []
        for m in mentions:
            if m.normalized:
                out.append(m)
                continue
            js_result = self.flagship.generate_json(self.disambig_t + "\n" + m.surface)

            # Handle the fact that generate_json returns a list
            if js_result and isinstance(js_result, list) and len(js_result) > 0:
                js = js_result[0]
                # Ensure js is a dictionary before calling .get()
                if isinstance(js, dict):
                    m.normalized = js.get("normalized")
                    m.external_ids = js.get("external_ids", {})
            out.append(m)
        return out


def extract_people(episode, people_disambiguator_model_uri: str) -> list[PersonMention]:
    """Compatibility wrapper used by HCEPipeline to extract people."""
    from pathlib import Path

    # Build LLM from provided model URI
    llm = System2LLM(people_disambiguator_model_uri)

    # Get prompt paths
    detect_prompt = Path(__file__).parent / "prompts" / "people_detect.txt"
    disambig_prompt = Path(__file__).parent / "prompts" / "people_disambiguate.txt"

    # Create extractor
    extractor = PeopleExtractor(llm, detect_prompt, disambig_prompt)

    # Extract and disambiguate
    mentions = extractor.detect(episode.source_id, episode.segments)
    return extractor.disambiguate(mentions)
