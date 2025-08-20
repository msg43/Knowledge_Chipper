from pathlib import Path

from .models.llm_any import AnyLLM
from .types import Relation, ScoredClaim


class RelationMiner:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def relate(self, claims: list[ScoredClaim]) -> list[Relation]:
        """Find relationships between claims using LLM analysis."""
        relations = []

        if len(claims) < 2:
            return relations

        # Process claims in pairs to find relationships
        for i, claim1 in enumerate(claims):
            for j, claim2 in enumerate(claims[i + 1 :], i + 1):
                try:
                    # Prepare prompt with both claims
                    prompt_text = self.template.format(
                        claim1=claim1.canonical,
                        claim2=claim2.canonical,
                        claim1_type=claim1.claim_type,
                        claim2_type=claim2.claim_type,
                    )

                    # Get LLM analysis
                    result = self.llm.generate_json(prompt_text)

                    if result and isinstance(result, list) and len(result) > 0:
                        relation_data = result[0]

                        # Only create relation if one is detected
                        if relation_data.get("has_relation", False):
                            relation = Relation(
                                episode_id=claim1.episode_id,
                                relation_id=f"rel_{claim1.claim_id}_{claim2.claim_id}",
                                source_claim_id=claim1.claim_id,
                                target_claim_id=claim2.claim_id,
                                relation_type=relation_data.get(
                                    "relation_type", "supports"
                                ),
                                strength=relation_data.get("strength", 0.5),
                                explanation=relation_data.get("explanation", ""),
                            )
                            relations.append(relation)

                except Exception as e:
                    # Continue processing even if one pair fails
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Failed to analyze relation between claims {i} and {j}: {e}"
                    )
                    continue

        return relations
