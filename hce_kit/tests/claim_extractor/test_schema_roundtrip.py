from claim_extractor.types import EpisodeBundle


def test_episode_schema():
    sample = {
        "episode_id": "ep_001",
        "segments": [
            {
                "episode_id": "ep_001",
                "segment_id": "s1",
                "speaker": "HOST",
                "t0": "00:00:00.000",
                "t1": "00:00:12.500",
                "text": "Welcome",
            }
        ],
    }
    eb = EpisodeBundle.model_validate(sample)
    assert eb.episode_id == "ep_001"
