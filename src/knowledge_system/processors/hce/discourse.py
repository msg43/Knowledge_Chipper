from .models.llm_system2 import System2LLM
from .types import Segment

DISCOURSE_TAGS = ["claim", "evidence", "anecdote", "caveat", "hedge", "other"]


class DiscourseTagger:
    def __init__(self, llm: System2LLM):
        self.llm = llm

    def tag(self, seg: Segment) -> dict:
        """Tag segment with discourse type and confidence.

        Returns:
            Dictionary with "tag" (one of DISCOURSE_TAGS) and "confidence" (float)
        """
        try:
            # Analyze segment text for discourse type
            prompt = """Analyze this text segment and classify its discourse type:

Text: "{seg.text}"

Classify as one of: {', '.join(DISCOURSE_TAGS)}

Return JSON with "tag" and "confidence" (0.0-1.0).
"""

            result = self.llm.generate_json(prompt)

            if result and isinstance(result, list) and len(result) > 0:
                tag_data = result[0]
                tag = tag_data.get("tag", "other")
                confidence = tag_data.get("confidence", 0.5)

                # Validate tag is in allowed list
                if tag not in DISCOURSE_TAGS:
                    tag = "other"

                return {"tag": tag, "confidence": float(confidence)}

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Discourse tagging failed for segment {seg.segment_id}: {e}"
            )

        # Fallback
        return {"tag": "other", "confidence": 0.3}
