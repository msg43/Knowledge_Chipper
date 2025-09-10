import logging
from pathlib import Path

from .models.llm_any import AnyLLM
from .types import PersonMention, Segment

logger = logging.getLogger(__name__)


class PeopleExtractor:
    def __init__(
        self,
        llm_local: AnyLLM,
        detect_prompt: Path,
        disambig_prompt: Path,
        flagship: AnyLLM | None = None,
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

    def detect(self, episode_id: str, segments: list[Segment]) -> list[PersonMention]:
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
                person_mention = PersonMention(
                    episode_id=episode_id,
                    mention_id=f"pm_{seg.segment_id}_{i}",
                    span_segment_id=seg.segment_id,
                    t0=r.get("t0", seg.t0),
                    t1=r.get("t1", seg.t1),
                    surface=r["surface"],
                    normalized=r.get("normalized"),
                    entity_type=r.get("entity_type", "person"),
                    confidence=r.get("confidence", 0.5),
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
            js = self.flagship.judge_json(self.disambig_t + "\n" + m.surface)
            m.normalized = js.get("normalized")
            m.external_ids = js.get("external_ids", {})
            out.append(m)
        return out


def extract_people(episode, people_disambiguator_model_uri: str) -> list[PersonMention]:
    """Compatibility wrapper used by HCEPipeline to extract people."""
    from pathlib import Path

    # Build LLM from provided model URI
    llm = AnyLLM(people_disambiguator_model_uri)

    # Get prompt paths
    detect_prompt = Path(__file__).parent / "prompts" / "people_detect.txt"
    disambig_prompt = Path(__file__).parent / "prompts" / "people_disambiguate.txt"

    # Create extractor
    extractor = PeopleExtractor(llm, detect_prompt, disambig_prompt)

    # Extract and disambiguate
    mentions = extractor.detect(episode.episode_id, episode.segments)
    return extractor.disambiguate(mentions)
