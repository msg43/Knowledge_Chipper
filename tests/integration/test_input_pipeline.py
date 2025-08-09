from unittest.mock import patch

from knowledge_system.processors import registry


class DummyResult:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return getattr(other, "value", None) == self.value


def test_youtube_metadata_routing_and_processing():
    url = "https://www.youtube.com/watch?v=abc123"
    proc_cls = registry.get_processor_for_input(url)
    assert proc_cls.__name__ == "YouTubeMetadataProcessor"
    with patch.object(
        proc_cls, "process", return_value=DummyResult("meta-ok")
    ) as mock_proc:
        proc = proc_cls()
        result = proc.process(url)
        mock_proc.assert_called_once_with(url)
        assert result == DummyResult("meta-ok")


def test_youtube_download_routing_and_processing():
    url = "https://youtu.be/xyz456"
    # Should match YouTubeDownloadProcessor (last registered for this pattern)
    proc_cls = registry.get_processor_for_input(url)
    assert proc_cls.__name__ in ("YouTubeMetadataProcessor", "YouTubeDownloadProcessor")
    with patch.object(
        proc_cls, "process", return_value=DummyResult("audio-ok")
    ) as mock_proc:
        proc = proc_cls()
        result = proc.process(url)
        mock_proc.assert_called_once_with(url)
        assert result == DummyResult("audio-ok")


def test_pdf_routing_and_processing():
    file_path = "test.pdf"
    proc_cls = registry.get_processor_for_input(file_path)
    assert proc_cls.__name__ == "PDFProcessor"
    with patch.object(
        proc_cls, "process", return_value=DummyResult("pdf-ok")
    ) as mock_proc:
        proc = proc_cls()
        result = proc.process(file_path)
        mock_proc.assert_called_once_with(file_path)
        assert result == DummyResult("pdf-ok")


def test_unknown_input_returns_none():
    assert registry.get_processor_for_input("file.unknown") is None
    assert registry.get_processor_for_input("https://notyoutube.com/abc") is None
