from pathlib import Path

from .models.llm_system2 import System2LLM
from .types import EvidenceSpan, MentalModel, Segment


class ConceptExtractor:
    def __init__(self, llm: System2LLM, prompt: Path):
        self.llm = llm
        self.template = prompt.read_text()

    def detect(self, source_id: str, segments: list[Segment]) -> list[MentalModel]:
        """Extract concepts using chunked processing for efficiency."""
        out: list[MentalModel] = []

        # Group segments into chunks for processing (following skimmer pattern)
        chunk_size = (
            8  # Optimal size for concept extraction - balances context vs attention
        )

        for i in range(0, len(segments), chunk_size):
            chunk = segments[i : i + chunk_size]

            # Prepare chunk text for analysis
            chunk_text = "\n".join(
                [
                    f"[segment_id={seg.segment_id} t0={seg.t0} t1={seg.t1} speaker={seg.speaker}]\n{seg.text}"
                    for seg in chunk
                ]
            )

            # Generate concepts using LLM with chunk context
            try:
                js = self.llm.generate_json(
                    self.template
                    + "\n\nANALYZE THESE SEGMENTS FOR CONCEPTS:\n\n"
                    + chunk_text
                )

                for j, r in enumerate(js):
                    # Ensure r is a dictionary before calling .get()
                    if not isinstance(r, dict):
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Skipping invalid concept result type {type(r)} at chunk {i//chunk_size}, item {j}: {r}"
                        )
                        continue

                    # Check for required 'name' field
                    if "name" not in r:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Skipping concept without required 'name' field at chunk {i//chunk_size}: {r}"
                        )
                        continue

                    # Determine which segment this concept belongs to (use first_mention_ts or fallback)
                    first_mention_ts = r.get("t0") or r.get("first_mention_ts")
                    source_segment = chunk[0]  # Default to first segment in chunk

                    if first_mention_ts:
                        # Try to match timestamp to specific segment
                        for seg in chunk:
                            if seg.t0 <= str(first_mention_ts) <= seg.t1:
                                source_segment = seg
                                break

                    out.append(
                        MentalModel(
                            source_id=source_id,
                            model_id=f"mm_chunk_{i//chunk_size}_{j}",
                            name=r["name"],
                            definition=r.get("definition"),
                            first_mention_ts=(
                                str(first_mention_ts)
                                if first_mention_ts
                                else source_segment.t0
                            ),
                            evidence_spans=[
                                EvidenceSpan(**e)
                                for e in r.get("evidence", [])
                                if isinstance(e, dict)
                            ],
                            aliases=r.get("aliases", []),
                        )
                    )

            except Exception as e:
                # Continue processing even if one chunk fails
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to process concept chunk {i//chunk_size}: {e}")
                continue

        return out


def extract_concepts(
    episode, scored_claims, model_uri: str = "local://qwen2.5:7b"
) -> list[MentalModel]:
    """Compatibility wrapper used by HCEPipeline to extract concepts."""
    from pathlib import Path

    # For now, we'll use a simple approach
    # In a full implementation, this would use the scored claims to inform concept extraction
    try:
        from .models.llm_system2 import System2LLM

        # Use provided model URI
        llm = System2LLM(model_uri)
        prompt_path = Path(__file__).parent / "prompts" / "concepts_detect.txt"

        extractor = ConceptExtractor(llm, prompt_path)
        return extractor.detect(episode.source_id, episode.segments)
    except Exception:
        # Return empty list if extraction fails
        return []
