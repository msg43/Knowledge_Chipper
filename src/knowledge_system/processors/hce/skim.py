from pathlib import Path
from ...config import get_settings
from .types import EpisodeBundle, Milestone

from .models.llm_any import AnyLLM
from .types import Milestone, Segment


class Skimmer:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def skim(self, episode_id: str, segments: list[Segment]) -> list[Milestone]:
        """Extract key milestones from segments using LLM analysis."""
        milestones = []

        # Group segments into time-based chunks for processing
        chunk_size = 10  # Process 10 segments at a time

        for i in range(0, len(segments), chunk_size):
            chunk = segments[i : i + chunk_size]

            # Prepare chunk text for analysis
            chunk_text = "\n".join(
                [f"[{seg.t0}-{seg.t1}] {seg.speaker}: {seg.text}" for seg in chunk]
            )

            # Generate milestones using LLM
            try:
                results = self.llm.generate_json(self.template + "\n\n" + chunk_text)

                # Convert results to Milestone objects
                for j, result in enumerate(results):
                    milestone = Milestone(
                        milestone_id=f"ms_{episode_id}_{i//chunk_size}_{j}",
                        t0=result.get("t0", chunk[0].t0 if chunk else "0"),
                        t1=result.get("t1", chunk[-1].t1 if chunk else "0"),
                        title=result.get("title", "Key Point"),
                        description=result.get("description", ""),
                        importance=result.get("importance", 0.5),
                        topic=result.get("topic", "general"),
                    )
                    milestones.append(milestone)

            except Exception as e:
                # Continue processing even if one chunk fails
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to process chunk {i//chunk_size}: {e}")
                continue

        return milestones


def skim_episode(episode: EpisodeBundle, model_uri: str | None = None) -> list[Milestone]:
    """Compatibility wrapper used by HCEPipeline.

    If model_uri is provided, uses that model; otherwise falls back to settings.
    """
    settings = get_settings()
    # Use provided model or fall back to miner/default model
    resolved_model_uri = model_uri
    if not resolved_model_uri:
        resolved_model_uri = (
            f"openai://{settings.hce.miner_model}"
            if settings.llm.provider == "openai"
            else f"{settings.llm.provider}://{settings.llm.model}"
        )
    llm = AnyLLM(resolved_model_uri)
    prompt_path = Path(__file__).parent / "prompts" / "skim.txt"
    sk = Skimmer(llm, prompt_path)
    return sk.skim(episode.episode_id, episode.segments)
