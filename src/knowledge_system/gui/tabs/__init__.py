""" GUI tabs package.""".

from .api_keys_tab import APIKeysTab
from .introduction_tab import IntroductionTab
from .process_tab import ProcessTab
from .summarization_tab import SummarizationTab
from .transcription_tab import TranscriptionTab
from .watcher_tab import WatcherTab
from .youtube_tab import YouTubeTab

__all__ = [
    "IntroductionTab",
    "ProcessTab",
    "WatcherTab",
    "YouTubeTab",
    "TranscriptionTab",
    "SummarizationTab",
    "APIKeysTab",
]
