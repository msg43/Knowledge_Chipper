import pytest


@pytest.mark.skip(
    reason="Complex HCE mocking - requires proper ConsolidatedClaim structure and pipeline setup"
)
def test_hce_summarization_with_mocks(monkeypatch):
    # Patch HCE validation to pass
    def mock_validate_hce():
        pass  # Just pass validation

    monkeypatch.setattr(
        "knowledge_system.processors.hce.health.validate_hce_or_raise",
        mock_validate_hce,
    )

    # Mock sentence transformers to avoid dependency issues
    import sys
    from unittest.mock import MagicMock

    sentence_transformers = MagicMock()
    sentence_transformers.SentenceTransformer.return_value.encode.return_value = [
        [0.1, 0.2, 0.3]
    ]
    sys.modules["sentence_transformers"] = sentence_transformers

    # Patch AnyLLM to avoid network/API calls
    from knowledge_system.processors.hce.models import llm_any as llm_any_mod

    def fake_generate_json(prompt: str):
        # Return one candidate claim for miner/glossary/concepts/people
        # Shape matches miner expectations for CandidateClaim
        return [
            {
                "episode_id": "test_episode",
                "segment_id": "seg_1",
                "candidate_id": "cand_1",
                "speaker": "Kenneth Rogoff",
                "claim_text": "AI-driven inflation risk will increase within 5-7 years.",
                "claim_type": "forecast",
                "stance": "asserts",
                "confidence_local": 0.8,
                "evidence_spans": [
                    {
                        "t0": "000000",
                        "t1": "000010",
                        "quote": "we will have another big inflation soon",
                        "segment_id": "seg_1",
                    }
                ],
            }
        ]

    def fake_judge_json(prompt: str):
        return {
            "importance": 0.9,
            "novelty": 0.7,
            "controversy": 0.5,
            "fragility": 0.4,
            "confidence_final": 0.85,
            "decision": "accept",
        }

    monkeypatch.setattr(
        llm_any_mod.AnyLLM, "generate_json", staticmethod(fake_generate_json)
    )
    monkeypatch.setattr(llm_any_mod.AnyLLM, "judge_json", staticmethod(fake_judge_json))

    # Run summarizer on simple input text
    from knowledge_system.processors.summarizer import SummarizerProcessor

    processor = SummarizerProcessor(provider="openai", model="gpt-4o-mini-2024-07-18")
    text = (
        "Kenneth Rogoff discusses future inflation dynamics.\n\n"
        "He predicts a significant inflation shock within a decade."
    )
    result = processor.process(text, dry_run=False, allow_llm_fallback=False)

    assert result.success is True
    assert isinstance(result.data, str)
    assert len(result.data) > 0
    md = result.metadata or {}
    # HCE path should extract at least one claim via mocks
    assert md.get("claims_extracted", 0) >= 1
