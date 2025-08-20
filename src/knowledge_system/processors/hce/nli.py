from .models.llm_any import AnyLLM


class NLI:
    def __init__(self, llm: AnyLLM):
        self.llm = llm

    def entailment(self, premise: str, hypothesis: str) -> float:
        """Calculate entailment score between premise and hypothesis.

        Args:
            premise: The premise statement
            hypothesis: The hypothesis statement

        Returns:
            Entailment score in [0,1] where 1.0 means strong entailment
        """
        try:
            prompt = f"""Analyze the logical relationship between these statements:

Premise: "{premise}"
Hypothesis: "{hypothesis}"

Determine if the premise entails (logically implies) the hypothesis.
Return a JSON object with:
- "entailment_score": float between 0.0 (no entailment) and 1.0 (strong entailment)
- "reasoning": brief explanation

Consider:
- Does the premise logically lead to the hypothesis?
- Is the hypothesis a logical consequence of the premise?
- How strong is the logical connection?
"""

            result = self.llm.generate_json(prompt)

            if result and isinstance(result, list) and len(result) > 0:
                data = result[0]
                score = data.get("entailment_score", 0.5)
                return max(0.0, min(1.0, float(score)))  # Clamp to [0,1]

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"NLI entailment analysis failed: {e}")

        # Fallback: neutral score
        return 0.5
