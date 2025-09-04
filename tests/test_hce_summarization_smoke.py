from pathlib import Path

from src.knowledge_system.processors.summarizer import SummarizerProcessor


def test_processor_honors_use_skim_flag(tmp_path: Path):
    src_text = "Paragraph one.\n\nParagraph two."
    proc = SummarizerProcessor(
        provider="openai",
        model="gpt-4o-mini-2024-07-18",
        max_tokens=500,
        hce_options={"use_skim": False},
    )
    result = proc.process(src_text)
    assert result.success
    assert isinstance(result.data, str)


def test_dual_judge_routing_threshold_flag(tmp_path: Path):
    src_text = "A causes B. C is a fact."
    proc = SummarizerProcessor(
        provider="openai",
        model="gpt-4o-mini-2024-07-18",
        max_tokens=500,
        hce_options={
            "router_uncertainty_threshold": 0.9,  # effectively route none in typical cases
        },
    )
    result = proc.process(src_text)
    assert result.success
    assert "Key Claims" in result.data


def test_prompt_driven_summary_mode(tmp_path: Path):
    # Use a minimal template with {text}
    template = "Write a one-line summary.\n\n{text}"
    src = "This is a small document to summarize."
    proc = SummarizerProcessor(
        provider="openai",
        model="gpt-4o-mini-2024-07-18",
        max_tokens=200,
    )
    # prefer_template_summary triggers template path even if HCE works
    result = proc.process(
        src,
        dry_run=False,
        prompt_template=tmp_path.joinpath("tmpl.txt").write_text(template) or tmp_path.joinpath("tmpl.txt"),
        prefer_template_summary=True,
    )
    assert result.success
    assert isinstance(result.data, str)

