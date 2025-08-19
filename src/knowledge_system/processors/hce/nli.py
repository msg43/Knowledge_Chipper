from .models.llm_any import AnyLLM


class NLI:
    def __init__(self, llm: AnyLLM):
        self.llm = llm

    def entailment(self, premise: str, hypothesis: str) -> float:
        # Return entailment score in [0,1]; TODO implement
        raise NotImplementedError("NLI.entailment not implemented")
