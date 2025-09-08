class CrossEncoder:
    """Cross-encoder model for scoring claim-context pairs."""

    def __init__(self, name: str):
        self.name = name
        self._model = None

    def _ensure_model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                import logging

                from sentence_transformers import CrossEncoder as STCrossEncoder

                logger = logging.getLogger(__name__)
                logger.info(f"Loading cross-encoder model: {self.name}")
                self._model = STCrossEncoder(self.name)
            except ImportError:
                import logging

                logger = logging.getLogger(__name__)
                logger.error("sentence-transformers not installed for cross-encoder")
                raise

    def score(self, pairs):
        """Score (context, claim) pairs using cross-encoder.

        Args:
            pairs: List of (context, claim) tuples

        Returns:
            List of float scores, one per pair
        """
        if not pairs:
            return []

        try:
            self._ensure_model()

            # Convert pairs to format expected by sentence-transformers
            formatted_pairs = [(context, claim) for context, claim in pairs]

            # Get scores from cross-encoder
            scores = self._model.predict(formatted_pairs)

            # Ensure scores are in [0,1] range
            import numpy as np

            scores = np.clip(scores, 0.0, 1.0)

            return scores.tolist() if hasattr(scores, "tolist") else list(scores)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Cross-encoder scoring failed: {e}")

            # Fallback: return neutral scores
            return [0.5] * len(pairs)
