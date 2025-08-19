from .models.llm_any import AnyLLM
from .types import Segment

DISCOURSE_TAGS = ["claim", "evidence", "anecdote", "caveat", "hedge", "other"]


class DiscourseTagger:
    def __init__(self, llm: AnyLLM):
        self.llm = llm

    def tag(self, seg: Segment) -> dict:
        # Return {"tag": one of DISCOURSE_TAGS, "confidence": float}
        raise NotImplementedError("DiscourseTagger.tag not implemented")
