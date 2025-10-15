from pathlib import Path

from .models.llm_system2 import System2LLM
from .types import EvidenceSpan, JargonTerm, Segment


class GlossaryExtractor:
    def __init__(self, llm: System2LLM, prompt: Path):
        self.llm = llm
        self.template = prompt.read_text()

    def detect(self, episode_id: str, segments: list[Segment]) -> list[JargonTerm]:
        """Extract jargon terms using chunked processing for efficiency."""
        out: list[JargonTerm] = []

        # Group segments into chunks for processing (following skimmer pattern)
        chunk_size = (
            8  # Optimal size for jargon extraction - balances context vs attention
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

            # Generate jargon terms using LLM with chunk context
            try:
                js = self.llm.generate_json(
                    self.template
                    + "\n\nANALYZE THESE SEGMENTS FOR JARGON TERMS:\n\n"
                    + chunk_text
                )

                for j, r in enumerate(js):
                    # Ensure r is a dictionary before calling .get()
                    if not isinstance(r, dict):
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Skipping invalid jargon result type {type(r)} at chunk {i//chunk_size}, item {j}: {r}"
                        )
                        continue

                    # Check for required 'term' field
                    if "term" not in r:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Skipping jargon term without required 'term' field at chunk {i//chunk_size}: {r}"
                        )
                        continue

                    # Determine which segment this term belongs to (use source_segment_id or fallback)
                    source_segment_id = r.get("source_segment_id")
                    _source_segment = chunk[0]  # Default to first segment in chunk

                    if source_segment_id:
                        # Try to match segment_id to specific segment
                        for seg in chunk:
                            if seg.segment_id == source_segment_id:
                                break

                    out.append(
                        JargonTerm(
                            episode_id=episode_id,
                            term_id=f"jt_chunk_{i//chunk_size}_{j}",
                            term=r["term"],
                            category=r.get("category"),
                            definition=r.get("definition"),
                            evidence_spans=[
                                EvidenceSpan(**e)
                                for e in r.get("evidence", [])
                                if isinstance(e, dict)
                            ],
                        )
                    )

            except Exception as e:
                # Continue processing even if one chunk fails
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to process jargon chunk {i//chunk_size}: {e}")
                continue

        return out


def extract_jargon(episode, model_uri: str = "local://qwen2.5:7b") -> list[JargonTerm]:
    """Compatibility wrapper used by HCEPipeline to extract jargon terms."""
    from pathlib import Path

    # For now, we'll use a simple approach
    # In a full implementation, this would extract jargon terms
    try:
        from .models.llm_system2 import System2LLM

        # Use provided model URI
        llm = System2LLM(model_uri)
        prompt_path = Path(__file__).parent / "prompts" / "glossary_detect.txt"

        extractor = GlossaryExtractor(llm, prompt_path)
        return extractor.detect(episode.episode_id, episode.segments)
    except Exception:
        # Return empty list if extraction fails
        return []
