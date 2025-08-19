from collections import defaultdict

from .types import PipelineOutputs


def rollup(outputs: list[PipelineOutputs]):
    people = defaultdict(int)
    models = defaultdict(int)
    jargon = defaultdict(int)
    for o in outputs:
        for p in o.people:
            people[p.normalized or p.surface] += 1
        for m in o.concepts:
            models[m.name] += 1
        for t in o.jargon:
            jargon[t.term] += 1
    return people, models, jargon
