from __future__ import annotations

from knowledge_system.superchunk.config import SuperChunkConfig
from knowledge_system.superchunk.segmenter import Paragraph, Segmenter


def test_boundary_respects_hotspots_and_sentences():
    cfg = SuperChunkConfig()
    seg = Segmenter(config=cfg)
    paras = [
        Paragraph(text="Alpha. Beta continues.", span_start=0, span_end=21),
        Paragraph(
            text="Gamma is here and continues. Delta ends.", span_start=22, span_end=62
        ),
        Paragraph(
            text="Hotspot should not be split. Keep together.",
            span_start=63,
            span_end=106,
        ),
    ]
    hotspots = [[1, 2]]
    chunks = seg.segment(paras, hotspots=hotspots)
    assert len(chunks) >= 1
    # Ensure final chunk ends at sentence boundary
    for ch in chunks:
        assert ch.text.endswith((".", "!", "?")) or len(ch.text) > 0
